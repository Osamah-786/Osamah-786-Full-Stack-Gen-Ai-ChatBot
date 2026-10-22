# Backend

FastAPI owns request authentication, chat orchestration, hybrid filing retrieval, grounded answer validation, and chat persistence. Run commands in this directory; `uv` uses `pyproject.toml` and the project environment.

## Local setup

```powershell
Copy-Item .env.example .env
# Fill placeholders in .env using the Supabase/Groq setup guides.
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

`GET /health` is a credential-free check. Open `http://localhost:8000/docs` for FastAPI's generated API reference. Use the direct/session Supabase Postgres URL in `DATABASE_URL` for Alembic and SQLAlchemy.

## Tests and lint

```powershell
uv run pytest -m "not integration"
uv run ruff check .
```

The pytest integration marker is reserved for tests requiring live Supabase or Groq credentials. Never run such tests against production without explicit task approval.

## Package map

| Path | Responsibility |
| --- | --- |
| `app/` | Runtime application; see [`app/README.md`](app/README.md). |
| `ingest/` | Corpus source/chunk CLI entry points; see [`ingest/README.md`](ingest/README.md). |
| `alembic/` | Database schema migrations; see [`alembic/README.md`](alembic/README.md). |
| `tests/` | Offline unit tests; see [`tests/README.md`](tests/README.md). |
| `pyproject.toml` | Dependencies, package build metadata, pytest config, and Ruff-compatible project setup. |
| `uv.lock` | Locked Python dependency resolution. |
| `.env.example` | Placeholder names and safe example configuration; copy to ignored `.env`. |
| `alembic.ini` | Alembic script/logging setup; DB URL is supplied from app settings. |

## Important boundaries

- Runtime configuration is centralized in `app/config.py`; modules should not read environment variables directly.
- `app/embeddings.py` is the shared 384-dimensional document/query embedding implementation. Keep model and vector-column dimensions aligned.
- `app/retrieval/` owns PostgreSQL vector/full-text searches and RRF; no external reranker currently exists.
- Schema changes require a reviewed Alembic migration. Do not use dashboard edits as the schema source of truth.
- Chat responses are text + citations + insufficient-evidence status. No structured result/table schema exists yet.
- Current `GROQ_GROUNDING_MODEL` and `RETRIEVAL_FTS_KEYWORD_MODEL` configuration entries are not used in the request path; the agent uses `GROQ_CHAT_MODEL`.
