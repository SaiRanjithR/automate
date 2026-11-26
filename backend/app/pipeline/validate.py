"""Pre-submission validator (F10) and go / no-go (F12)."""

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, select

from app.models import Company, FactConflict, Project, Requirement, Response, SubmissionRules
from app.services.profile import check_eligibility, unfilled_fields
from app.services.scoring import GoNoGoInput, go_no_go, readiness_score

WORDS_PER_PAGE = 450
FIXED_PAGES = 3  # cover, contents, company profile


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


def estimate_pages(rows: list[tuple[Requirement, Response | None]]) -> float:
    words = sum(
        len((resp.answer or "").split()) + len(req.text.split()) + 6
        for req, resp in rows
        if resp and resp.answer
    )
    return round(FIXED_PAGES + words / WORDS_PER_PAGE, 1)


def validate_project(session: Session, project: Project) -> dict[str, Any]:
    assert project.id is not None
    rows = _rows(session, project.id)
    rules_row = session.exec(
        select(SubmissionRules).where(col(SubmissionRules.project_id) == project.id)
    ).first()
    rules: dict[str, Any] = rules_row.rules if rules_row else {}
    company = session.get(Company, project.company_id)
    blockers: list[dict[str, Any]] = []
    checks = 0

    mandatory = [(q, r) for q, r in rows if q.type == "mandatory"]
    gaps = [(q, r) for q, r in mandatory if r is None or r.status == "gap"]
    unapproved = [(q, r) for q, r in mandatory if r is None or not r.approved]
    needs_review = [(q, r) for q, r in rows if r is not None and r.needs_review]
    checks += 4
    if gaps:
        blockers.append(
            {
                "code": "mandatory_gaps",
                "severity": "high",
                "message": f"{len(gaps)} mandatory requirement(s) have no answer (gap).",
                "requirement_ids": [q.id for q, _ in gaps],
            }
        )
    if unapproved:
        blockers.append(
            {
                "code": "unapproved",
                "severity": "high",
                "message": f"{len(unapproved)} mandatory answer(s) are not approved yet.",
                "requirement_ids": [q.id for q, _ in unapproved],
            }
        )
    if needs_review:
        blockers.append(
            {
                "code": "needs_review",
                "severity": "medium",
                "message": f"{len(needs_review)} answer(s) changed by an addendum need review.",
                "requirement_ids": [q.id for q, _ in needs_review],
            }
        )

    for form in rules.get("forms", []):
        checks += 1
        missing = unfilled_fields(form, company, project)
        if missing:
            blockers.append(
                {
                    "code": "form_fields",
                    "severity": "medium",
                    "message": f"{form.get('code')} ({form.get('title')}): fill {', '.join(missing)}.",
                }
            )

    eligibility = check_eligibility(session, company, rules.get("eligibility", []))
    for item in eligibility:
        checks += 1
        if item["status"] == "missing":
            blockers.append(
                {
                    "code": "eligibility",
                    "severity": "high",
                    "message": f"Eligibility: {item['criterion']} — {item['reason']}",
                }
            )

    page_limit = (rules.get("format") or {}).get("page_limit")
    pages = estimate_pages(rows)
    checks += 1
    if page_limit and pages > page_limit:
        blockers.append(
            {
                "code": "page_limit",
                "severity": "high",
                "message": f"Technical proposal is about {pages} pages; the limit is {page_limit}.",
            }
        )

    checks += 1
    if project.deadline:
        deadline = (
            project.deadline if project.deadline.tzinfo else project.deadline.replace(tzinfo=UTC)
        )
        if deadline < datetime.now(UTC):
            blockers.append(
                {
                    "code": "deadline",
                    "severity": "high",
                    "message": "The submission deadline has passed.",
                }
            )

    conflicts = list(
        session.exec(
            select(FactConflict).where(
                col(FactConflict.project_id) == project.id, col(FactConflict.resolved).is_(False)
            )
        ).all()
    )
    checks += 1
    if conflicts:
        blockers.append(
            {
                "code": "conflicts",
                "severity": "medium",
                "message": f"{len(conflicts)} conflicting fact(s) across answers: "
                + ", ".join(c.key for c in conflicts),
            }
        )

    from app.services.policy import latest_audit

    audit = latest_audit(session, project.id)
    checks += 1
    if audit is not None:
        high = [f for f in audit.findings if f["severity"] == "high"]
        if high:
            blockers.append(
                {
                    "code": "policy",
                    "severity": "high",
                    "message": f"{len(high)} high-severity policy exception(s) in the last audit: "
                    + "; ".join(sorted({f["rule_name"] for f in high}))[:300],
                }
            )

    company_missing = [
        f
        for f in ("legal_name", "signatory_name", "address")
        if company is None or not getattr(company, f)
    ]
    checks += 1
    if company_missing:
        blockers.append(
            {
                "code": "profile",
                "severity": "high",
                "message": "Company profile incomplete: " + ", ".join(company_missing),
            }
        )

    approved_ratio = (len(mandatory) - len(unapproved)) / len(mandatory) if mandatory else 1.0
    gap_ratio = len(gaps) / len(mandatory) if mandatory else 0.0
    score = readiness_score(blockers, checks, approved_ratio, gap_ratio)
    project.readiness_score = score
    session.add(project)
    session.commit()
    return {
        "readiness_score": score,
        "blockers": blockers,
        "estimated_pages": pages,
        "page_limit": page_limit,
        "eligibility": eligibility,
        "counts": {
            "requirements": len(rows),
            "mandatory": len(mandatory),
            "approved": sum(1 for _, r in rows if r and r.approved),
            "gaps": sum(1 for _, r in rows if r is None or r.status == "gap"),
            "drafted": sum(1 for _, r in rows if r and r.answer),
        },
    }


def compute_go_no_go(session: Session, project: Project) -> dict[str, Any]:
    assert project.id is not None
    rows = _rows(session, project.id)
    rules_row = session.exec(
        select(SubmissionRules).where(col(SubmissionRules.project_id) == project.id)
    ).first()
    company = session.get(Company, project.company_id)
    eligibility = check_eligibility(
        session, company, (rules_row.rules if rules_row else {}).get("eligibility", [])
    )
    mandatory = [(q, r) for q, r in rows if q.type == "mandatory"]
    days: float | None = None
    if project.deadline:
        deadline = (
            project.deadline if project.deadline.tzinfo else project.deadline.replace(tzinfo=UTC)
        )
        days = (deadline - datetime.now(UTC)).total_seconds() / 86400
    result = go_no_go(
        GoNoGoInput(
            mandatory_total=len(mandatory),
            mandatory_gaps=sum(
                1 for _, r in mandatory if r is None or r.status in ("gap", "pending")
            ),
            eligibility_failed=[e["criterion"] for e in eligibility if e["status"] == "missing"],
            days_to_deadline=days,
            gap_rows=sum(1 for _, r in rows if r is None or r.status in ("gap", "pending")),
            drafted_rows=sum(1 for _, r in rows if r and r.answer),
            competition_rating=project.competition_rating,
        )
    )
    result["drafted"] = any(r and r.status != "pending" for _, r in rows)
    project.go_no_go = result
    session.add(project)
    session.commit()
    return result
