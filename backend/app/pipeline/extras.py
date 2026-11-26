"""P1 stages: proposal outline, consistency checker, addendum diff."""

import difflib
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlmodel import Session, col, delete, select

from app.jobs.runner import JobContext, register
from app.llm.client import UsageMeter, get_llm
from app.models import (
    EvaluationCriterion,
    FactConflict,
    OutlineSection,
    Project,
    Requirement,
    Response,
    RfpFile,
    RfpPage,
    SubmissionRules,
)
from app.pipeline.analyse import (
    assign_codes,
    classify_chunks,
    extract_from_chunks,
    link_criteria,
    parse_deadline,
    parse_rfp_file,
)
from app.pipeline.textutil import normalize
from app.schemas.llm import FactList
from app.services import audit
from app.services.scoring import page_budgets

TECHNICAL_EXCLUDE = re.compile(r"presentation|demo|financial|price|commercial", re.I)

# ---------------------------------------------------------------- outline (F19)


def generate_outline(session: Session, project: Project) -> list[OutlineSection]:
    assert project.id is not None
    for req in session.exec(
        select(Requirement).where(col(Requirement.project_id) == project.id)
    ).all():
        req.outline_section_id = None
        session.add(req)
    session.flush()
    session.exec(delete(OutlineSection).where(col(OutlineSection.project_id) == project.id))
    session.flush()
    rules_row = session.exec(
        select(SubmissionRules).where(col(SubmissionRules.project_id) == project.id)
    ).first()
    page_limit = float(
        ((rules_row.rules if rules_row else {}).get("format") or {}).get("page_limit") or 30
    )
    criteria = [
        c
        for c in session.exec(
            select(EvaluationCriterion)
            .where(col(EvaluationCriterion.project_id) == project.id)
            .order_by(col(EvaluationCriterion.id))
        ).all()
        if not TECHNICAL_EXCLUDE.search(c.name)
    ]
    titles = (
        ["Executive Summary", "Company Profile"]
        + [c.name for c in criteria]
        + ["General Compliance"]
    )
    marks = [5.0, 5.0] + [float(c.max_marks or 10) for c in criteria] + [5.0]
    budgets = page_budgets(marks, page_limit)
    sections: list[OutlineSection] = []
    for order, (title, budget) in enumerate(zip(titles, budgets, strict=True)):
        crit = criteria[order - 2] if 2 <= order < 2 + len(criteria) else None
        section = OutlineSection(
            project_id=project.id,
            title=title,
            order=order,
            page_budget=budget,
            criterion_id=crit.id if crit else None,
        )
        session.add(section)
        sections.append(section)
    session.flush()
    by_criterion = {s.criterion_id: s for s in sections if s.criterion_id}
    general = sections[-1]
    for req in session.exec(
        select(Requirement).where(col(Requirement.project_id) == project.id)
    ).all():
        target = by_criterion.get(req.criterion_id) if req.criterion_id else None
        req.outline_section_id = (target or general).id
        session.add(req)
    session.commit()
    return sections


# ---------------------------------------------------------------- consistency (F21)


def run_consistency(session: Session, project: Project, settings: Any) -> list[FactConflict]:
    assert project.id is not None
    llm = get_llm(settings)
    usage = UsageMeter(settings.llm_max_tokens_per_project, project.tokens_used)
    session.exec(delete(FactConflict).where(col(FactConflict.project_id) == project.id))
    rows = session.exec(
        select(Requirement, Response)
        .join(Response, col(Response.requirement_id) == col(Requirement.id))
        .where(col(Requirement.project_id) == project.id, col(Response.answer).is_not(None))
    ).all()
    values: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for req, resp in rows:
        facts = llm.complete("extract_facts", {"answer": resp.answer or ""}, FactList, usage).value
        for fact in facts.facts:
            value = normalize(fact.value).lower()
            values[fact.key][value].append({"requirement_id": req.id, "req_code": req.req_code})
    conflicts: list[FactConflict] = []
    for key, by_value in values.items():
        if key in ("certifications",) or len(by_value) < 2:
            continue
        conflict = FactConflict(
            project_id=project.id,
            key=key,
            values=[{"value": v, "rows": refs} for v, refs in by_value.items()],
        )
        session.add(conflict)
        conflicts.append(conflict)
    project.tokens_used = usage.used
    session.add(project)
    session.commit()
    return conflicts


# ---------------------------------------------------------------- addendum diff (F11)

_DELETED = re.compile(
    r"(?:clause|section|para(?:graph)?)\s+(\d+(?:\.\d+)+)[^.\n]{0,60}?\b(?:is|stands|shall be|has been)\s+(?:deleted|withdrawn|removed)",
    re.I,
)
_AMENDED = re.compile(
    r"(?:clause|section|para(?:graph)?)\s+(\d+(?:\.\d+)+)\s+(?:is|stands|shall be|has been)\s+(?:amended|modified|substituted|replaced|revised)",
    re.I,
)
_ADDED = re.compile(
    r"new\s+(?:clause|section|para(?:graph)?)\s+(\d+(?:\.\d+)+)\s+(?:is|has been|shall be)\s+(?:added|inserted|included)",
    re.I,
)
_PREFIX = re.compile(
    r"^.*?(?:amended to read|substituted by|replaced by|is added|is inserted|as follows)\s*[:\-]\s*",
    re.I,
)
MODIFIED_THRESHOLD = 0.8


def _strip_amendment_prefix(text: str) -> str:
    stripped = _PREFIX.sub("", text).strip()
    return stripped[0].upper() + stripped[1:] if stripped else text


def ratio(a: str, b: str) -> float:
    from rapidfuzz import fuzz

    return fuzz.ratio(normalize(a).lower(), normalize(b).lower()) / 100.0


def word_diff(old: str, new: str) -> list[dict[str, str]]:
    a, b = old.split(), new.split()
    out: list[dict[str, str]] = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b).get_opcodes():
        if op == "equal":
            out.append({"op": "equal", "text": " ".join(a[i1:i2])})
        if op in ("delete", "replace"):
            out.append({"op": "delete", "text": " ".join(a[i1:i2])})
        if op in ("insert", "replace"):
            out.append({"op": "insert", "text": " ".join(b[j1:j2])})
    return out


@register("addendum")
def addendum_job(ctx: JobContext) -> None:
    project_id = int(ctx.params["project_id"])
    file_id = int(ctx.params["rfp_file_id"])
    settings = ctx.settings
    llm = get_llm(settings)
    with Session(ctx.engine) as session:
        project = session.get(Project, project_id)
        rfp_file = session.get(RfpFile, file_id)
        if project is None or rfp_file is None:
            raise ValueError("Project or addendum file not found")
        usage = UsageMeter(settings.llm_max_tokens_per_project, project.tokens_used)
        ctx.progress("parsing", 10, f"Parsing {rfp_file.filename}")
        chunks = parse_rfp_file(session, settings, rfp_file)
        for chunk in chunks:
            chunk.category = "scope"  # every addendum section may change requirements
        page_texts = {
            p.page: p.text
            for p in session.exec(select(RfpPage).where(col(RfpPage.rfp_file_id) == file_id)).all()
        }
        full_text = "\n".join(page_texts[k] for k in sorted(page_texts))
        ctx.progress("matching", 40, "Matching changes to requirements")
        items = extract_from_chunks(llm, settings, chunks, page_texts, usage)
        existing = list(
            session.exec(
                select(Requirement).where(
                    col(Requirement.project_id) == project_id,
                    col(Requirement.version_status) != "removed",
                )
            ).all()
        )
        changed_ids: list[int] = []
        added: list[Requirement] = []
        counts = {"modified": 0, "added": 0, "removed": 0}

        for match in _DELETED.finditer(full_text):
            clause = match.group(1)
            for req in existing:
                if re.match(rf"^{re.escape(clause)}(?:\b|\.)", req.section_path):
                    req.version_status = "removed"
                    session.add(req)
                    counts["removed"] += 1

        new_items = []
        for item in items:
            context = f"{item.source_quote} {item.text}"
            amended = _AMENDED.search(context)
            added_clause = _ADDED.search(context)
            item.text = _strip_amendment_prefix(item.text)
            if added_clause:
                item.section_path = (
                    f"{added_clause.group(1)} {item.section_path.split(' ', 1)[-1]}".strip()
                )
                new_items.append(item)
                continue
            if amended:
                clause = amended.group(1)
                candidates = [
                    r
                    for r in existing
                    if re.match(rf"^{re.escape(clause)}(?:\b|\s|$)", r.section_path)
                ]
            else:
                candidates = existing
            best = max(candidates, key=lambda r: ratio(r.text, item.text), default=None)
            score = ratio(best.text, item.text) if best else 0.0
            if best and normalize(best.text).lower() == normalize(item.text).lower():
                continue
            if best and (amended or score >= MODIFIED_THRESHOLD):
                best.previous_text = best.previous_text or best.text
                best.text = item.text
                best.source_quote = item.source_quote
                best.version_status = "modified"
                best.rfp_file_id = file_id
                best.page = item.page
                session.add(best)
                assert best.id is not None
                changed_ids.append(best.id)
                counts["modified"] += 1
                response = session.exec(
                    select(Response).where(col(Response.requirement_id) == best.id)
                ).first()
                if response is not None:
                    response.needs_review = True
                    if response.approved:
                        audit.record(
                            session,
                            entity="response",
                            entity_id=response.id or 0,
                            action="unapproved_by_addendum",
                            actor="system",
                            project_id=project_id,
                        )
                    response.approved = False
                    session.add(response)
            else:
                new_items.append(item)

        codes = assign_codes(new_items, {r.req_code for r in existing})
        max_order = max((r.order for r in existing), default=0)
        for item, code in zip(new_items, codes, strict=True):
            max_order += 1
            req = Requirement(
                project_id=project_id,
                rfp_file_id=file_id,
                req_code=code,
                text=item.text,
                section_path=item.section_path,
                page=item.page,
                type=item.type,
                keyword=item.keyword,
                category=item.category,
                source_quote=item.source_quote,
                version_status="added",
                order=max_order,
            )
            session.add(req)
            session.flush()
            assert req.id is not None
            session.add(Response(requirement_id=req.id))
            added.append(req)
            changed_ids.append(req.id)
            counts["added"] += 1

        # Deadline changes ("extended to ...") update the project.
        from app.llm.offline import _parse_deadline

        new_deadline = parse_deadline(_parse_deadline(full_text))
        if new_deadline:
            project.deadline = new_deadline
            rules_row = session.exec(
                select(SubmissionRules).where(col(SubmissionRules.project_id) == project_id)
            ).first()
            if rules_row:
                rules_row.rules = {**rules_row.rules, "deadline": new_deadline.isoformat()}
                session.add(rules_row)
        project.tokens_used = usage.used
        session.add(project)
        session.commit()
        if added:
            link_criteria(llm, session, project_id, usage, added)
        ctx.progress("matching", 80, "Changes matched", **counts)
        session.commit()

    if changed_ids:
        ctx.progress("drafting", 85, f"Re-drafting {len(changed_ids)} changed requirement(s)")
        from app.pipeline.draft import draft_job

        sub = JobContext(
            job_id=ctx.job_id,
            engine=ctx.engine,
            settings=ctx.settings,
            params={
                "project_id": project_id,
                "requirement_ids": changed_ids,
                "include_approved": True,
            },
        )
        draft_job(sub)
        for key, value in counts.items():
            ctx.counts[key] = value
    ctx.progress("done", 100, "Addendum applied", **counts)


__all__ = ["Path", "classify_chunks", "generate_outline", "run_consistency", "word_diff"]
