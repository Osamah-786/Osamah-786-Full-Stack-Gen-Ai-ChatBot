from datetime import date
from uuid import UUID

from app.assistant.outputs import Citation, GroundedAnswer
from app.chat import orchestrator
from app.retrieval.retriever import RetrievedPassage


def test_orchestrator_retrieves_validates_and_returns_trusted_citations(monkeypatch):
    passage = RetrievedPassage(
        chunk_id=UUID(int=1),
        source_document_id=UUID(int=2),
        chunk_index=0,
        text="Operating cash flow was $10 million.",
        page_number=8,
        section="Cash Flows",
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

    class SessionFactory:
        def __call__(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

    class Retriever:
        def __init__(self, *_args, **_kwargs):
            pass

        def search(self, _query):
            return [passage]

    monkeypatch.setattr(orchestrator, "get_session_factory", SessionFactory)
    monkeypatch.setattr(orchestrator, "DocumentRetriever", Retriever)
    monkeypatch.setattr(
        orchestrator,
        "run_agent",
        lambda _prompt, _deps: GroundedAnswer(
            answer="Cash flow was $10 million. [1]",
            citations=[Citation(citation_index=1, chunk_id=passage.chunk_id, excerpt="$10 million")],
        ),
    )

    prepared = orchestrator.prepare_turn("What was cash flow?", "user", UUID(int=3))
    assert prepared.result.answer == "Cash flow was $10 million. [1]"
    assert prepared.citations[0]["source_url"] == passage.source_url
