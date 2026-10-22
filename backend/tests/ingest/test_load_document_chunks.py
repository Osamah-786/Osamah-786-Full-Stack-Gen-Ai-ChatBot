from types import SimpleNamespace

from app.embeddings import DIMENSIONS, MODEL_NAME
from ingest.load_document_chunks import chunk_is_current, make_chunk_metadata


def test_make_chunk_metadata_contains_filing_and_embedding_provenance() -> None:
    filing = {
        "ticker": "AAPL",
        "form": "10-K",
        "filing_date": "2021-10-29",
        "report_date": "2021-09-25",
        "accession_number": "0000320193-21-000105",
    }

    metadata = make_chunk_metadata(
        filing,
        "2021/aapl.md",
        "Item 1 > Business",
        ["Item 1", "Business"],
        "Apple revenue",
        MODEL_NAME,
        DIMENSIONS,
    )

    assert metadata["ticker"] == "AAPL"
    assert metadata["fiscal_year"] == 2021
    assert metadata["accession_number"] == filing["accession_number"]
    assert metadata["embedding_dimensions"] == DIMENSIONS
    assert metadata["content_hash"]


def test_chunk_is_current_only_when_text_model_and_vector_match() -> None:
    text = "Apple revenue"
    metadata = make_chunk_metadata(
        {
            "ticker": "AAPL",
            "form": "10-K",
            "filing_date": "2021-10-29",
            "report_date": "2021-09-25",
            "accession_number": "0000320193-21-000105",
        },
        "2021/aapl.md",
        None,
        [],
        text,
        MODEL_NAME,
        DIMENSIONS,
    )
    chunk = {
        "chunk_text": text,
        "page_number": None,
        "section": None,
        "token_count": 3,
        "chunk_metadata": metadata,
    }
    row = SimpleNamespace(**chunk, embedding_384=[0.0] * DIMENSIONS)

    assert chunk_is_current(row, chunk, MODEL_NAME, DIMENSIONS)
    assert not chunk_is_current(
        row, {**chunk, "token_count": 4}, MODEL_NAME, DIMENSIONS
    )
    assert not chunk_is_current(row, chunk, "different-model", DIMENSIONS)
