"""Hybrid retrieval over company knowledge: vector cosine + BM25, plus the answer library."""

from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import AnswerLibrary, KnowledgeChunk, KnowledgeDoc
from app.pipeline.embed import Embedder, HashEmbedder, from_bytes, get_embedder
from app.pipeline.index import company_chunks
from app.pipeline.textutil import words

VECTOR_WEIGHT = 0.7
BM25_WEIGHT = 0.3
BM25_SATURATION = 6.0
HASH_MIN_SCORE = 0.12
OUTCOME_BOOST = {"won": 1.2, "unknown": 1.0, "lost": 0.9}
DOC_OUTCOME_BOOST = {"won": 1.15, "unknown": 1.0, "lost": 0.9}


@dataclass
class Evidence:
    chunk_id: int
    doc_id: int
    filename: str
    page: int
    text: str
    score: float
    source: str = "knowledge"  # knowledge | library
    outcome: str = "unknown"


class KnowledgeIndex:
    """In-memory index of one company's chunks for a batch of queries (one drafting job)."""

    def __init__(self, session: Session, settings: Settings, company_id: int) -> None:
        self.settings = settings
        self.embedder: Embedder = get_embedder(settings)
        chunks = company_chunks(session, company_id)
        doc_rows = list(
            session.exec(
                select(KnowledgeDoc).where(col(KnowledgeDoc.company_id) == company_id)
            ).all()
        )
        self.outcomes = {d.id: d.outcome for d in doc_rows}
        docs = {
            d.id: d.filename
            for d in session.exec(
                select(KnowledgeDoc).where(col(KnowledgeDoc.company_id) == company_id)
            ).all()
        }
        self.chunks: list[KnowledgeChunk] = [
            c for c in chunks if len(from_bytes(c.embedding)) == self.embedder.dim
        ]
        self.filenames = docs
        self.matrix = (
            np.vstack([from_bytes(c.embedding) for c in self.chunks])
            if self.chunks
            else np.zeros((0, self.embedder.dim), dtype=np.float32)
        )
        self.bm25 = BM25Okapi([words(c.text) for c in self.chunks]) if self.chunks else None
        library = list(
            session.exec(
                select(AnswerLibrary).where(col(AnswerLibrary.company_id) == company_id)
            ).all()
        )
        self.library = [a for a in library if len(from_bytes(a.embedding)) == self.embedder.dim]
        self.library_matrix = (
            np.vstack([from_bytes(a.embedding) for a in self.library])
            if self.library
            else np.zeros((0, self.embedder.dim), dtype=np.float32)
        )

    @property
    def min_score(self) -> float:
        """Below this top score a requirement is a gap. Hash vectors score lower than neural ones."""
        if isinstance(self.embedder, HashEmbedder):
            return min(self.settings.retrieval_min_score, HASH_MIN_SCORE)
        return self.settings.retrieval_min_score

    @property
    def empty(self) -> bool:
        return not self.chunks

    def search(self, query: str, top_k: int | None = None) -> list[Evidence]:
        top_k = top_k or self.settings.retrieval_top_k
        results: list[Evidence] = []
        query_vec = self.embedder.embed([query])[0]
        if self.chunks and self.bm25 is not None:
            cosine = self.matrix @ query_vec
            raw_bm25 = np.asarray(self.bm25.get_scores(words(query)), dtype=np.float32)
            bm25 = raw_bm25 / (raw_bm25 + BM25_SATURATION)
            hybrid = VECTOR_WEIGHT * np.clip(cosine, 0, 1) + BM25_WEIGHT * bm25
            boost = np.array(
                [
                    DOC_OUTCOME_BOOST.get(self.outcomes.get(c.doc_id, "unknown"), 1.0)
                    for c in self.chunks
                ],
                dtype=np.float32,
            )
            hybrid = np.clip(hybrid * boost, 0, 1)
            for i in np.argsort(-hybrid)[:top_k]:
                chunk = self.chunks[int(i)]
                assert chunk.id is not None
                results.append(
                    Evidence(
                        chunk_id=chunk.id,
                        doc_id=chunk.doc_id,
                        filename=self.filenames.get(chunk.doc_id, "document"),
                        page=chunk.page,
                        text=chunk.text,
                        score=round(float(hybrid[int(i)]), 4),
                        outcome=self.outcomes.get(chunk.doc_id, "unknown"),
                    )
                )
        if self.library:
            sims = self.library_matrix @ query_vec
            for i in np.argsort(-sims)[:2]:
                entry = self.library[int(i)]
                score = (
                    float(np.clip(sims[int(i)], 0, 1))
                    * VECTOR_WEIGHT
                    * OUTCOME_BOOST.get(entry.outcome, 1.0)
                )
                assert entry.id is not None
                results.append(
                    Evidence(
                        chunk_id=-entry.id,  # negative ids mark answer-library entries
                        doc_id=0,
                        filename=f"Answer library ({entry.outcome})",
                        page=0,
                        text=entry.answer,
                        score=round(score, 4),
                        source="library",
                        outcome=entry.outcome,
                    )
                )
        results.sort(key=lambda e: e.score, reverse=True)
        return results[:top_k]
