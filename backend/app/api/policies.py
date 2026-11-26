"""Zero-code policy rules: CRUD for UI rules, read-only view of file rules, import/export, re-audit."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import col, select

from app.api.projects import get_project
from app.core.deps import CurrentUser, SessionDep, SettingsDep
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.models import AuditRun, PolicyRule
from app.models.tables import utcnow
from app.services.policy import (
    RuleSpec,
    field_catalog,
    latest_audit,
    load_all_rules,
    parse_rules,
    run_audit,
)

router = APIRouter(tags=["policies"])


class PolicyRuleOut(RuleSpec):
    db_id: int | None
    source: str  # "ui" or "file:<name>"
    editable: bool


class PolicyFileOut(BaseModel):
    name: str
    modified: str
    rules: int
    error: str | None


class PoliciesOut(BaseModel):
    rules: list[PolicyRuleOut]
    files: list[PolicyFileOut]
    errors: list[str]
    policy_dir: str


class EnabledIn(BaseModel):
    enabled: bool


class ImportIn(BaseModel):
    rules: list[dict[str, Any]]


class ImportOut(BaseModel):
    created: int
    updated: int
    errors: list[str]


class AuditRunOut(BaseModel):
    id: int
    created_at: datetime
    findings: list[dict[str, Any]]
    errors: list[str]
    rules_evaluated: int
    resolved: int
    new_count: int
    counts: dict[str, int]


def _run_out(run: AuditRun) -> AuditRunOut:
    assert run.id is not None
    counts = {
        s: sum(1 for f in run.findings if f["severity"] == s) for s in ("high", "medium", "low")
    }
    return AuditRunOut(
        id=run.id,
        created_at=run.created_at,
        findings=run.findings,
        errors=run.errors,
        rules_evaluated=run.rules_evaluated,
        resolved=run.resolved,
        new_count=sum(1 for f in run.findings if f.get("new")),
        counts=counts,
    )


def _apply(row: PolicyRule, spec: RuleSpec) -> None:
    row.rule_key = spec.id
    row.name = spec.name
    row.description = spec.description
    row.scope = spec.scope
    row.when = spec.when.model_dump(by_alias=True, exclude_none=True) if spec.when else None
    row.flag_if = spec.flag_if.model_dump(by_alias=True, exclude_none=True)
    row.severity = spec.severity
    row.message = spec.message
    row.enabled = spec.enabled
    row.updated_at = utcnow()


@router.get("/policies/fields")
def list_fields(_: CurrentUser) -> list[dict[str, Any]]:
    return field_catalog()


@router.get("/policies", response_model=PoliciesOut)
def list_policies(_: CurrentUser, session: SessionDep, settings: SettingsDep) -> PoliciesOut:
    rules, files, errors = load_all_rules(session, settings.policy_dir)
    return PoliciesOut(
        rules=[
            PolicyRuleOut(
                **r.spec.model_dump(by_alias=True),
                db_id=r.db_id,
                source=r.source,
                editable=r.source == "ui",
            )
            for r in rules
        ],
        files=[
            PolicyFileOut(name=f.name, modified=f.modified, rules=f.rules, error=f.error)
            for f in files
        ],
        errors=errors,
        policy_dir=str(settings.policy_dir),
    )


@router.post("/policies", response_model=PolicyRuleOut, status_code=201)
def create_policy(body: RuleSpec, _: CurrentUser, session: SessionDep) -> PolicyRuleOut:
    if session.exec(select(PolicyRule).where(col(PolicyRule.rule_key) == body.id)).first():
        raise ConflictError(f"A rule with id '{body.id}' already exists")
    row = PolicyRule(rule_key=body.id, name=body.name)
    _apply(row, body)
    session.add(row)
    session.commit()
    return PolicyRuleOut(**body.model_dump(by_alias=True), db_id=row.id, source="ui", editable=True)


@router.put("/policies/{rule_id}", response_model=PolicyRuleOut)
def update_policy(
    rule_id: int, body: RuleSpec, _: CurrentUser, session: SessionDep
) -> PolicyRuleOut:
    row = session.get(PolicyRule, rule_id)
    if row is None:
        raise NotFoundError(f"Rule {rule_id} not found")
    clash = session.exec(select(PolicyRule).where(col(PolicyRule.rule_key) == body.id)).first()
    if clash is not None and clash.id != rule_id:
        raise ConflictError(f"A rule with id '{body.id}' already exists")
    _apply(row, body)
    session.add(row)
    session.commit()
    return PolicyRuleOut(**body.model_dump(by_alias=True), db_id=row.id, source="ui", editable=True)


@router.patch("/policies/{rule_id}", response_model=PolicyRuleOut)
def toggle_policy(
    rule_id: int, body: EnabledIn, _: CurrentUser, session: SessionDep
) -> PolicyRuleOut:
    row = session.get(PolicyRule, rule_id)
    if row is None:
        raise NotFoundError(f"Rule {rule_id} not found")
    row.enabled = body.enabled
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    from app.services.policy import db_rule_spec

    return PolicyRuleOut(
        **db_rule_spec(row).model_dump(by_alias=True), db_id=row.id, source="ui", editable=True
    )


@router.delete("/policies/{rule_id}", status_code=204)
def delete_policy(rule_id: int, _: CurrentUser, session: SessionDep) -> None:
    row = session.get(PolicyRule, rule_id)
    if row is None:
        raise NotFoundError(f"Rule {rule_id} not found")
    session.delete(row)
    session.commit()


@router.post("/policies/import", response_model=ImportOut)
def import_policies(body: ImportIn, _: CurrentUser, session: SessionDep) -> ImportOut:
    specs, errors = parse_rules({"rules": body.rules})
    if not specs and errors:
        raise ValidationFailedError("; ".join(errors[:3]))
    created = updated = 0
    for spec in specs:
        row = session.exec(select(PolicyRule).where(col(PolicyRule.rule_key) == spec.id)).first()
        if row is None:
            row = PolicyRule(rule_key=spec.id, name=spec.name)
            created += 1
        else:
            updated += 1
        _apply(row, spec)
        session.add(row)
    session.commit()
    return ImportOut(created=created, updated=updated, errors=errors)


@router.get("/policies/export")
def export_policies(_: CurrentUser, session: SessionDep) -> dict[str, Any]:
    from app.services.policy import db_rule_spec

    rows = session.exec(select(PolicyRule).order_by(col(PolicyRule.id))).all()
    return {"rules": [db_rule_spec(r).model_dump(by_alias=True, exclude_none=True) for r in rows]}


@router.post("/projects/{project_id}/audit", response_model=AuditRunOut)
def rerun_audit(
    project_id: int, _: CurrentUser, session: SessionDep, settings: SettingsDep
) -> AuditRunOut:
    return _run_out(run_audit(session, get_project(session, project_id), settings.policy_dir))


@router.get("/projects/{project_id}/audit", response_model=AuditRunOut | None)
def read_audit(project_id: int, _: CurrentUser, session: SessionDep) -> AuditRunOut | None:
    get_project(session, project_id)
    run = latest_audit(session, project_id)
    return _run_out(run) if run else None
