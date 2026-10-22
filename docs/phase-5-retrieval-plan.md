# Phase 5 — Retrieval Pipeline Plan

## Current state

> **Status:** The retrieval design in this plan is implemented in `backend/app/retrieval/queries.py`, `fusion.py`, and `retriever.py`; PydanticAI integration followed in Phase 6. This plan records the original choices. Verify corpus-wide relevance separately; it is not established by unit tests. The most recent transcript reports a full ingestion run stopped after four of 25 filings on an oversized chunk; the current loader contains a tokenizer-boundary split path, but the corpus was not re-run during the documentation audit.

- The current retriever embeds with `embed_query()` and uses `DocumentChunk.embedding_384` (384 dimensions), `search_vector`, and source filing metadata.
- The legacy `embedding` vector column is not used by current retrieval. HNSW and GIN indexes are declared in Alembic migrations.
- Phase 5 retrieval remains unit-testable independently of the agent/LLM, although Phase 6 now calls it.

## Original implementation sequence

### 1. Define the retrieval result

In `app/retrieval/retriever.py`, define the result shape used by later agent tools: chunk ID and text, source document ID, chunk index, page and section, company/ticker, filing type/date/year, accession number, source URL, and retrieval rank/score.

### 2. Implement the independent searches

In `app/retrieval/queries.py`, add two SQLAlchemy searches joining chunks to source documents:

- **Semantic search:** embed the question with `app.embeddings.embed_query()`, search `embedding_384` by cosine distance, and return ranked chunk IDs.
- **Lexical search:** use Postgres `websearch_to_tsquery('english', ...)` against `search_vector`, ordered by `ts_rank_cd`.

Both should accept optional ticker, fiscal-year, and filing-type filters. Use bound SQLAlchemy expressions, return stable IDs/ranks, and handle empty or stop-word-only lexical queries without failing.

### 3. Fuse the ranked results

In `app/retrieval/fusion.py`, implement pure Python Reciprocal Rank Fusion (RRF). Combine ranks rather than raw scores, since vector distance and Postgres text rank are on different scales. Start with `k=60`; keep deterministic tie-breaking and deduplicate by chunk ID.

The linked cookbook separates retriever helpers from fusion and uses RRF with `k=60`. Adapt that pattern by replacing BM25 with Postgres full-text search and retaining pgvector semantic search. [Retriever helpers](https://github.com/daveebbelaar/ai-cookbook/blob/main/knowledge/hybrid-retrieval/utils/retrievers.py) · [RRF helper](https://github.com/daveebbelaar/ai-cookbook/blob/main/knowledge/hybrid-retrieval/utils/fusion.py)

### 4. Compose retrieval and neighboring context

In `app/retrieval/retriever.py`:

1. Embed the query once.
2. Fetch candidates from both search paths (start with 50 per path).
3. Fuse the ranked IDs and select the top 10.
4. Load the selected chunks and source metadata.
5. Add adjacent chunks from the same source document (initially one before and after), deduplicating overlaps and returning them in document order.

Keep the selected hit's fused rank/score distinguishable from context-only neighbors. Do not add reranking in this phase; it is absent from the Phase 5 checklist and would add complexity and another model/service.

### 5. Keep the PydanticAI boundary ready for Phase 6

Expose retrieval as a typed, injectable dependency. In Phase 6, pass it through `DocumentAgentDeps` and register bounded tools such as `search_filings`, `read_chunk`, and `read_surrounding_chunks`. The agent should call these tools rather than generate SQL. PydanticAI supports explicit runtime dependencies and context-aware tools; retrieval itself remains testable without calling the LLM. [Dependencies](https://pydantic.dev/docs/ai/core-concepts/dependencies/) · [Tools](https://pydantic.dev/docs/ai/tools-toolsets/tools/)

### 6. Verify retrieval

- Unit-test RRF ordering, duplicates, ties, and empty rankings.
- Unit-test query construction and result mapping with mocked database sessions; verify the 384-dimensional query embedding is used and metadata filters are applied.
- Unit-test fused retrieval and neighbor deduplication/order.
- Add an optional `@pytest.mark.integration` test against Supabase; it must not call Groq.
- After the remaining corpus ingestion completes, check representative client-brief questions: Apple revenue mix, NVIDIA data-center demand, and multi-year comparisons. Confirm returned passages have correct filing metadata and page/section where available.

## Starting defaults

| Setting | Initial value |
| --- | ---: |
| Candidates per search | 50 |
| RRF constant | 60 |
| Fused passages | 10 |
| Neighbor chunks per selected hit | 1 before + 1 after |

Tune these only after checking the client-brief queries and the final prompt context budget.

## Expected files

- `backend/app/retrieval/queries.py`
- `backend/app/retrieval/fusion.py`
- `backend/app/retrieval/retriever.py`
- Targeted retrieval unit tests under `backend/tests/`

No schema migration or dependency addition is expected: the current model and migrations already define the vector and full-text search columns and indexes.
