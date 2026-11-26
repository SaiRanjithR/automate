"""Zero-code policy rules and the re-audit engine.

A rule is pure data (UI form, JSON or YAML file):

    id: penalty-cap
    name: Penalty above 1%
    scope: requirement            # requirement | tender | company
    when:  {field: requirement.text, op: matches, value: "penalt|liquidated damages"}
    flag_if: {field: requirement.max_percent, op: gt, value: 1}
    severity: high                # high | medium | low
    message: "{requirement.code}: penalty of {requirement.max_percent}% exceeds our 1% cap"
    enabled: true

Conditions are {field, op, value} or {all: [...]}, {any: [...]}, {not: {...}}. Fields are listed in
FIELDS. Requirement rules are checked once per requirement row; tender and company rules once per
project. Files in POLICY_DIR are re-read on every audit, so edits apply without a restart.
"""

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import (
    BaseModel,
    Field,
    SerializerFunctionWrapHandler,
    ValidationError,
    field_validator,
    model_serializer,
    model_validator,
)
from sqlmodel import Session, col, select

from app.models import (
    AuditRun,
    Company,
    EvaluationCriterion,
    PolicyRule,
    Project,
    Requirement,
    Response,
    SubmissionRules,
)

logger = logging.getLogger(__name__)

Scope = Literal["requirement", "tender", "company"]
Severity = Literal["high", "medium", "low"]
OPS = (
    "eq", "neq", "gt", "gte", "lt", "lte", "contains", "not_contains", "contains_any",
    "not_contains_any", "matches", "not_matches", "in", "not_in", "exists", "not_exists",
    "is_true", "is_false",
)  # fmt: skip
NO_VALUE_OPS = ("exists", "not_exists", "is_true", "is_false")


# ---------------------------------------------------------------- schema


class Condition(BaseModel):
    field: str | None = None
    op: str | None = None
    value: Any = None
    all: list["Condition"] | None = None
    any: list["Condition"] | None = None
    not_: "Condition | None" = Field(default=None, alias="not")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _one_kind(self) -> "Condition":
        kinds = [
            self.field is not None,
            self.all is not None,
            self.any is not None,
            self.not_ is not None,
        ]
        if sum(kinds) != 1:
            raise ValueError("a condition needs exactly one of: field, all, any, not")
        if self.field is not None:
            if self.field not in FIELDS:
                raise ValueError(f"unknown field '{self.field}'")
            if self.op not in OPS:
                raise ValueError(f"unknown op '{self.op}' (use one of {', '.join(OPS)})")
            if self.op in ("matches", "not_matches"):
                try:
                    re.compile(str(self.value))
                except re.error as exc:
                    raise ValueError(f"invalid regular expression: {exc}") from exc
        return self

    @model_serializer(mode="wrap")
    def _only_used_keys(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Emit only the keys a condition uses, e.g. {"all": [...]} without "field": null."""
        data: dict[str, Any] = handler(self)
        return {k: v for k, v in data.items() if v is not None}

    def fields(self) -> set[str]:
        out = {self.field} if self.field else set()
        for child in (self.all or []) + (self.any or []) + ([self.not_] if self.not_ else []):
            out |= child.fields()
        return out


class RuleSpec(BaseModel):
    id: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=160)
    description: str = ""
    scope: Scope = "requirement"
    when: Condition | None = None
    flag_if: Condition
    severity: Severity = "medium"
    message: str = ""
    enabled: bool = True

    @field_validator("id")
    @classmethod
    def _slug(cls, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
        if not slug:
            raise ValueError("id must contain letters or digits")
        return slug

    @model_validator(mode="after")
    def _fields_match_scope(self) -> "RuleSpec":
        allowed = {name for name, f in FIELDS.items() if self.scope in f.scopes}
        used = self.flag_if.fields() | (self.when.fields() if self.when else set())
        wrong = sorted(used - allowed)
        if wrong:
            raise ValueError(f"field(s) {', '.join(wrong)} cannot be used in a {self.scope} rule")
        return self


# ---------------------------------------------------------------- field catalog


@dataclass(frozen=True)
class FieldDef:
    type: str  # text | number | boolean | list
    scopes: tuple[str, ...]
    description: str


R = ("requirement",)
ALL = ("requirement", "tender", "company")
TR = ("requirement", "tender")

FIELDS: dict[str, FieldDef] = {
    "requirement.code": FieldDef("text", R, "Requirement ID, e.g. R-5.7-01"),
    "requirement.text": FieldDef("text", R, "The requirement sentence"),
    "requirement.section": FieldDef("text", R, "Clause number and heading"),
    "requirement.category": FieldDef(
        "text", R, "functional, technical, security, sla, commercial, ..."
    ),
    "requirement.type": FieldDef("text", R, "mandatory or optional"),
    "requirement.criterion": FieldDef("text", R, "Scoring criterion it is linked to"),
    "requirement.change": FieldDef("text", R, "unchanged, modified, added (by an addendum)"),
    "requirement.max_percent": FieldDef(
        "number", R, "Largest percentage in the clause (e.g. penalty %)"
    ),
    "requirement.max_amount_inr": FieldDef(
        "number", R, "Largest rupee amount in the clause (lakh/crore understood)"
    ),
    "requirement.max_days": FieldDef(
        "number", R, "Largest period in days in the clause (weeks/months converted)"
    ),
    "answer.text": FieldDef("text", R, "Drafted or edited answer"),
    "answer.status": FieldDef(
        "text",
        R,
        "fully_compliant, partially_compliant, non_compliant, compliant_with_customisation, gap, pending",
    ),
    "answer.approved": FieldDef("boolean", R, "Approved by a person"),
    "answer.has_answer": FieldDef("boolean", R, "An answer exists"),
    "answer.is_commitment": FieldDef("boolean", R, "Answer is a commitment to the RFP clause"),
    "answer.word_count": FieldDef("number", R, "Words in the answer"),
    "answer.citation_count": FieldDef("number", R, "Number of evidence citations"),
    "answer.review_score": FieldDef("number", R, "Review score 0-100"),
    "tender.title": FieldDef("text", TR, "Tender title"),
    "tender.buyer": FieldDef("text", TR, "Buyer / tender inviting authority"),
    "tender.portal": FieldDef("text", TR, "Submission portal"),
    "tender.bid_system": FieldDef("text", TR, "two_bid or empty"),
    "tender.emd_inr": FieldDef("number", TR, "Earnest money deposit in rupees"),
    "tender.days_to_deadline": FieldDef(
        "number", TR, "Days left until submission (negative if passed)"
    ),
    "tender.page_limit": FieldDef("number", TR, "Technical proposal page limit"),
    "tender.validity_days": FieldDef("number", TR, "Bid validity in days"),
    "tender.technical_weight": FieldDef("number", TR, "Technical weight in QCBS (e.g. 70)"),
    "tender.requirement_count": FieldDef("number", TR, "Number of requirements"),
    "tender.mandatory_gaps": FieldDef("number", TR, "Mandatory requirements without an answer"),
    "tender.approved_percent": FieldDef("number", TR, "Share of requirements approved (0-100)"),
    "tender.eligibility_missing": FieldDef(
        "number", TR, "Eligibility criteria not met by the profile"
    ),
    "tender.readiness_score": FieldDef("number", TR, "Readiness score 0-100"),
    "company.name": FieldDef("text", ALL, "Company legal name"),
    "company.certifications": FieldDef("list", ALL, "Certification names from the profile"),
    "company.latest_turnover_inr": FieldDef("number", ALL, "Most recent annual turnover in rupees"),
    "company.avg_turnover_inr": FieldDef("number", ALL, "Average turnover of the last 3 years"),
    "company.years_in_business": FieldDef("number", ALL, "Years since establishment"),
    "company.has_gstin": FieldDef("boolean", ALL, "GSTIN is filled in"),
}


def field_catalog() -> list[dict[str, Any]]:
    return [
        {"name": name, "type": f.type, "scopes": list(f.scopes), "description": f.description}
        for name, f in FIELDS.items()
    ]


# ---------------------------------------------------------------- value extraction

_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|per\s*cent|percent)", re.I)
_AMOUNT = re.compile(
    r"(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)\s*(?:\([A-Za-z ]+\)\s*)?(lakhs?|lacs?|crores?|cr\b)?",
    re.I,
)
_PERIOD = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:\([A-Za-z ]+\)\s*)?(calendar\s+|working\s+)?(days?|weeks?|months?|years?)\b",
    re.I,
)


def max_percent(text: str) -> float | None:
    values = [float(v) for v in _PERCENT.findall(text)]
    return max(values) if values else None


def max_amount_inr(text: str) -> float | None:
    values: list[float] = []
    for number, unit in _AMOUNT.findall(text):
        value = float(number.replace(",", ""))
        unit = unit.lower()
        if unit.startswith(("lakh", "lac")):
            value *= 1e5
        elif unit.startswith("cr"):
            value *= 1e7
        values.append(value)
    return max(values) if values else None


def max_days(text: str) -> float | None:
    factor = {"day": 1, "week": 7, "month": 30, "year": 365}
    values = [float(n) * factor[unit.lower().rstrip("s")] for n, _, unit in _PERIOD.findall(text)]
    return max(values) if values else None


# ---------------------------------------------------------------- evaluation


def _compare(actual: Any, op: str, expected: Any) -> bool:
    if op == "exists":
        return actual not in (None, "", [])
    if op == "not_exists":
        return actual in (None, "", [])
    if op == "is_true":
        return actual is True
    if op == "is_false":
        return actual is False or actual is None
    if actual is None:
        return op in ("neq", "not_contains", "not_contains_any", "not_in", "not_matches")
    if op in ("gt", "gte", "lt", "lte"):
        try:
            a, b = float(actual), float(expected)
        except (TypeError, ValueError):
            return False
        return {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[op]
    if op in ("eq", "neq"):
        same = (
            str(actual).strip().lower() == str(expected).strip().lower()
            if not isinstance(actual, bool)
            else actual == expected
        )
        return same if op == "eq" else not same
    haystack = (
        [str(x).lower() for x in actual] if isinstance(actual, list) else [str(actual).lower()]
    )
    joined = " | ".join(haystack)
    needles = [str(x).lower() for x in (expected if isinstance(expected, list) else [expected])]
    if op in ("contains", "not_contains"):
        hit = all(n in joined for n in needles)
        return hit if op == "contains" else not hit
    if op in ("contains_any", "not_contains_any"):
        hit = any(n in joined for n in needles)
        return hit if op == "contains_any" else not hit
    if op in ("in", "not_in"):
        hit = str(actual).lower() in needles
        return hit if op == "in" else not hit
    if op in ("matches", "not_matches"):
        hit = re.search(str(expected), joined, re.I) is not None
        return hit if op == "matches" else not hit
    return False


def evaluate(condition: Condition, context: dict[str, Any]) -> bool:
    if condition.all is not None:
        return all(evaluate(c, context) for c in condition.all)
    if condition.any is not None:
        return any(evaluate(c, context) for c in condition.any)
    if condition.not_ is not None:
        return not evaluate(condition.not_, context)
    assert condition.field is not None and condition.op is not None
    return _compare(context.get(condition.field), condition.op, condition.value)


def render_message(template: str, context: dict[str, Any], rule: RuleSpec) -> str:
    def value(match: re.Match[str]) -> str:
        found = context.get(match.group(1))
        if isinstance(found, float) and found.is_integer():
            return str(int(found))
        if isinstance(found, list):
            return ", ".join(str(x) for x in found)
        return "—" if found is None else str(found)

    text = template or rule.name
    return re.sub(r"\{([a-z_]+\.[a-z_]+)\}", value, text)


# ---------------------------------------------------------------- loading rules


@dataclass
class LoadedRule:
    spec: RuleSpec
    source: str  # "ui" or "file:<name>"
    db_id: int | None = None


@dataclass
class PolicyFile:
    name: str
    modified: str
    rules: int
    error: str | None


def parse_rules(payload: Any) -> tuple[list[RuleSpec], list[str]]:
    """Parse {rules: [...]} or [...] into RuleSpecs; invalid rules become error strings."""
    items = payload.get("rules", []) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return [], ["expected a list of rules or {rules: [...]}"]
    specs: list[RuleSpec] = []
    errors: list[str] = []
    for index, item in enumerate(items):
        try:
            specs.append(RuleSpec.model_validate(item))
        except ValidationError as exc:
            label = item.get("id") if isinstance(item, dict) else f"#{index + 1}"
            first = exc.errors()[0]
            where = ".".join(str(p) for p in first.get("loc", ()))
            errors.append(f"rule {label}: {where + ': ' if where else ''}{first.get('msg')}")
    return specs, errors


def load_file_rules(policy_dir: Path) -> tuple[list[LoadedRule], list[PolicyFile], list[str]]:
    rules: list[LoadedRule] = []
    files: list[PolicyFile] = []
    errors: list[str] = []
    if not policy_dir.is_dir():
        return rules, files, errors
    for path in sorted(policy_dir.iterdir()):
        if path.suffix.lower() not in (".json", ".yaml", ".yml"):
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
        try:
            raw = path.read_text(encoding="utf-8")
            payload = json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
        except (json.JSONDecodeError, yaml.YAMLError, OSError) as exc:
            message = f"{path.name}: cannot be read ({str(exc).splitlines()[0]})"
            files.append(PolicyFile(path.name, modified, 0, message))
            errors.append(message)
            continue
        specs, problems = parse_rules(payload or [])
        errors.extend(f"{path.name}: {p}" for p in problems)
        files.append(PolicyFile(path.name, modified, len(specs), "; ".join(problems) or None))
        rules.extend(LoadedRule(spec, f"file:{path.name}") for spec in specs)
    return rules, files, errors


def db_rule_spec(row: PolicyRule) -> RuleSpec:
    return RuleSpec.model_validate(
        {
            "id": row.rule_key,
            "name": row.name,
            "description": row.description,
            "scope": row.scope,
            "when": row.when,
            "flag_if": row.flag_if,
            "severity": row.severity,
            "message": row.message,
            "enabled": row.enabled,
        }
    )


def load_all_rules(
    session: Session, policy_dir: Path
) -> tuple[list[LoadedRule], list[PolicyFile], list[str]]:
    rules, files, errors = load_file_rules(policy_dir)
    for row in session.exec(select(PolicyRule).order_by(col(PolicyRule.id))).all():
        try:
            rules.append(LoadedRule(db_rule_spec(row), "ui", row.id))
        except ValidationError as exc:
            errors.append(f"rule {row.rule_key}: {exc.errors()[0].get('msg')}")
    return rules, files, errors


# ---------------------------------------------------------------- contexts


def _tender_context(
    session: Session, project: Project, rows: list[tuple[Requirement, Response | None]]
) -> dict[str, Any]:
    from app.services.profile import check_eligibility

    assert project.id is not None
    rules_row = session.exec(
        select(SubmissionRules).where(col(SubmissionRules.project_id) == project.id)
    ).first()
    rules = rules_row.rules if rules_row else {}
    deadline = project.deadline
    days = None
    if deadline is not None:
        deadline = deadline if deadline.tzinfo else deadline.replace(tzinfo=UTC)
        days = round((deadline - datetime.now(UTC)).total_seconds() / 86400, 1)
    qcbs = str(rules.get("qcbs_split") or "")
    company = session.get(Company, project.company_id)
    eligibility = check_eligibility(session, company, rules.get("eligibility", []))
    mandatory = [(q, r) for q, r in rows if q.type == "mandatory"]
    return {
        "tender.title": project.title,
        "tender.buyer": project.buyer,
        "tender.portal": rules.get("portal"),
        "tender.bid_system": rules.get("bid_system"),
        "tender.emd_inr": (rules.get("emd") or {}).get("amount_inr"),
        "tender.days_to_deadline": days,
        "tender.page_limit": (rules.get("format") or {}).get("page_limit"),
        "tender.validity_days": rules.get("validity_days"),
        "tender.technical_weight": float(qcbs.split(":")[0]) if ":" in qcbs else None,
        "tender.requirement_count": len(rows),
        "tender.mandatory_gaps": sum(
            1 for _, r in mandatory if r is None or r.status in ("gap", "pending")
        ),
        "tender.approved_percent": round(
            100 * sum(1 for _, r in rows if r and r.approved) / len(rows), 1
        )
        if rows
        else 0.0,
        "tender.eligibility_missing": sum(1 for e in eligibility if e["status"] == "missing"),
        "tender.readiness_score": project.readiness_score,
    }


def _company_context(company: Company | None) -> dict[str, Any]:
    if company is None:
        return {}
    turnover = [float(t.get("amount_inr") or 0) for t in company.turnover]
    recent = turnover[-3:]
    return {
        "company.name": company.legal_name,
        "company.certifications": [str(c.get("name", "")) for c in company.certifications],
        "company.latest_turnover_inr": turnover[-1] if turnover else None,
        "company.avg_turnover_inr": sum(recent) / len(recent) if recent else None,
        "company.years_in_business": datetime.now(UTC).year - company.year_established
        if company.year_established
        else None,
        "company.has_gstin": bool(company.gstin),
    }


def _requirement_context(
    req: Requirement, resp: Response | None, criteria: dict[int, str]
) -> dict[str, Any]:
    answer = (resp.answer or "") if resp else ""
    return {
        "requirement.code": req.req_code,
        "requirement.text": req.text,
        "requirement.section": req.section_path,
        "requirement.category": req.category,
        "requirement.type": req.type,
        "requirement.criterion": criteria.get(req.criterion_id or 0),
        "requirement.change": req.version_status,
        "requirement.max_percent": max_percent(req.text),
        "requirement.max_amount_inr": max_amount_inr(req.text),
        "requirement.max_days": max_days(req.text),
        "answer.text": answer or None,
        "answer.status": resp.status if resp else "pending",
        "answer.approved": bool(resp and resp.approved),
        "answer.has_answer": bool(answer),
        "answer.is_commitment": bool(
            resp and any(c.get("kind") == "rfp_clause" for c in resp.citations)
        ),
        "answer.word_count": len(answer.split()),
        "answer.citation_count": len(resp.citations) if resp else 0,
        "answer.review_score": resp.review_score if resp else None,
    }


# ---------------------------------------------------------------- audit


def _rows(session: Session, project_id: int) -> list[tuple[Requirement, Response | None]]:
    reqs = list(
        session.exec(
            select(Requirement)
            .where(
                col(Requirement.project_id) == project_id,
                col(Requirement.version_status) != "removed",
            )
            .order_by(col(Requirement.order))
        ).all()
    )
    responses = {
        r.requirement_id: r
        for r in session.exec(
            select(Response).where(col(Response.requirement_id).in_([q.id for q in reqs]))
        ).all()
    }
    return [(q, responses.get(q.id or 0)) for q in reqs]


def run_audit(session: Session, project: Project, policy_dir: Path) -> AuditRun:
    """Evaluate every enabled rule, mark findings not present in the previous run as new, save."""
    assert project.id is not None
    rules, _files, errors = load_all_rules(session, policy_dir)
    active = [r for r in rules if r.spec.enabled]
    rows = _rows(session, project.id)
    company = session.get(Company, project.company_id)
    criteria = {
        c.id: c.name
        for c in session.exec(
            select(EvaluationCriterion).where(col(EvaluationCriterion.project_id) == project.id)
        ).all()
        if c.id
    }
    base = {**_tender_context(session, project, rows), **_company_context(company)}
    findings: list[dict[str, Any]] = []

    def add(rule: LoadedRule, context: dict[str, Any], target: dict[str, Any] | None) -> None:
        key = f"{rule.source}|{rule.spec.id}|{target['requirement_id'] if target else 'project'}"
        findings.append(
            {
                "key": key,
                "rule_id": rule.spec.id,
                "rule_name": rule.spec.name,
                "source": rule.source,
                "scope": rule.spec.scope,
                "severity": rule.spec.severity,
                "message": render_message(rule.spec.message, context, rule.spec),
                "target": target,
            }
        )

    checks: Callable[[LoadedRule, dict[str, Any]], bool] = lambda rule, ctx: (  # noqa: E731
        (rule.spec.when is None or evaluate(rule.spec.when, ctx))
        and evaluate(rule.spec.flag_if, ctx)
    )
    for rule in active:
        try:
            if rule.spec.scope == "requirement":
                for req, resp in rows:
                    ctx = {**base, **_requirement_context(req, resp, criteria)}
                    if checks(rule, ctx):
                        add(rule, ctx, {"requirement_id": req.id, "req_code": req.req_code})
            elif checks(rule, base):
                add(rule, base, None)
        except Exception as exc:  # a broken rule must never break the audit
            logger.warning("Policy rule %s failed: %s", rule.spec.id, exc)
            errors.append(f"rule {rule.spec.id}: {exc}")

    previous = session.exec(
        select(AuditRun)
        .where(col(AuditRun.project_id) == project.id)
        .order_by(col(AuditRun.id).desc())
    ).first()
    previous_keys = {f["key"] for f in previous.findings} if previous else set()
    for finding in findings:
        finding["new"] = previous is not None and finding["key"] not in previous_keys
    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (not f["new"], order[f["severity"]], f["rule_name"]))
    current_keys = {f["key"] for f in findings}
    run = AuditRun(
        project_id=project.id,
        findings=findings,
        errors=errors,
        rules_evaluated=len(active),
        resolved=len(previous_keys - current_keys) if previous else 0,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def latest_audit(session: Session, project_id: int) -> AuditRun | None:
    return session.exec(
        select(AuditRun)
        .where(col(AuditRun.project_id) == project_id)
        .order_by(col(AuditRun.id).desc())
    ).first()
