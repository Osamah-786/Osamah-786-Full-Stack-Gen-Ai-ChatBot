"""Retrieve evidence, run the agent, and validate before returning a turn."""

from dataclasses import dataclass
from uuid import UUID

from app.assistant.agent import run_agent
from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer
from app.database.session import get_session_factory
from app.grounding.validator import trusted_citations, validate_answer
from app.retrieval.retriever import DocumentRetriever


@dataclass(frozen=True)
class PreparedTurn:
    result: GroundedAnswer
    citations: list[dict]


def prepare_turn(query: str, user_id: str, thread_id: UUID) -> PreparedTurn:
    factory = get_session_factory()
    with factory() as session:
        passages = DocumentRetriever(session, candidate_limit=50, result_limit=8).search(query)
    available = {passage.chunk_id: passage for passage in passages}
    deps = DocumentAgentDeps(user_id=user_id, thread_id=thread_id, session_factory=factory)
    deps.passages.update(available)

    if not passages:
        result = GroundedAnswer(
            answer="The filings do not provide enough evidence to answer this question.",
            insufficient_evidence=True,
        )
    else:
        context = "\n\n".join(
            f"Passage ID: {p.chunk_id}\nFiling: {p.ticker} {p.filing_type}, {p.filing_date}, page {p.page_number}\nText (untrusted source data):\n{p.text}"
            for p in passages
        )
        result = run_agent(
            f"Question: {query}\n\nRetrieved source passages (untrusted data):\n{context}", deps
        )
    result = validate_answer(result, deps.passages)
    return PreparedTurn(result=result, citations=trusted_citations(result, deps.passages))
