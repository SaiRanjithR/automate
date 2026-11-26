from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlmodel import Session, col, select

from app.api.projects import get_project, runner_of
from app.core.deps import CurrentUser, SessionDep, SettingsDep
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.models import AnswerLibrary, AuditEvent, EvaluationCriterion, Project, Requirement
from app.models import Response as ResponseRow
from app.models.tables import utcnow
from app.pipeline.embed import get_embedder, to_bytes
from app.pipeline.extras import word_diff
from app.schemas.api import (
    AuditOut,
    JobStarted,
    RedraftIn,
    RequirementList,
    RequirementOut,
    RequirementPatch,
    ResponseOut,
    ResponsePatch,
    ReviewIssue,
)
from app.services import audit

router = APIRouter(tags=["requirements"])


def response_out(r: ResponseRow | None) -> ResponseOut | None:
    if r is None or r.id is None:
        return None
    return ResponseOut(
        id=r.id,
        answer=r.answer,
        status=r.status,
        confidence=r.confidence,
        citations=r.citations,
        gap_reason=r.gap_reason,
        approved=r.approved,
        approval_override_reason=r.approval_override_reason,
        edited_by_user=r.edited_by_user,
        needs_review=r.needs_review,
        review_score=r.review_score,
        review_issues=[ReviewIssue.model_validate(i) for i in r.review_issues],
        model=r.model,
        updated_at=r.updated_at,
    )


def requirement_out(
    req: Requirement, resp: ResponseRow | None, criteria: dict[int, str]
) -> RequirementOut:
    assert req.id is not None
    return RequirementOut(
        id=req.id,
        req_code=req.req_code,
        text=req.text,
        section_path=req.section_path,
        page=req.page,
        type=req.type,
        keyword=req.keyword,
        category=req.category,
        source_quote=req.source_quote,
        criterion_id=req.criterion_id,
        criterion_name=criteria.get(req.criterion_id) if req.criterion_id else None,
        outline_section_id=req.outline_section_id,
        version_status=req.version_status,
        previous_text=req.previous_text,
        rfp_file_id=req.rfp_file_id,
        response=response_out(resp),
    )


def _criteria(session: Session, project_id: int) -> dict[int, str]:
    return {
        c.id: c.name
        for c in session.exec(
            select(EvaluationCriterion).where(col(EvaluationCriterion.project_id) == project_id)
        ).all()
        if c.id
    }


@router.get("/projects/{project_id}/requirements", response_model=RequirementList)
def list_requirements(
    project_id: int,
    _: CurrentUser,
    session: SessionDep,
    status: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    mandatory: Annotated[bool | None, Query()] = None,
    criterion_id: Annotated[int | None, Query()] = None,
    has_issues: Annotated[bool | None, Query()] = None,
    version_status: Annotated[str | None, Query()] = None,
    include_removed: Annotated[bool, Query()] = False,
    q: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RequirementList:
    get_project(session, project_id)
    query = (
        select(Requirement, ResponseRow)
        .join(ResponseRow, col(ResponseRow.requirement_id) == col(Requirement.id), isouter=True)
        .where(col(Requirement.project_id) == project_id)
        .order_by(col(Requirement.order))
    )
    rows = list(session.exec(query).all())
    if not include_removed and "removed" not in (version_status or ""):
        rows = [(q_, r) for q_, r in rows if q_.version_status != "removed"]

    def count(pred: Callable[[Requirement, ResponseRow | None], bool]) -> int:
        return len([1 for req_, resp_ in rows if pred(req_, resp_)])

    summary: dict[str, int] = {
        "total": len(rows),
        "fully_compliant": count(lambda _q, r: r is not None and r.status == "fully_compliant"),
        "partially_compliant": count(
            lambda _q, r: r is not None and r.status == "partially_compliant"
        ),
        "compliant_with_customisation": count(
            lambda _q, r: r is not None and r.status == "compliant_with_customisation"
        ),
        "non_compliant": count(lambda _q, r: r is not None and r.status == "non_compliant"),
        "gap": count(lambda _q, r: r is not None and r.status == "gap"),
        "pending": count(lambda _q, r: r is None or r.status == "pending"),
        "approved": count(lambda _q, r: r is not None and r.approved),
        "with_issues": count(
            lambda _q, r: (
                r is not None and any(i.get("severity") == "high" for i in r.review_issues)
            )
        ),
        "changed": count(lambda q_, _r: q_.version_status in ("modified", "added")),
    }
    if status:
        statuses = set(status.split(","))
        rows = [
            (q_, r)
            for q_, r in rows
            if (r.status if r else "pending") in statuses
            or ("approved" in statuses and r and r.approved)
        ]
    if category:
        rows = [(q_, r) for q_, r in rows if q_.category == category]
    if mandatory is not None:
        rows = [(q_, r) for q_, r in rows if (q_.type == "mandatory") == mandatory]
    if criterion_id is not None:
        rows = [(q_, r) for q_, r in rows if q_.criterion_id == criterion_id]
    if has_issues:
        rows = [(q_, r) for q_, r in rows if r and r.review_issues]
    if version_status:
        rows = [(q_, r) for q_, r in rows if q_.version_status in set(version_status.split(","))]
    if q:
        needle = q.lower()
        rows = [
            (q_, r)
            for q_, r in rows
            if needle in q_.text.lower()
            or needle in q_.req_code.lower()
            or (r and needle in (r.answer or "").lower())
        ]
    criteria = _criteria(session, project_id)
    page = rows[offset : offset + limit]
    return RequirementList(
        items=[requirement_out(q_, r, criteria) for q_, r in page], total=len(rows), summary=summary
    )


def _load(session: Session, requirement_id: int) -> tuple[Requirement, ResponseRow]:
    req = session.get(Requirement, requirement_id)
    if req is None:
        raise NotFoundError(f"Requirement {requirement_id} not found")
    resp = session.exec(
        select(ResponseRow).where(col(ResponseRow.requirement_id) == requirement_id)
    ).first()
    if resp is None:
        resp = ResponseRow(requirement_id=requirement_id)
        session.add(resp)
        session.flush()
    return req, resp


@router.patch("/requirements/{requirement_id}", response_model=RequirementOut)
def patch_requirement(
    requirement_id: int, body: RequirementPatch, user: CurrentUser, session: SessionDep
) -> RequirementOut:
    req, resp = _load(session, requirement_id)
    before = {"text": req.text, "type": req.type, "criterion_id": req.criterion_id}
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(req, key, value)
    req.updated_at = utcnow()
    session.add(req)
    audit.record(
        session,
        entity="requirement",
        entity_id=requirement_id,
        action="edit",
        actor=f"user:{user.id}",
        project_id=req.project_id,
        before=before,
        after=body.model_dump(exclude_unset=True),
    )
    session.commit()
    return requirement_out(req, resp, _criteria(session, req.project_id))


@router.patch("/responses/{response_id}", response_model=RequirementOut)
def patch_response(
    response_id: int,
    body: ResponsePatch,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
) -> RequirementOut:
    resp = session.get(ResponseRow, response_id)
    if resp is None:
        raise NotFoundError(f"Response {response_id} not found")
    req = session.get(Requirement, resp.requirement_id)
    assert req is not None
    before = {"answer": resp.answer, "status": resp.status, "approved": resp.approved}
    data = body.model_dump(exclude_unset=True)
    if "answer" in data and data["answer"] != resp.answer:
        resp.answer = (data["answer"] or "").strip() or None
        resp.edited_by_user = True
        resp.approved = False
    if data.get("status"):
        resp.status = data["status"]
        if resp.status != "gap" and resp.answer is None and not data.get("answer"):
            raise ValidationFailedError("Write an answer before changing the status from gap")
    action = "edit"
    if data.get("approved") is True:
        high = [i for i in resp.review_issues if i.get("severity") == "high"]
        reason = (data.get("override_reason") or "").strip()
        if high and not reason:
            raise ConflictError(
                "This answer has high-severity review issues; give an override reason to approve it"
            )
        if not resp.answer and resp.status != "non_compliant":
            raise ConflictError(
                "Gap rows cannot be approved; write an answer or mark the row non-compliant"
            )
        resp.approved = True
        resp.needs_review = False
        resp.approval_override_reason = reason or None
        action = "approve"
        project = session.get(Project, req.project_id)
        if project is not None and resp.answer:
            existing = session.exec(
                select(AnswerLibrary).where(col(AnswerLibrary.source_requirement_id) == req.id)
            ).first()
            vector = get_embedder(settings).embed([req.text])[0]
            entry = existing or AnswerLibrary(
                company_id=project.company_id,
                requirement_text=req.text,
                answer=resp.answer,
                source_project_id=project.id,
                source_requirement_id=req.id,
                outcome=project.outcome,
                embedding=to_bytes(vector),
            )
            entry.answer = resp.answer
            entry.embedding = to_bytes(vector)
            session.add(entry)
    elif data.get("approved") is False:
        resp.approved = False
        action = "unapprove"
    resp.updated_at = utcnow()
    session.add(resp)
    audit.record(
        session,
        entity="response",
        entity_id=response_id,
        action=action,
        actor=f"user:{user.id}",
        project_id=req.project_id,
        before=before,
        after={"answer": resp.answer, "status": resp.status, "approved": resp.approved},
    )
    session.commit()
    return requirement_out(req, resp, _criteria(session, req.project_id))


@router.post("/responses/{response_id}/redraft", response_model=JobStarted, status_code=202)
def redraft(
    response_id: int, body: RedraftIn, request: Request, _: CurrentUser, session: SessionDep
) -> JobStarted:
    resp = session.get(ResponseRow, response_id)
    if resp is None:
        raise NotFoundError(f"Response {response_id} not found")
    req = session.get(Requirement, resp.requirement_id)
    assert req is not None and req.id is not None
    job = runner_of(request).submit(
        "draft",
        {
            "project_id": req.project_id,
            "requirement_ids": [req.id],
            "hint": body.hint,
            "include_approved": True,
        },
        project_id=req.project_id,
    )
    assert job.id is not None
    return JobStarted(job_id=job.id, project_id=req.project_id)


@router.get("/responses/{response_id}/history", response_model=list[AuditOut])
def history(response_id: int, _: CurrentUser, session: SessionDep) -> list[AuditOut]:
    events = session.exec(
        select(AuditEvent)
        .where(col(AuditEvent.entity) == "response", col(AuditEvent.entity_id) == response_id)
        .order_by(col(AuditEvent.id).desc())
    ).all()
    return [
        AuditOut(
            id=e.id or 0, action=e.action, actor=e.actor, before=e.before, after=e.after, at=e.at
        )
        for e in events
    ]


@router.get("/requirements/{requirement_id}/diff")
def requirement_diff(
    requirement_id: int, _: CurrentUser, session: SessionDep
) -> list[dict[str, str]]:
    req = session.get(Requirement, requirement_id)
    if req is None:
        raise NotFoundError(f"Requirement {requirement_id} not found")
    if not req.previous_text:
        return [{"op": "equal", "text": req.text}]
    return word_diff(req.previous_text, req.text)
