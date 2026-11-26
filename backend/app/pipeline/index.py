"""Index company knowledge documents into embedded chunks stored in SQLite."""

import logging
from pathlib import Path

from sqlmodel import Session, col, delete, select

from app.core.config import Settings
from app.models import KnowledgeChunk, KnowledgeDoc
from app.pipeline.embed import get_embedder, to_bytes
from app.pipeline.parse import Line, parse_document
from app.pipeline.textutil import normalize, split_sentences

logger = logging.getLogger(__name__)
CHUNK_WORDS = 180
OVERLAP_WORDS = 40


def chunk_page(text: str) -> list[str]:
    """Split page text into ~180-word windows on sentence boundaries with ~40 words overlap."""
    sentences = split_sentences(text)
    chunks: list[str] = []
    current: list[str] = []
    count = 0
    for sentence in sentences:
        n = len(sentence.split())
        if current and count + n > CHUNK_WORDS:
            chunks.append(" ".join(current))
            tail: list[str] = []
            tail_count = 0
            for previous in reversed(current):
                tail_count += len(previous.split())
                tail.insert(0, previous)
                if tail_count >= OVERLAP_WORDS:
                    break
            current, count = tail, tail_count
        current.append(sentence)
        count += n
    if current:
        chunks.append(" ".join(current))
    return [c for c in chunks if len(c.split()) >= 5]


def _is_header_row(line: Line) -> bool:
    """Table header rows ("Certification | Number | Valid until") carry no evidence."""
    if not line.is_table_row:
        return False
    cells = [c.strip() for c in line.text.split(" | ") if c.strip()]
    return all(len(c.split()) <= 4 for c in cells) and not any(ch.isdigit() for ch in line.text)


def _as_sentence(line: Line) -> str:
    """Terminate headings and table rows so they never merge into the next sentence."""
    text = line.text.replace(" | ", ": ") if line.is_table_row else line.text
    looks_like_heading = line.is_table_row or line.bold or len(text.split()) <= 8
    if looks_like_heading and not text.endswith((".", ":", ";", "!", "?", ",")):
        return f"{text}."
    return text


def index_document(session: Session, settings: Settings, doc: KnowledgeDoc, kind: str) -> int:
    assert doc.id is not None
    parsed = parse_document(Path(doc.stored_path), kind, ocr=settings.ocr_enabled)
    session.exec(delete(KnowledgeChunk).where(col(KnowledgeChunk.doc_id) == doc.id))
    texts: list[tuple[int, str]] = []
    for page in parsed.pages:
        page_text = "\n".join(_as_sentence(line) for line in page.lines if not _is_header_row(line))
        for piece in chunk_page(page_text):
            texts.append((page.page, normalize(piece)))
    embedder = get_embedder(settings)
    vectors = embedder.embed([t for _, t in texts])
    for index, ((page_no, text), vector) in enumerate(zip(texts, vectors, strict=True)):
        session.add(
            KnowledgeChunk(
                doc_id=doc.id,
                company_id=doc.company_id,
                page=page_no,
                chunk_index=index,
                text=text,
                embedding=to_bytes(vector),
            )
        )
    doc.pages = len(parsed.pages)
    doc.status = "ready"
    doc.error = None
    session.add(doc)
    session.commit()
    logger.info("Indexed knowledge doc %s: %s chunks", doc.id, len(texts))
    return len(texts)


def company_chunks(session: Session, company_id: int) -> list[KnowledgeChunk]:
    return list(
        session.exec(
            select(KnowledgeChunk)
            .join(KnowledgeDoc, col(KnowledgeDoc.id) == col(KnowledgeChunk.doc_id))
            .where(
                col(KnowledgeChunk.company_id) == company_id, col(KnowledgeDoc.status) == "ready"
            )
        ).all()
    )
