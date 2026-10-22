# Backend setup

The checked-in FastAPI backend is already scaffolded. Install its declared dependencies with `uv`; do not reinitialize the project or rerun `uv add` for the packages in `pyproject.toml`.

## Configure and run

From the repository root:

```powershell
if (!(Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

Fill the backend `.env` with Supabase API credentials, a direct/session Postgres `DATABASE_URL`, Groq API key, and allowed frontend origin. Keep secrets local. Then:

```powershell
Set-Location backend
uv sync
uv run uvicorn app.main:app --reload
```

Open `http://localhost:8000/health` for the health route and `/docs` for FastAPI's generated API docs. The ASGI object is named `app`, so the correct target is `app.main:app` (lowercase).

## Migrations

Alembic configuration and `env.py` already exist. From `backend/`, apply reviewed migrations with:

```powershell
uv run alembic upgrade head
```

`DATABASE_URL` must use Supabase's direct/session connection, not the transaction pooler. Special characters in the password must be URL encoded. When schema models change, update SQLAlchemy models and create/review a migration; never make untracked dashboard schema edits.

## Tests and lint

```powershell
uv run pytest -m "not integration"
uv run ruff check .
```

Run targeted tests while changing a specific module. Integration tests may require real credentials and are not run by the default command.

## Ingestion

From `backend/`, `uv run python -m ingest.load_source_documents` delegates to the source importer in `data/`. Chunk operations are `uv run python -m ingest.load_document_chunks --dry-run`, `--pilot`, or `--all`. The latter modes read/write the configured database and embeddings; inspect [the ingestion guide](../INGESTION_AND_RETRIEVAL.md) before running them. `--all` should not be run against production without explicit authorization.
