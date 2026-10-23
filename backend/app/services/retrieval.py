"""Hybrid retrieval: pgvector cosine similarity + Postgres full-text search,
merged with Reciprocal Rank Fusion and boosted for the current academic year."""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.llm_client import STOPWORDS, tokenize


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    title: str
    content: str
    page_no: int | None
    source_url: str | None
    academic_year: str | None
    doc_type: str
    vector_score: float = 0.0
    keyword_score: float = 0.0
    fused_score: float = 0.0


@dataclass
class FAQHit:
    id: int
    question: str
    answer: str
    score: float


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def build_tsquery(query: str) -> str | None:
    """OR-query of meaningful tokens, e.g. 'annual | fee | cse'. Safe for to_tsquery."""
    toks = [t for t in tokenize(query) if t not in STOPWORDS and len(t) > 1]
    toks = [re.sub(r"[^\w]", "", t) for t in toks]
    toks = list(dict.fromkeys(t for t in toks if t))[:12]
    return " | ".join(toks) if toks else None


ACTIVE_DOC_FILTER = """
    d.status = 'active'
    AND (d.valid_to IS NULL OR d.valid_to >= CURRENT_DATE)
    AND (d.valid_from IS NULL OR d.valid_from <= CURRENT_DATE + INTERVAL '365 days')
"""


async def search_chunks(db: AsyncSession, query: str, query_vec: list[float],
                        candidates: int | None = None, top_k: int | None = None) -> list[RetrievedChunk]:
    candidates = candidates or settings.RETRIEVAL_CANDIDATES
    top_k = top_k or settings.RETRIEVAL_TOP_K
    # Make the HNSW index return enough rows after filtering.
    await db.execute(text("SET LOCAL hnsw.ef_search = 100"))

    vec_sql = text(f"""
        SELECT c.id, c.document_id, d.title, c.content, c.page_no, d.source_url, d.academic_year, d.doc_type,
               1 - (c.embedding <=> CAST(:qv AS vector)) AS score
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE {ACTIVE_DOC_FILTER} AND c.embedding IS NOT NULL
        ORDER BY c.embedding <=> CAST(:qv AS vector)
        LIMIT :lim
    """)
    rows_v = (await db.execute(vec_sql, {"qv": _vec_literal(query_vec), "lim": candidates})).all()

    rows_k = []
    tsq = build_tsquery(query)
    if tsq:
        kw_sql = text(f"""
            SELECT c.id, c.document_id, d.title, c.content, c.page_no, d.source_url, d.academic_year, d.doc_type,
                   ts_rank_cd(c.tsv, to_tsquery('simple', :tsq)) AS score
            FROM chunks c JOIN documents d ON d.id = c.document_id
            WHERE {ACTIVE_DOC_FILTER} AND c.tsv @@ to_tsquery('simple', :tsq)
            ORDER BY score DESC
            LIMIT :lim
        """)
        rows_k = (await db.execute(kw_sql, {"tsq": tsq, "lim": candidates})).all()

    merged: dict[int, RetrievedChunk] = {}
    k = 60  # RRF constant
    for rank, r in enumerate(rows_v):
        item = merged.setdefault(r.id, RetrievedChunk(r.id, r.document_id, r.title, r.content, r.page_no,
                                                       r.source_url, r.academic_year, r.doc_type))
        item.vector_score = float(r.score)
        item.fused_score += 1.0 / (k + rank + 1)
    for rank, r in enumerate(rows_k):
        item = merged.setdefault(r.id, RetrievedChunk(r.id, r.document_id, r.title, r.content, r.page_no,
                                                       r.source_url, r.academic_year, r.doc_type))
        item.keyword_score = float(r.score)
        item.fused_score += 1.0 / (k + rank + 1)

    current = settings.CURRENT_ACADEMIC_YEAR
    for item in merged.values():
        if item.academic_year and item.academic_year < current:
            item.fused_score *= 0.6  # older academic year: still usable, but the current one wins

    ranked = sorted(merged.values(), key=lambda x: x.fused_score, reverse=True)
    return ranked[:top_k]


async def match_faq(db: AsyncSession, query_vec: list[float]) -> FAQHit | None:
    row = (await db.execute(text("""
        SELECT id, question, answer, 1 - (embedding <=> CAST(:qv AS vector)) AS score
        FROM faqs WHERE is_active AND embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:qv AS vector) LIMIT 1
    """), {"qv": _vec_literal(query_vec)})).first()
    if row and row.score >= settings.FAQ_MATCH_THRESHOLD:
        return FAQHit(row.id, row.question, row.answer, float(row.score))
    return None


def relevance(chunks: list[RetrievedChunk]) -> float:
    """Confidence that we actually have relevant context (0..1)."""
    if not chunks:
        return 0.0
    best_vec = max(c.vector_score for c in chunks)
    has_keyword = any(c.keyword_score > 0 for c in chunks)
    # A keyword hit on top of moderate semantic similarity is strong evidence.
    return min(1.0, best_vec + (0.1 if has_keyword else 0.0))
