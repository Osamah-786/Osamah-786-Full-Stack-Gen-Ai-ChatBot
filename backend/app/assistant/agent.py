"""PydanticAI agent configured for the project's Groq-compatible endpoint."""

from functools import lru_cache
from pathlib import Path
from uuid import UUID

from pydantic_ai import Agent, RunContext, UsageLimits
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer
from app.retrieval.retriever import DocumentRetriever, RetrievalFilters, RetrievedPassage

_INSTRUCTIONS = Path(__file__).with_name("instructions.md").read_text(encoding="utf-8")


def _passage_data(passage: RetrievedPassage) -> dict:
    return passage.model_dump(mode="json")


def build_agent(model: Model | str | None = None) -> Agent[DocumentAgentDeps, GroundedAnswer]:
    agent: Agent[DocumentAgentDeps, GroundedAnswer] = Agent(
        model,
        deps_type=DocumentAgentDeps,
        output_type=GroundedAnswer,
        instructions=_INSTRUCTIONS,
        retries=1,
    )

    @agent.tool
    def search_filings(
        ctx: RunContext[DocumentAgentDeps],
        query: str,
        tickers: list[str] | None = None,
        fiscal_years: list[int] | None = None,
        filing_types: list[str] | None = None,
    ) -> list[dict]:
        """Search SEC filings with hybrid semantic and PostgreSQL full-text retrieval."""
        with ctx.deps.session_factory() as session:
            results = DocumentRetriever(session, candidate_limit=30, result_limit=5).search(
                query[:1000],
                filters=RetrievalFilters(
                    tickers=(tickers or [])[:10],
                    fiscal_years=(fiscal_years or [])[:10],
                    filing_types=(filing_types or [])[:10],
                ),
            )
        ctx.deps.passages.update({passage.chunk_id: passage for passage in results})
        return [_passage_data(passage) for passage in results]

    @agent.tool
    def read_chunk(ctx: RunContext[DocumentAgentDeps], chunk_id: UUID) -> dict | None:
        """Read one filing chunk by its ID."""
        with ctx.deps.session_factory() as session:
            passage = DocumentRetriever(session).read_chunk(chunk_id)
        if passage is None:
            return None
        ctx.deps.passages[passage.chunk_id] = passage
        return _passage_data(passage)

    @agent.tool
    def read_surrounding_chunks(
        ctx: RunContext[DocumentAgentDeps], chunk_id: UUID
    ) -> list[dict]:
        """Read the adjacent filing chunks around a known passage."""
        with ctx.deps.session_factory() as session:
            results = DocumentRetriever(session).read_surrounding_chunks(chunk_id, window=1)
        ctx.deps.passages.update({passage.chunk_id: passage for passage in results})
        return [_passage_data(passage) for passage in results]

    return agent


@lru_cache(maxsize=1)
def get_agent() -> Agent[DocumentAgentDeps, GroundedAnswer]:
    from app.config import settings

    model = OpenAIChatModel(
        settings.groq_chat_model,
        provider=OpenAIProvider(
            base_url=settings.groq_base_url,
            api_key=settings.groq_api_key.get_secret_value(),
        ),
    )
    return build_agent(model)


def run_agent(
    prompt: str,
    deps: DocumentAgentDeps,
    *,
    agent: Agent[DocumentAgentDeps, GroundedAnswer] | None = None,
) -> GroundedAnswer:
    run = (agent or get_agent()).run_sync(
        prompt,
        deps=deps,
        usage_limits=UsageLimits(request_limit=4, tool_calls_limit=3),
    )
    return run.output
