"""Single-workspace company profile and knowledge indexing job."""

from pathlib import Path

from sqlmodel import Session, col, select

from app.jobs.runner import JobContext, register
from app.models import Company, KnowledgeDoc
from app.pipeline.index import index_document
from app.services.files import sniff_kind


def get_or_create_company(session: Session) -> Company:
    company = session.exec(select(Company).order_by(col(Company.id))).first()
    if company is None:
        company = Company()
        session.add(company)
        session.commit()
        session.refresh(company)
    return company


@register("index_knowledge")
def index_knowledge_job(ctx: JobContext) -> None:
    doc_ids: list[int] = [int(i) for i in ctx.params.get("doc_ids", [])]
    total = len(doc_ids)
    failed = 0
    for n, doc_id in enumerate(doc_ids, start=1):
        with Session(ctx.engine) as session:
            doc = session.get(KnowledgeDoc, doc_id)
            if doc is None:
                continue
            doc.status = "indexing"
            session.add(doc)
            session.commit()
            try:
                kind = sniff_kind(Path(doc.stored_path)) or "pdf"
                index_document(session, ctx.settings, doc, kind)
            except Exception as exc:
                session.rollback()
                doc = session.get(KnowledgeDoc, doc_id)
                if doc is not None:
                    doc.status = "failed"
                    doc.error = str(exc)[:500]
                    session.add(doc)
                    session.commit()
                failed += 1
        ctx.progress(
            "indexing",
            round(100 * n / max(total, 1)),
            f"Indexed {n} of {total}",
            indexed=n - failed,
            failed=failed,
        )
