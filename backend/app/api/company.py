from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from sqlmodel import col, select

from app.core.deps import CurrentUser, SessionDep, SettingsDep
from app.core.errors import NotFoundError, ValidationFailedError
from app.jobs.runner import JobRunner
from app.models import KnowledgeChunk, KnowledgeDoc
from app.models.tables import utcnow
from app.pipeline.retrieve import KnowledgeIndex
from app.schemas.api import (
    CompanyIn,
    CompanyOut,
    JobStarted,
    KnowledgeDocOut,
    KnowledgeDocPatch,
    SearchHit,
)
from app.services.company import get_or_create_company
from app.services.files import save_upload

router = APIRouter(tags=["company"])
DOC_TYPES = {"past_proposal", "product", "certificate", "case_study", "profile", "other"}


def _company_out(session: SessionDep) -> CompanyOut:
    company = get_or_create_company(session)
    return CompanyOut.model_validate(company.model_dump())


@router.get("/company", response_model=CompanyOut)
def get_company(_: CurrentUser, session: SessionDep) -> CompanyOut:
    return _company_out(session)


@router.put("/company", response_model=CompanyOut)
def update_company(body: CompanyIn, _: CurrentUser, session: SessionDep) -> CompanyOut:
    company = get_or_create_company(session)
    for key, value in body.model_dump().items():
        setattr(company, key, value)
    company.updated_at = utcnow()
    session.add(company)
    session.commit()
    return _company_out(session)


def _doc_out(doc: KnowledgeDoc) -> KnowledgeDocOut:
    assert doc.id is not None
    return KnowledgeDocOut(
        id=doc.id,
        outcome=doc.outcome,
        filename=doc.filename,
        doc_type=doc.doc_type,
        pages=doc.pages,
        status=doc.status,
        error=doc.error,
        created_at=doc.created_at,
    )


@router.get("/knowledge", response_model=list[KnowledgeDocOut])
def list_knowledge(_: CurrentUser, session: SessionDep) -> list[KnowledgeDocOut]:
    company = get_or_create_company(session)
    docs = session.exec(
        select(KnowledgeDoc)
        .where(col(KnowledgeDoc.company_id) == company.id)
        .order_by(col(KnowledgeDoc.id).desc())
    ).all()
    return [_doc_out(d) for d in docs]


@router.post("/knowledge", response_model=JobStarted, status_code=202)
def upload_knowledge(
    request: Request,
    _: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    files: Annotated[list[UploadFile], File()],
    doc_type: Annotated[str, Form()] = "other",
    outcome: Annotated[str, Form()] = "unknown",
) -> JobStarted:
    if outcome not in ("won", "lost", "unknown"):
        raise ValidationFailedError("outcome must be won, lost or unknown")
    if doc_type not in DOC_TYPES:
        raise ValidationFailedError(f"doc_type must be one of {', '.join(sorted(DOC_TYPES))}")
    if not files:
        raise ValidationFailedError("Attach at least one file")
    company = get_or_create_company(session)
    assert company.id is not None
    ids: list[int] = []
    for upload in files:
        path, _kind = save_upload(settings, upload, "knowledge")
        doc = KnowledgeDoc(
            company_id=company.id,
            outcome=outcome,
            filename=upload.filename or path.name,
            stored_path=str(path),
            doc_type=doc_type,
        )
        session.add(doc)
        session.commit()
        assert doc.id is not None
        ids.append(doc.id)
    runner: JobRunner = request.app.state.jobs
    job = runner.submit("index_knowledge", {"doc_ids": ids})
    assert job.id is not None
    return JobStarted(job_id=job.id)


@router.patch("/knowledge/{doc_id}", response_model=KnowledgeDocOut)
def update_knowledge(
    doc_id: int, body: KnowledgeDocPatch, _: CurrentUser, session: SessionDep
) -> KnowledgeDocOut:
    doc = session.get(KnowledgeDoc, doc_id)
    if doc is None:
        raise NotFoundError(f"Document {doc_id} not found")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(doc, key, value)
    doc.updated_at = utcnow()
    session.add(doc)
    session.commit()
    return _doc_out(doc)


@router.delete("/knowledge/{doc_id}", status_code=204)
def delete_knowledge(doc_id: int, _: CurrentUser, session: SessionDep) -> None:
    doc = session.get(KnowledgeDoc, doc_id)
    if doc is None:
        raise NotFoundError(f"Document {doc_id} not found")
    for chunk in session.exec(
        select(KnowledgeChunk).where(col(KnowledgeChunk.doc_id) == doc_id)
    ).all():
        session.delete(chunk)
    Path(doc.stored_path).unlink(missing_ok=True)
    session.delete(doc)
    session.commit()


@router.get("/knowledge/search", response_model=list[SearchHit])
def search_knowledge(
    q: Annotated[str, Query(min_length=2)],
    _: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
) -> list[SearchHit]:
    company = get_or_create_company(session)
    assert company.id is not None
    index = KnowledgeIndex(session, settings, company.id)
    return [
        SearchHit(chunk_id=e.chunk_id, filename=e.filename, page=e.page, text=e.text, score=e.score)
        for e in index.search(q, top_k=5)
        if e.source == "knowledge"
    ]
