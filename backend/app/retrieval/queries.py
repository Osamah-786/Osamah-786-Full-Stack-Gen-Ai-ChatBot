"""PostgreSQL full-text and pgvector searches for document chunks."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.embeddings import DIMENSIONS
from app.database.models import DocumentChunk, SourceDocument


def _filters(
    *,
    tickers: Sequence[str] | None,
    fiscal_years: Sequence[int] | None,
    filing_types: Sequence[str] | None,
) -> list:
    conditions = []
    if tickers:
        conditions.append(SourceDocument.ticker.in_([item.upper() for item in tickers]))
    if fiscal_years:
        conditions.append(SourceDocument.fiscal_year.in_(fiscal_years))
    if filing_types:
        conditions.append(SourceDocument.filing_type.in_([item.upper() for item in filing_types]))
    return conditions


def semantic_search(
    session: Session,
    query_embedding: list[float],
    *,
    limit: int = 50,
    tickers: Sequence[str] | None = None,
    fiscal_years: Sequence[int] | None = None,
    filing_types: Sequence[str] | None = None,
) -> list[UUID]:
    """Return chunk IDs ordered by cosine distance to a query embedding."""
    if limit <= 0:
        return []
    if len(query_embedding) != DIMENSIONS:
        raise ValueError(f"Query embedding must have {DIMENSIONS} dimensions")

    conditions = _filters(
        tickers=tickers, fiscal_years=fiscal_years, filing_types=filing_types
    )
    conditions.append(DocumentChunk.embedding_384.is_not(None))
    distance = DocumentChunk.embedding_384.cosine_distance(query_embedding)
    statement = (
        select(DocumentChunk.id)
        .join(SourceDocument, DocumentChunk.source_document_id == SourceDocument.id)
        .where(*conditions)
        .order_by(distance)
        .limit(limit)
    )
    return list(session.scalars(statement))


def full_text_search(
    session: Session,
    query: str,
    *,
    limit: int = 50,
    tickers: Sequence[str] | None = None,
    fiscal_years: Sequence[int] | None = None,
    filing_types: Sequence[str] | None = None,
) -> list[UUID]:
    """Return chunk IDs ranked by PostgreSQL's English full-text search."""
    query = query.strip()
    if not query or limit <= 0:
        return []

    tsquery = func.websearch_to_tsquery("english", query)
    rank = func.ts_rank_cd(DocumentChunk.search_vector, tsquery)
    conditions = _filters(
        tickers=tickers, fiscal_years=fiscal_years, filing_types=filing_types
    )
    conditions.append(DocumentChunk.search_vector.op("@@")(tsquery))
    statement = (
        select(DocumentChunk.id)
        .join(SourceDocument, DocumentChunk.source_document_id == SourceDocument.id)
        .where(*conditions)
        .order_by(rank.desc())
        .limit(limit)
    )
    return list(session.scalars(statement))


def load_chunks(
    session: Session,
    chunk_ids: Sequence[UUID],
) -> list[tuple[DocumentChunk, SourceDocument]]:
    """Load chunks with filing metadata, preserving the caller's requested IDs."""
    if not chunk_ids:
        return []
    statement = (
        select(DocumentChunk, SourceDocument)
        .join(SourceDocument, DocumentChunk.source_document_id == SourceDocument.id)
        .where(DocumentChunk.id.in_(chunk_ids))
    )
    rows = session.execute(statement).all()
    by_id = {chunk.id: (chunk, source) for chunk, source in rows}
    return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]


def load_neighbors(
    session: Session,
    anchors: Sequence[tuple[DocumentChunk, SourceDocument]],
    *,
    window: int = 1,
) -> list[tuple[DocumentChunk, SourceDocument]]:
    """Load nearby chunks from the same filings as the retrieved anchors."""
    if not anchors:
        return []

    ranges: dict[UUID, set[int]] = {}
    for chunk, _ in anchors:
        ranges.setdefault(chunk.source_document_id, set()).update(
            range(max(0, chunk.chunk_index - window), chunk.chunk_index + window + 1)
        )
    conditions = [
        and_(
            DocumentChunk.source_document_id == source_id,
            DocumentChunk.chunk_index.in_(indices),
        )
        for source_id, indices in ranges.items()
    ]
    statement = (
        select(DocumentChunk, SourceDocument)
        .join(SourceDocument, DocumentChunk.source_document_id == SourceDocument.id)
        .where(or_(*conditions))
        .order_by(SourceDocument.ticker, SourceDocument.fiscal_year, DocumentChunk.chunk_index)
    )
    return list(session.execute(statement).all())
