# Backend agent instructions

Read the [repository instructions](../AGENTS.md) first. This file adds backend-specific rules and reflects the current implementation; use [backend README](README.md) and [architecture docs](../docs/ARCHITECTURE.md) for navigation.

## Stack and layout

- Python 3.12+, `uv`, FastAPI/Uvicorn, Pydantic v2/settings, PydanticAI, OpenAI-compatible SDK configured for Groq, Supabase Python client, SQLAlchemy/psycopg/Alembic, pgvector, Sentence Transformers, and Docling.
- Runtime packages live under `app/`: API routes, auth, assistant, chat orchestration/streaming, database clients/models/persistence, embeddings, retrieval, and grounding.
- `ingest/` contains command-line entry points; `tests/` contains offline pytest coverage.
- There is no distinct `services/` or `repositories/` layer, no HTTP ingest route, and no standalone BM25/reranker implementation. Inspect callers before adding modules.

## Configuration and secrets

- `app/config.py` is the single backend settings source. Do not add direct `os.getenv` or dotenv reads in application modules.
- `.env.example` contains placeholders only; actual keys/URLs belong in ignored `.env`.
- Never expose/log Groq, Supabase service-role, database credentials, user messages, or source excerpts.
- Frontend must never receive backend-only credentials.

## Database and embedding safety

- SQLAlchemy metadata is in `app/database/models/`; Alembic migrations under `alembic/versions/` are the schema source of truth. Review migrations, especially pgvector indexes and RLS policies.
- Use the Supabase direct/session Postgres connection for Alembic; not the transaction pooler.
- Existing vectors use `document_chunks.embedding vector(1536)` (legacy) and `embedding_384 vector(384)` (current). Runtime ingestion and retrieval use `embedding_384`.
- Current local encoder is `sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions, maximum ingestion chunk size 254 tokenizer tokens. Never change model or dimensions without a data/migration and re-embedding plan.
- Do not run full ingestion, live provider calls, production migrations, or production DB writes unless the task explicitly authorizes them.

## Commands

Run from `backend/`:

```powershell
uv sync
uv run uvicorn app.main:app --reload
uv run pytest -m "not integration"
uv run ruff check .
uv run alembic upgrade head
```

Chunk CLI: `uv run python -m ingest.load_document_chunks` with one of `--dry-run`, `--pilot`, or `--all`. `--all` writes to the configured database. Source document importer is `uv run python -m ingest.load_source_documents` (delegates to `data/import_source_documents.py`).

## Change and verification rules

- Preserve HTTP routes, payload names, stream event names, and citation trust guarantees unless the task changes their contract. Check frontend `src/lib/api.ts` when editing request/stream shapes.
- Retrieval unit tests and grounding tests should not access live DB/Groq. Keep integration work explicitly marked.
- Inspect existing ingestion/retrieval/model implementations before creating duplicates. Prefer the smallest change, avoid dependencies, and report unverified database/provider behavior honestly.
