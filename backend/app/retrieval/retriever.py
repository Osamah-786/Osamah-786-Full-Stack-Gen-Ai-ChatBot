"""Compose semantic and full-text search into source passages."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database.models import DocumentChunk, SourceDocument
from app.embeddings import embed_query
from app.retrieval import queries
from app.retrieval.fusion import reciprocal_rank_fusion


class RetrievalFilters(BaseModel):
    """Optional filing filters, also suitable for future bounded agent tools."""

    tickers: list[str] = Field(default_factory=list)
    fiscal_years: list[int] = Field(default_factory=list)
    filing_types: list[str] = Field(default_factory=list)


class RetrievedPassage(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_id: UUID
    source_document_id: UUID
    chunk_index: int
    text: str
    page_number: int | None
    section: str | None
    ticker: str
    company_name: str
    filing_type: str
    filing_date: date
    fiscal_year: int
    accession_number: str
    source_url: str
    rank: int | None
    score: float
    is_neighbor: bool


class DocumentRetriever:
    """Synchronous retrieval service; callers own the SQLAlchemy session."""

    def __init__(
        self,
        session: Session,
        *,
        candidate_limit: int = 50,
        result_limit: int = 10,
        neighbor_window: int = 1,
    ) -> None:
        if candidate_limit <= 0 or result_limit <= 0 or neighbor_window < 0:
            raise ValueError("Retrieval limits must be positive and neighbor_window non-negative")
        self._session = session
        self._candidate_limit = candidate_limit
        self._result_limit = result_limit
        self._neighbor_window = neighbor_window

    def search(
        self,
        query: str,
        *,
        filters: RetrievalFilters | None = None,
    ) -> list[RetrievedPassage]:
        query = query.strip()
        if not query:
            return []

        filters = filters or RetrievalFilters()
        filter_args = {
            "tickers": filters.tickers or None,
            "fiscal_years": filters.fiscal_years or None,
            "filing_types": filters.filing_types or None,
        }
        vector_ids = queries.semantic_search(
            self._session,
            embed_query(query),
            limit=self._candidate_limit,
            **filter_args,
        )
        text_ids = queries.full_text_search(
            self._session,
            query,
            limit=self._candidate_limit,
            **filter_args,
        )
        fused = reciprocal_rank_fusion([vector_ids, text_ids])[: self._result_limit]
        if not fused:
            return []

        anchors = queries.load_chunks(self._session, [hit.chunk_id for hit in fused])
        if not anchors:
            return []
        surrounding = queries.load_neighbors(
            self._session,
            anchors,
            window=self._neighbor_window,
        )

        fused_by_id = {hit.chunk_id: (rank, hit.score) for rank, hit in enumerate(fused, start=1)}
        anchor_rank_by_id = {
            chunk.id: fused_by_id[chunk.id][0]
            for chunk, _ in anchors
            if chunk.id in fused_by_id
        }
        contextualized: dict[UUID, tuple[DocumentChunk, SourceDocument, int]] = {}
        for chunk, source in surrounding:
            nearby_ranks = [
                anchor_rank_by_id[anchor.id]
                for anchor, _ in anchors
                if anchor.source_document_id == chunk.source_document_id
                and abs(anchor.chunk_index - chunk.chunk_index) <= self._neighbor_window
            ]
            if nearby_ranks:
                contextualized[chunk.id] = (chunk, source, min(nearby_ranks))

        passages = []
        for chunk, source, context_rank in sorted(
            contextualized.values(),
            key=lambda item: (item[2], item[1].ticker, item[1].fiscal_year, item[0].chunk_index),
        ):
            rank_score = fused_by_id.get(chunk.id)
            passages.append(
                RetrievedPassage(
                    chunk_id=chunk.id,
                    source_document_id=chunk.source_document_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.chunk_text,
                    page_number=chunk.page_number,
                    section=chunk.section,
                    ticker=source.ticker,
                    company_name=source.company_name,
                    filing_type=source.filing_type,
                    filing_date=source.filing_date,
                    fiscal_year=source.fiscal_year,
                    accession_number=source.accession_number,
                    source_url=source.source_url,
                    rank=rank_score[0] if rank_score else None,
                    score=rank_score[1] if rank_score else 0.0,
                    is_neighbor=rank_score is None,
                )
            )
        return passages

    def read_chunk(self, chunk_id: UUID) -> RetrievedPassage | None:
        rows = queries.load_chunks(self._session, [chunk_id])
        return _passage(rows[0], rank=None, score=0.0, is_neighbor=False) if rows else None

    def read_surrounding_chunks(
        self, chunk_id: UUID, *, window: int = 1
    ) -> list[RetrievedPassage]:
        anchors = queries.load_chunks(self._session, [chunk_id])
        if not anchors:
            return []
        rows = queries.load_neighbors(self._session, anchors, window=window)
        return [
            _passage((chunk, source), rank=None, score=0.0, is_neighbor=chunk.id != chunk_id)
            for chunk, source in rows
        ]


def _passage(
    row: tuple[DocumentChunk, SourceDocument],
    *,
    rank: int | None,
    score: float,
    is_neighbor: bool,
) -> RetrievedPassage:
    chunk, source = row
    return RetrievedPassage(
        chunk_id=chunk.id,
        source_document_id=chunk.source_document_id,
        chunk_index=chunk.chunk_index,
        text=chunk.chunk_text,
        page_number=chunk.page_number,
        section=chunk.section,
        ticker=source.ticker,
        company_name=source.company_name,
        filing_type=source.filing_type,
        filing_date=source.filing_date,
        fiscal_year=source.fiscal_year,
        accession_number=source.accession_number,
        source_url=source.source_url,
        rank=rank,
        score=score,
        is_neighbor=is_neighbor,
    )
