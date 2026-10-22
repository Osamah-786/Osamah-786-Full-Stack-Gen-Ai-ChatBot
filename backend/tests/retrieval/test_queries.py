from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from app.embeddings import DIMENSIONS
from app.retrieval.queries import full_text_search, semantic_search


class FakeScalars:
    def __init__(self, values):
        self.values = values

    def __iter__(self):
        return iter(self.values)


class FakeSession:
    def __init__(self, values=()):
        self.values = values
        self.statement = None

    def scalars(self, statement):
        self.statement = statement
        return FakeScalars(self.values)


def sql_for(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_semantic_search_uses_local_vector_column_and_metadata_filters() -> None:
    chunk_id = UUID(int=1)
    session = FakeSession([chunk_id])

    result = semantic_search(
        session,
        [0.0] * DIMENSIONS,
        tickers=["aapl"],
        fiscal_years=[2024],
        filing_types=["10-k"],
    )

    sql = sql_for(session.statement)
    assert result == [chunk_id]
    assert "embedding_384 <=>" in sql
    assert "source_documents.ticker IN" in sql
    assert "source_documents.fiscal_year IN" in sql
    assert "source_documents.filing_type IN" in sql
    assert session.statement._limit_clause.value == 50


def test_full_text_search_uses_postgres_websearch_and_rank() -> None:
    chunk_id = UUID(int=1)
    session = FakeSession([chunk_id])

    result = full_text_search(session, 'Apple "services revenue"')

    sql = sql_for(session.statement)
    assert result == [chunk_id]
    assert "websearch_to_tsquery" in sql
    assert "search_vector @@" in sql
    assert "ts_rank_cd" in sql


def test_search_handles_blank_text_and_rejects_wrong_vector_dimension() -> None:
    session = FakeSession()

    assert full_text_search(session, "  ") == []
    assert session.statement is None
    with pytest.raises(ValueError, match="384 dimensions"):
        semantic_search(session, [0.0, 1.0])
