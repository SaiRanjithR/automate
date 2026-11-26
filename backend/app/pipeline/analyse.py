"""Analyse job: parse RFP files, extract requirements, submission rules and evaluation criteria."""

import logging
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, col, delete, select

from app.core.config import Settings
from app.jobs.runner import JobContext, register
from app.llm.client import LLM, UsageMeter, get_llm
from app.models import (
    EvaluationCriterion,
    OutlineSection,
    Project,
    Requirement,
    Response,
    RfpFile,
    RfpPage,
    SubmissionRules,
)
from app.models.tables import utcnow
from app.pipeline.chunk import Chunk, build_chunks, section_number
from app.pipeline.parse import parse_document
from app.pipeline.textutil import normalize, quote_found, similarity
from app.schemas.llm import (
    ChunkClassification,
    CriteriaList,
    CriterionLinks,
    ExtractedRequirement,
    RequirementList,
    SubmissionRulesOut,
)
from app.services.files import sniff_kind

logger = logging.getLogger(__name__)

REQUIREMENT_CATEGORIES = {
    "scope",
    "technical",
    "sla",
    "eligibility",
    "commercial",
    "general_conditions",
    "other",
}
RULE_CATEGORIES = {"introduction", "instructions", "eligibility", "forms", "commercial", "other"}
MAX_RULES_CHARS = 90_000
DEDUPE_THRESHOLD = 0.92


def parse_rfp_file(session: Session, settings: Settings, rfp_file: RfpFile) -> list[Chunk]:
    """Parse one RFP file, store its page texts, return its chunks."""
    path = Path(rfp_file.stored_path)
    kind = sniff_kind(path) or "pdf"
    parsed = parse_document(path, kind, ocr=settings.ocr_enabled)
    session.exec(delete(RfpPage).where(col(RfpPage.rfp_file_id) == rfp_file.id))
    for page in parsed.pages:
        assert rfp_file.id is not None
        session.add(RfpPage(rfp_file_id=rfp_file.id, page=page.page, text=page.text))
    rfp_file.pages = len(parsed.pages)
    rfp_file.parsed_at = utcnow()
    session.add(rfp_file)
    session.commit()
    return build_chunks(parsed)


def classify_chunks(llm: LLM, chunks: list[Chunk], usage: UsageMeter) -> None:
    for chunk in chunks:
        result = llm.complete(
            "classify_chunk",
            {"heading": chunk.heading, "text": chunk.text[:1500]},
            ChunkClassification,
            usage,
        )
        chunk.category = result.value.category


def buyer_aliases(buyer: str | None) -> list[str]:
    """Names the buyer goes by: the full name and any acronym in brackets, e.g. 'GeM'."""
    if not buyer:
        return []
    aliases = {buyer.strip()}
    for acronym in re.findall(r"\(([A-Za-z][A-Za-z\-]{1,12})\)", buyer):
        aliases.add(acronym)
    base = re.sub(r"\s*\([^)]*\)", "", buyer).strip()
    if base:
        aliases.add(base)
    return sorted(aliases, key=len, reverse=True)


def extract_from_chunks(
    llm: LLM,
    settings: Settings,
    chunks: list[Chunk],
    page_texts: dict[int, str],
    usage: UsageMeter,
    buyer: str | None = None,
) -> list[ExtractedRequirement]:
    """Run extraction on requirement chunks in parallel; keep items whose quote is on the page."""
    targets = [c for c in chunks if c.category in REQUIREMENT_CATEGORIES]
    aliases = buyer_aliases(buyer)

    def run(chunk: Chunk) -> list[ExtractedRequirement]:
        result = llm.complete(
            "extract_requirements",
            {
                "section_path": chunk.section_path,
                "chunk_text": chunk.text,
                "buyer": buyer or "the buyer",
                "category": chunk.category,
                "buyer_aliases": aliases,
            },
            RequirementList,
            usage,
        )
        return result.value.requirements

    with ThreadPoolExecutor(max_workers=settings.llm_max_concurrency) as pool:
        batches = list(pool.map(run, targets))

    verified: list[ExtractedRequirement] = []
    dropped = 0
    for items in batches:
        for item in items:
            nearby = " ".join(
                page_texts.get(p, "") for p in (item.page - 1, item.page, item.page + 1)
            )
            if quote_found(item.source_quote, nearby):
                verified.append(item)
            else:
                dropped += 1
    if dropped:
        logger.info("Dropped %s requirements whose quote was not found on the page", dropped)
    return dedupe(verified)


def dedupe(items: list[ExtractedRequirement]) -> list[ExtractedRequirement]:
    kept: list[ExtractedRequirement] = []
    for item in items:
        if any(similarity(item.text, k.text) >= DEDUPE_THRESHOLD for k in kept):
            continue
        kept.append(item)
    return kept


def requirement_prefix(section_path: str) -> str:
    match = re.match(r"^(\d+)(?:\.(\d+))?", section_path)
    if match:
        return f"{match.group(1)}.{match.group(2)}" if match.group(2) else match.group(1)
    return section_number(section_path)


def assign_codes(
    items: list[ExtractedRequirement], existing_codes: set[str] | None = None
) -> list[str]:
    counters: dict[str, int] = defaultdict(int)
    used = set(existing_codes or set())
    codes: list[str] = []
    for item in items:
        prefix = requirement_prefix(item.section_path)
        while True:
            counters[prefix] += 1
            code = f"R-{prefix}-{counters[prefix]:02d}"
            if code not in used:
                break
        used.add(code)
        codes.append(code)
    return codes


def parse_deadline(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def extract_rules(llm: LLM, chunks: list[Chunk], usage: UsageMeter) -> SubmissionRulesOut:
    parts: list[str] = []
    size = 0
    for index, chunk in enumerate(chunks):
        if index == 0 or chunk.category in RULE_CATEGORIES or chunk.heading == "Preamble":
            text = chunk.text
            if size + len(text) > MAX_RULES_CHARS:
                break
            parts.append(text)
            size += len(text)
    return llm.complete(
        "extract_submission_rules", {"text": "\n\n".join(parts)}, SubmissionRulesOut, usage
    ).value


def extract_criteria(llm: LLM, chunks: list[Chunk], usage: UsageMeter) -> CriteriaList:
    text = "\n\n".join(c.text for c in chunks if c.category == "evaluation")
    if not text:
        return CriteriaList(qcbs_split=None, min_qualifying_marks=None, criteria=[])
    return llm.complete("extract_criteria", {"text": text}, CriteriaList, usage).value


def link_criteria(
    llm: LLM,
    session: Session,
    project_id: int,
    usage: UsageMeter,
    requirements: list[Requirement] | None = None,
) -> None:
    criteria = list(
        session.exec(
            select(EvaluationCriterion).where(col(EvaluationCriterion.project_id) == project_id)
        ).all()
    )
    if requirements is None:
        requirements = list(
            session.exec(select(Requirement).where(col(Requirement.project_id) == project_id)).all()
        )
    if not criteria or not requirements:
        return
    by_code = {c.code: c for c in criteria}
    criteria_list = [
        {"code": c.code, "name": c.name, "sub_criteria": c.sub_criteria, "max_marks": c.max_marks}
        for c in criteria
    ]
    criteria_text = "\n".join(
        f"{c.code}: {c.name} ({c.max_marks} marks) — {'; '.join(c.sub_criteria)}" for c in criteria
    )
    for start in range(0, len(requirements), 30):
        batch = requirements[start : start + 30]
        req_list = [{"text": r.text, "category": r.category} for r in batch]
        req_text = "\n".join(f"{i}: {r.text}" for i, r in enumerate(batch))
        result = llm.complete(
            "link_requirements_to_criteria",
            {
                "criteria": criteria_text,
                "requirements": req_text,
                "criteria_list": criteria_list,
                "requirement_list": req_list,
            },
            CriterionLinks,
            usage,
        )
        for link in result.value.links:
            if 0 <= link.requirement_index < len(batch) and link.criterion_code in by_code:
                batch[link.requirement_index].criterion_id = by_code[link.criterion_code].id
                session.add(batch[link.requirement_index])
    session.commit()


def store_rules(session: Session, project: Project, rules: SubmissionRulesOut) -> None:
    assert project.id is not None
    existing = session.exec(
        select(SubmissionRules).where(col(SubmissionRules.project_id) == project.id)
    ).first()
    data: dict[str, Any] = rules.model_dump()
    if existing:
        existing.rules = data
        session.add(existing)
    else:
        session.add(SubmissionRules(project_id=project.id, rules=data))
    if rules.title and not project.title.strip():
        project.title = rules.title
    if rules.tender_no and not project.tender_no:
        project.tender_no = rules.tender_no
    if rules.buyer and not project.buyer:
        project.buyer = rules.buyer
    deadline = parse_deadline(rules.deadline)
    if deadline:
        project.deadline = deadline
    session.add(project)


@register("analyse")
def analyse_job(ctx: JobContext) -> None:
    project_id = int(ctx.params["project_id"])
    settings = ctx.settings
    llm = get_llm(settings)
    with Session(ctx.engine) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")
        usage = UsageMeter(settings.llm_max_tokens_per_project, project.tokens_used)
        project.status = "analysing"
        session.add(project)
        session.commit()
        files = list(
            session.exec(
                select(RfpFile)
                .where(col(RfpFile.project_id) == project_id, col(RfpFile.role) != "addendum")
                .order_by(col(RfpFile.id))
            ).all()
        )
        try:
            ctx.progress("parsing", 5, f"Parsing {len(files)} file(s)")
            all_chunks: list[tuple[RfpFile, Chunk]] = []
            pages_total = 0
            for rfp_file in files:
                chunks = parse_rfp_file(session, settings, rfp_file)
                pages_total += rfp_file.pages
                all_chunks.extend((rfp_file, c) for c in chunks)
            ctx.progress("parsing", 15, f"Parsed {pages_total} pages", pages=pages_total)

            classify_chunks(llm, [c for _, c in all_chunks], usage)
            ctx.progress("rules", 20, "Reading submission rules", sections=len(all_chunks))
            rules = extract_rules(llm, [c for _, c in all_chunks], usage)
            store_rules(session, project, rules)
            session.commit()
            ctx.progress(
                "requirements",
                30,
                "Finding requirements",
                forms=len(rules.forms),
                eligibility=len(rules.eligibility),
            )

            # Children before parents: requirements (and their responses) reference outline
            # sections, which reference evaluation criteria.
            req_ids = list(
                session.exec(
                    select(Requirement.id).where(col(Requirement.project_id) == project_id)
                ).all()
            )
            session.exec(delete(Response).where(col(Response.requirement_id).in_(req_ids)))
            session.exec(delete(Requirement).where(col(Requirement.project_id) == project_id))
            session.exec(delete(OutlineSection).where(col(OutlineSection.project_id) == project_id))
            session.exec(
                delete(EvaluationCriterion).where(col(EvaluationCriterion.project_id) == project_id)
            )
            session.commit()

            all_items: list[tuple[RfpFile, ExtractedRequirement]] = []
            for rfp_file in files:
                page_texts = {
                    p.page: p.text
                    for p in session.exec(
                        select(RfpPage).where(col(RfpPage.rfp_file_id) == rfp_file.id)
                    ).all()
                }
                file_chunks = [c for f, c in all_chunks if f.id == rfp_file.id]
                items = extract_from_chunks(
                    llm, settings, file_chunks, page_texts, usage, buyer=rules.buyer
                )
                all_items.extend((rfp_file, item) for item in items)
            unique = dedupe([item for _, item in all_items])
            codes = assign_codes(unique)
            file_for = {id(item): f for f, item in all_items}
            for order, (item, code) in enumerate(zip(unique, codes, strict=True), start=1):
                req = Requirement(
                    project_id=project_id,
                    rfp_file_id=file_for[id(item)].id if id(item) in file_for else None,
                    req_code=code,
                    text=item.text,
                    section_path=item.section_path,
                    page=item.page,
                    type=item.type,
                    keyword=item.keyword,
                    category=item.category,
                    source_quote=item.source_quote,
                    order=order,
                )
                session.add(req)
                session.flush()
                assert req.id is not None
                session.add(Response(requirement_id=req.id))
            session.commit()
            ctx.progress(
                "requirements", 55, f"Found {len(unique)} requirements", requirements=len(unique)
            )

            ctx.progress("criteria", 80, "Reading scoring criteria")
            criteria = extract_criteria(llm, [c for _, c in all_chunks], usage)
            for crit in criteria.criteria:
                session.add(
                    EvaluationCriterion(
                        project_id=project_id,
                        code=crit.code,
                        name=crit.name,
                        max_marks=crit.max_marks,
                        sub_criteria=crit.sub_criteria,
                        min_qualifying_marks=criteria.min_qualifying_marks,
                        page=crit.page,
                    )
                )
            rules_row = session.exec(
                select(SubmissionRules).where(col(SubmissionRules.project_id) == project_id)
            ).one()
            rules_row.rules = {
                **rules_row.rules,
                "qcbs_split": criteria.qcbs_split,
                "min_qualifying_marks": criteria.min_qualifying_marks,
            }
            session.add(rules_row)
            session.commit()
            link_criteria(llm, session, project_id, usage)
            ctx.progress(
                "criteria",
                95,
                f"Read {len(criteria.criteria)} scoring criteria",
                criteria=len(criteria.criteria),
            )

            project.status = "ready"
            project.tokens_used = usage.used
            session.add(project)
            session.commit()
        except Exception:
            session.rollback()
            project = session.get(Project, project_id)
            if project is not None:
                project.status = "failed"
                project.tokens_used = usage.used
                session.add(project)
                session.commit()
            raise


def normalize_text(text: str) -> str:
    return normalize(text)
