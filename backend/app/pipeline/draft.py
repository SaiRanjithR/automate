"""Draft job: retrieve evidence, draft cited answers, verify citations, review each answer."""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.jobs.runner import JobContext, register
from app.llm.client import LLM, UsageMeter, get_llm
from app.models import (
    Company,
    EvaluationCriterion,
    OutlineSection,
    Project,
    Requirement,
    Response,
    WinTheme,
)
from app.models.tables import utcnow
from app.pipeline.retrieve import Evidence, KnowledgeIndex
from app.pipeline.review import review_answer
from app.pipeline.textutil import quote_found
from app.schemas.llm import DraftedResponse
from app.services import audit
from app.services.scoring import word_budget_for

logger = logging.getLogger(__name__)


@dataclass
class DraftContext:
    llm: LLM
    settings: Settings
    index: KnowledgeIndex
    company: dict[str, Any]
    win_themes: list[str]
    criteria: dict[int, EvaluationCriterion]
    budgets: dict[int, int]  # requirement_id -> word budget
    usage: UsageMeter


def company_summary(company: Company | None) -> dict[str, Any]:
    if company is None:
        return {}
    return {
        "legal_name": company.legal_name,
        "year_established": company.year_established,
        "certifications": [c.get("name") for c in company.certifications],
        "turnover": company.turnover,
    }


def _evidence_text(evidence: list[Evidence]) -> str:
    return "\n\n".join(
        f"[chunk_id {e.chunk_id}] ({e.filename}, page {e.page})\n{e.text}" for e in evidence
    )


_UNDERTAKING = re.compile(
    r"\b(submit|furnish|quote|sign(?:ed)?|abide|comply with (?:all |the )?(?:terms|conditions|provisions)|"
    r"accept (?:all |the )?(?:terms|conditions|rates|payment)|bank guarantee|performance security|"
    r"valid(?:ity)? (?:for|of)|remain valid|deposit|emd|earnest money|declaration|undertaking|affidavit|"
    r"stamp|notar|indemnif|penalt|liquidated damages|confidential|non-disclosure|jurisdiction|arbitration|"
    r"terminat|no change in the rates|rates finalized|detailed (?:project )?plan|implementation approach|"
    r"documentary proof|bear (?:all )?(?:the )?cost)",
    re.I,
)
UNDERTAKING_NOTE = "Commitment, not evidence: no document proves this; confirm your company accepts it before approving."


def is_undertaking(text: str) -> bool:
    """Contractual or procedural commitments (accept terms, furnish documents, pay penalties ...)."""
    return bool(_UNDERTAKING.search(text))


def undertaking_draft(req: Requirement) -> dict[str, Any]:
    """An honest commitment answer that cites the RFP clause itself, never a capability claim."""
    where = f"clause {req.section_path.split(' ')[0]}" if req.section_path else "the RFP"
    page = f", page {req.page}" if req.page else ""
    return {
        "answer": f"We confirm that we accept and will comply with this requirement as stated in {where}{page} of the RFP.",
        "status": "fully_compliant",
        "confidence": 0.6,
        "citations": [
            {
                "chunk_id": 0,
                "doc_id": 0,
                "filename": "RFP (commitment to the tender clause)",
                "page": req.page or 0,
                "quote": req.source_quote,
                "kind": "rfp_clause",
            }
        ],
        "gap_reason": None,
        "review_score": 95,
        "review_issues": [{"type": "undertaking", "message": UNDERTAKING_NOTE, "severity": "low"}],
        "model": "rules",
        "prompt_version": "undertaking@1",
    }


def draft_one(ctx: DraftContext, req: Requirement, hint: str | None = None) -> dict[str, Any]:
    """Draft from evidence; when there is none and the clause is a commitment, draft an undertaking."""
    fields = _draft_from_evidence(ctx, req, hint)
    if fields["status"] == "gap" and is_undertaking(req.text):
        return undertaking_draft(req)
    return fields


def _draft_from_evidence(
    ctx: DraftContext, req: Requirement, hint: str | None = None
) -> dict[str, Any]:
    """Return the new response fields for one requirement (no DB writes)."""
    query = req.text if not hint else f"{req.text}\n{hint}"
    evidence = ctx.index.search(query)
    top = evidence[0].score if evidence else 0.0
    if not evidence or top < ctx.index.min_score:
        return {
            "answer": None,
            "status": "gap",
            "confidence": round(top, 2),
            "citations": [],
            "gap_reason": "No relevant evidence found in your knowledge base.",
            "review_score": None,
            "review_issues": [],
            "model": ctx.llm.name,
            "prompt_version": "retrieval-floor",
        }
    criterion = ctx.criteria.get(req.criterion_id) if req.criterion_id else None
    criterion_text = (
        f"{criterion.name} ({criterion.max_marks:g} marks)"
        if criterion and criterion.max_marks
        else (criterion.name if criterion else "Not linked to a scoring criterion")
    )
    budget = ctx.budgets.get(req.id or 0, 150)
    instruction = f"\nReviewer hint: {hint}" if hint else ""
    result = ctx.llm.complete(
        "draft_response",
        {
            "req_code": req.req_code,
            "req_type": req.type,
            "requirement": req.text + instruction,
            "criterion": criterion_text,
            "win_themes": "; ".join(ctx.win_themes) or "None provided",
            "company": ctx.company,
            "evidence": _evidence_text(evidence),
            "evidence_list": [
                {"chunk_id": e.chunk_id, "text": e.text, "score": e.score} for e in evidence
            ],
            "word_budget": budget,
        },
        DraftedResponse,
        ctx.usage,
    )
    drafted = result.value
    by_id = {e.chunk_id: e for e in evidence}
    citations: list[dict[str, Any]] = []
    for citation in drafted.citations:
        source = by_id.get(citation.chunk_id)
        if source and quote_found(citation.quote, source.text):
            citations.append(
                {
                    "chunk_id": source.chunk_id,
                    "doc_id": source.doc_id,
                    "filename": source.filename,
                    "page": source.page,
                    "quote": citation.quote,
                    "outcome": source.outcome,
                }
            )
    status = drafted.status
    answer: str | None = drafted.answer.strip() or None
    gap_reason = drafted.gap_reason
    if status != "gap" and not citations:
        status, answer = "gap", None
        gap_reason = "The draft could not be tied to verifiable evidence, so it was withheld."
    review_score: int | None = None
    issues: list[dict[str, Any]] = []
    if status != "gap" and answer:
        review_score, issues = review_answer(
            ctx.llm,
            requirement=req.text,
            mandatory=req.type == "mandatory",
            answer=answer,
            citations=citations,
            word_budget=budget,
            usage=ctx.usage,
        )
    return {
        "answer": answer,
        "status": status,
        "confidence": round(float(drafted.confidence), 2),
        "citations": citations,
        "gap_reason": gap_reason,
        "review_score": review_score,
        "review_issues": issues,
        "model": result.model,
        "prompt_version": result.prompt_version,
    }


def build_context(
    session: Session, settings: Settings, project: Project, usage: UsageMeter
) -> DraftContext:
    assert project.id is not None
    company = session.get(Company, project.company_id)
    themes = [
        t.text
        for t in session.exec(
            select(WinTheme)
            .where(col(WinTheme.project_id) == project.id)
            .order_by(col(WinTheme.order))
        ).all()
    ]
    criteria = {
        c.id: c
        for c in session.exec(
            select(EvaluationCriterion).where(col(EvaluationCriterion.project_id) == project.id)
        ).all()
        if c.id is not None
    }
    sections = {
        s.id: s
        for s in session.exec(
            select(OutlineSection).where(col(OutlineSection.project_id) == project.id)
        ).all()
    }
    requirements = list(
        session.exec(select(Requirement).where(col(Requirement.project_id) == project.id)).all()
    )
    per_section: dict[int, int] = {}
    for r in requirements:
        if r.outline_section_id:
            per_section[r.outline_section_id] = per_section.get(r.outline_section_id, 0) + 1
    budgets: dict[int, int] = {}
    for r in requirements:
        section = sections.get(r.outline_section_id) if r.outline_section_id else None
        budgets[r.id or 0] = word_budget_for(
            section.page_budget if section else None, per_section.get(r.outline_section_id or 0, 0)
        )
    return DraftContext(
        llm=get_llm(settings),
        settings=settings,
        index=KnowledgeIndex(session, settings, project.company_id),
        company=company_summary(company),
        win_themes=themes,
        criteria=criteria,
        budgets=budgets,
        usage=usage,
    )


def save_draft(engine: Engine, req: Requirement, fields: dict[str, Any], actor: str) -> None:
    with Session(engine) as session:
        response = session.exec(
            select(Response).where(col(Response.requirement_id) == req.id)
        ).first()
        if response is None:
            assert req.id is not None
            response = Response(requirement_id=req.id)
        before = {"answer": response.answer, "status": response.status}
        for key, value in fields.items():
            setattr(response, key, value)
        response.approved = False
        response.approval_override_reason = None
        response.edited_by_user = False
        response.updated_at = utcnow()
        session.add(response)
        session.flush()
        assert response.id is not None
        audit.record(
            session,
            entity="response",
            entity_id=response.id,
            action="ai_draft",
            actor=actor,
            project_id=req.project_id,
            before=before,
            after={"answer": response.answer, "status": response.status},
            prompt_version=fields.get("prompt_version"),
        )
        session.commit()


@register("draft")
def draft_job(ctx: JobContext) -> None:
    project_id = int(ctx.params["project_id"])
    only_ids: list[int] | None = ctx.params.get("requirement_ids")
    hint: str | None = ctx.params.get("hint")
    include_approved = bool(ctx.params.get("include_approved", False))
    with Session(ctx.engine) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")
        usage = UsageMeter(ctx.settings.llm_max_tokens_per_project, project.tokens_used)
        dctx = build_context(session, ctx.settings, project, usage)
        query = select(Requirement).where(
            col(Requirement.project_id) == project_id, col(Requirement.version_status) != "removed"
        )
        if only_ids:
            query = query.where(col(Requirement.id).in_(only_ids))
        requirements = list(session.exec(query.order_by(col(Requirement.order))).all())
        approved = {
            r.requirement_id
            for r in session.exec(select(Response).where(col(Response.approved) == True)).all()  # noqa: E712
        }
    if not only_ids and not include_approved:
        requirements = [r for r in requirements if r.id not in approved]
    if dctx.index.empty:
        ctx.progress("drafting", 0, "Knowledge base is empty: every row will be a gap")
    total = len(requirements)
    done = {"n": 0, "gaps": 0}
    actor = f"model:{dctx.llm.name}"

    def work(req: Requirement) -> None:
        fields = draft_one(dctx, req, hint)
        save_draft(ctx.engine, req, fields, actor)
        done["n"] += 1
        if fields["status"] == "gap":
            done["gaps"] += 1
        ctx.progress(
            "drafting",
            round(100 * done["n"] / max(total, 1)),
            f"Drafted {done['n']} of {total}",
            drafted=done["n"],
            gaps=done["gaps"],
            total=total,
        )

    ctx.progress("drafting", 1, f"Drafting {total} answers", total=total, drafted=0, gaps=0)
    with ThreadPoolExecutor(max_workers=ctx.settings.llm_max_concurrency) as pool:
        list(pool.map(work, requirements))
    with Session(ctx.engine) as session:
        project = session.get(Project, project_id)
        if project is not None:
            project.tokens_used = usage.used
            session.add(project)
            session.commit()
