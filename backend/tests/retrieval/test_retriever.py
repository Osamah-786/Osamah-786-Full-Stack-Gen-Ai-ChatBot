from datetime import date
from types import SimpleNamespace
from uuid import UUID

from app.retrieval import queries
from app.retrieval.retriever import DocumentRetriever, RetrievalFilters


def _row(chunk_id: UUID, index: int):
    source_id = UUID(int=100)
    chunk = SimpleNamespace(
        id=chunk_id,
        source_document_id=source_id,
        chunk_index=index,
        chunk_text=f"passage {index}",
        page_number=index + 1,
        section="Business",
    )
    source = SimpleNamespace(
        id=source_id,
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        filing_date=date(2024, 11, 1),
        fiscal_year=2024,
        accession_number="0000000000-24-000001",
        source_url="https://example.test/filing",
    )
    return chunk, source


def test_retriever_fuses_searches_and_marks_neighbor_passages(monkeypatch) -> None:
    ids = [UUID(int=value) for value in (1, 2, 3)]
    rows = [_row(ids[0], 4), _row(ids[1], 3), _row(ids[2], 5)]
    observed_filters = []
    monkeypatch.setattr("app.retrieval.retriever.embed_query", lambda query: [0.0] * 384)
    monkeypatch.setattr(queries, "semantic_search", lambda *args, **kwargs: [ids[0], ids[1]])
    monkeypatch.setattr(
        queries,
        "full_text_search",
        lambda *args, **kwargs: [ids[1]],
    )

    def load_chunks(_session, chunk_ids):
        assert chunk_ids == [ids[1], ids[0]]
        return rows[:2]

    def load_neighbors(_session, anchors, *, window):
        observed_filters.append((len(anchors), window))
        return rows

    monkeypatch.setattr(queries, "load_chunks", load_chunks)
    monkeypatch.setattr(queries, "load_neighbors", load_neighbors)
    filters = RetrievalFilters(tickers=["AAPL"], fiscal_years=[2024])

    passages = DocumentRetriever(object()).search("Apple services", filters=filters)

    assert observed_filters == [(2, 1)]
    assert [passage.chunk_index for passage in passages] == [3, 4, 5]
    assert passages[0].rank == 1 and not passages[0].is_neighbor
    assert passages[1].rank == 2 and not passages[1].is_neighbor
    assert passages[2].is_neighbor and passages[2].rank is None
