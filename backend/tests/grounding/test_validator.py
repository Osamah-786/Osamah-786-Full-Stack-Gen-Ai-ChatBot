from datetime import date
from uuid import UUID

import pytest

from app.assistant.outputs import Citation, GroundedAnswer
from app.grounding.validator import GroundingError, trusted_citations, validate_answer
from app.retrieval.retriever import RetrievedPassage


@pytest.fixture
def passage() -> RetrievedPassage:
    return RetrievedPassage(
        chunk_id=UUID(int=1),
        source_document_id=UUID(int=2),
        chunk_index=0,
        text="Revenue increased 10 percent in fiscal 2024.",
        page_number=4,
        section="Results",
        ticker="ABC",
        company_name="ABC Corp",
        filing_type="10-K",
        filing_date=date(2025, 2, 1),
        fiscal_year=2024,
        accession_number="0000000000-25-000001",
        source_url="https://example.test/filing",
        rank=1,
        score=0.5,
        is_neighbor=False,
    )


def test_valid_exact_excerpt_and_trusted_metadata(passage):
    result = GroundedAnswer(
        answer="Revenue rose 10 percent. [1]",
        citations=[Citation(citation_index=1, chunk_id=passage.chunk_id, excerpt="Revenue increased 10 percent")],
    )
    validated = validate_answer(result, {passage.chunk_id: passage})
    assert validated == result
    assert trusted_citations(validated, {passage.chunk_id: passage})[0]["source_url"] == passage.source_url


@pytest.mark.parametrize(
    "citation",
    [
        Citation(citation_index=1, chunk_id=UUID(int=3), excerpt="Revenue increased"),
        Citation(citation_index=1, chunk_id=UUID(int=1), excerpt="Revenue doubled"),
    ],
)
def test_rejects_unavailable_or_fabricated_citation(passage, citation):
    result = GroundedAnswer(answer="Revenue rose. [1]", citations=[citation])
    with pytest.raises(GroundingError):
        validate_answer(result, {passage.chunk_id: passage})


def test_rejects_missing_marker_and_allows_explicit_no_evidence():
    with pytest.raises(GroundingError):
        validate_answer(
            GroundedAnswer(
                answer="Revenue rose.",
                citations=[Citation(citation_index=1, chunk_id=UUID(int=1), excerpt="Revenue")],
            ),
            {UUID(int=1): object()},
        )
    result = GroundedAnswer(
        answer="The filings do not provide enough evidence to answer this question.",
        insufficient_evidence=True,
    )
    assert validate_answer(result, {}) == result
