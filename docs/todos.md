# Document Copilot — implementation checklist

Work top to bottom. Each phase unlocks the next. Check items off as you go.

## Where to start: backend, frontend, or both?

**Start with foundation, then backend-led vertical slices.** This describes the original build sequence; use the phase checkboxes and current architecture docs for implementation/verification status.

| Order | Why |
| ----- | --- |
| 1. Supabase + sample data | Everything persists here; you need a project and a corpus to test against. |
| 2. Backend schema + migrations | Auth, chat, retrieval, and citations all depend on the data model. |
| 3. Thin vertical slices | Wire auth, then streaming chat, then grounded retrieval — each slice touches frontend + backend together. |
| 4. Frontend in parallel (lightly) | Scaffold the SPA early, but don't build citation UI or chat polish until the backend can return real grounded answers. |

The critical path is **data model → ingestion → retrieval → LLM → citations**. The frontend is mostly a streaming chat shell with auth and citation display — it shouldn't get far ahead of working APIs.

---

## Phase 0 — Prerequisites & foundation

- [x] Install toolchain: Python 3.12+, `uv`, Node 20+, `pnpm` (see [README](../README.md))
- [x] Create Supabase project and collect credentials ([supabase-setup](guides/supabase-setup.md))
- [x] Create Groq API key for chat (needed from Phase 6 onward); embeddings run locally
- [ ] Set a real contact `USER_AGENT` in `data/download.py` and download sample 10-K corpus:
  ```bash
  uv run data/download.py
  ```
- [x] Confirm `data/downloads/manifest.json` lists AAPL, MSFT, NVDA, AMZN, GOOGL filings (2021–2025)

---

## Phase 1 — Backend scaffold & database

Goal: a running FastAPI service with a migrated Supabase schema.

- [x] Init backend deps and project layout ([backend-setup](guides/backend-setup.md))
- [x] `app/config.py` — settings module, fail fast on missing env vars
- [x] `app/main.py` — FastAPI app, CORS, health check (`GET /health`)
- [x] SQLAlchemy models in `app/database/models/`:
  - [x] `users`
  - [x] `source_documents`
  - [x] `document_chunks` (embedding + generated `tsvector`)
  - [x] `chat_threads`
  - [x] `chat_messages`
  - [x] `message_citations`
- [x] Alembic init + first migration:
  - [x] `create extension if not exists vector`
  - [x] `vector(1536)` embedding column
  - [x] Add `embedding_384 vector(384)` and HNSW index for local model vectors (migration `0002_local_embeddings`)
  - [x] generated `tsvector` column on chunks
  - [x] HNSW index (vector) + GIN index (full-text)
  - [x] RLS policies (users see only their own chats)
- [x] `uv run alembic upgrade head` against Supabase direct connection (owner reported successful application of migration `0002_local_embeddings`)
- [x] `app/database/supabase.py` — user-scoped and service-role clients
- [ ] Verify: `uv run uvicorn app.main:app --reload` → health check returns 200

---

## Phase 2 — Auth (full stack)

Goal: analysts can sign in with email; backend rejects unauthenticated requests.

**Backend**

- [x] `app/auth/dependencies.py` — verify `Authorization: Bearer <supabase_jwt>`, expose `get_current_user`
- [x] Reject missing/expired tokens with `401` before any chat or retrieval work (`get_current_user` dependency)

**Frontend**

- [x] Scaffold Vite + React + TypeScript frontend ([frontend-setup](guides/frontend-setup.md)); Tailwind is declared but not used by current styles, and shadcn/ui is not installed
- [x] `src/lib/env.ts` — validate `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- [x] `src/lib/supabase.ts` — browser Supabase client
- [x] `src/lib/http.ts` + `src/lib/api.ts` — fetch wrapper with automatic bearer token
- [x] Sign-in / sign-up pages (email only, no SSO)
- [x] Protected routes — redirect unauthenticated users to login
- [ ] Verify: sign up, sign in, token reaches backend on a test authenticated endpoint

---

## Phase 3 — Chat shell (vertical slice)

Goal: end-to-end chat UI streaming from FastAPI, no real retrieval yet.

**Backend**

- [x] Chat thread CRUD: list threads, create thread, load message history
- [x] `POST /chat/stream` — accepts UI-message-shaped requests and streams grounded answer/citation events (custom SSE client; Vercel AI SDK package is not installed)
- [x] Persist user + assistant messages to `chat_messages` after stream completes
- [x] `403` when user accesses another user's thread

**Frontend**

- [x] React Router: login, chat list, chat thread routes
- [x] Custom frontend SSE client pointed at `POST /chat/stream` with Supabase bearer token
- [x] Thread sidebar (past conversations)
- [x] Basic message list + input + streaming indicator
- [ ] Verify: create thread, send message, see streamed stub response, reload and see history

---

## Phase 4 — Ingestion pipeline

Goal: SEC filings in the corpus are parsed, chunked, embedded, and stored in Supabase.

- [x] `ingest/` scripts (or CLI entrypoint) for one-off corpus loading
- [x] HTML → normalized Markdown extraction via Docling (year folders and filing manifest metadata)
- [ ] Preserve page/section metadata through extraction where the source provides it
- [x] Docling HybridChunker with 254-token embedding cap, chunk index, page/section when available, and filing metadata; no explicit overlap parameter is configured
- [x] Write `source_documents` rows with filing metadata from `manifest.json`
- [x] Write `document_chunks` rows with text + metadata (pilot verified)
- [x] Local `all-MiniLM-L6-v2` embeddings → store `vector(384)` per chunk in `embedding_384` (one-chunk pilot verified)
- [x] Generated `tsvector` populated for full-text search (pilot verified)
- [x] Idempotent re-run (skip chunks whose text, metadata, model, and vector are current)
- [x] Unit tests: metadata extraction, embedding provenance, and current-chunk detection
- [ ] Unit tests: Docling chunking and token-limit behavior
- [ ] Run ingestion on full sample corpus (25 filings × 5 companies)
- [ ] Verify: chunks exist in Supabase; spot-check a known passage (e.g. Apple revenue mix table)

---

## Phase 5 — Retrieval

Goal: a user question returns ranked, relevant source passages.

- [x] `retrieval/queries.py` — pgvector semantic search over `document_chunks`
- [x] `retrieval/queries.py` — Postgres full-text search over `search_vector`
- [x] `retrieval/fusion.py` — Reciprocal Rank Fusion in Python
- [x] `retrieval/retriever.py` — query → fused ranked passages + neighbor chunks
- [x] Unit tests: query construction, fusion ranking, and retriever ordering (mock DB)
- [ ] Integration test (optional, `@pytest.mark.integration`): real query against ingested corpus
- [ ] Verify: test queries from [client-brief](client-brief.md) return relevant chunks (manual or scripted)

---

## Phase 6 — LLM agent & grounding

Goal: grounded answers with enforced citations — the core product contract.

- [x] `assistant/instructions.md` — product contract (cite everything, refuse to invent, no stock picks)
- [x] PydanticAI agent with typed deps (`DocumentAgentDeps`) and output (`GroundedAnswer`)
- [x] Agent tools: `search_filings`, `read_chunk`, `read_surrounding_chunks`
- [x] `chat/orchestrator.py` — one turn: retrieve → agent → validate → stream → persist
- [x] `grounding/validator.py` — every citation maps to a retrieved passage; fail closed on violation
- [x] `chat/streaming.py` — AI SDK-compatible stream (text deltas + citation metadata parts)
- [x] Persist `message_citations` linked to assistant messages
- [x] Unit tests: citation validation, grounding enforcement, message conversion
- [ ] Verify against [client-brief example questions](client-brief.md#example-analyst-questions):
  - [ ] Answers cite specific filings and pages
  - [ ] Under-specified questions get "not enough evidence" responses
  - [ ] Question 10 (generative AI margins) refuses to infer beyond filings

---

## Phase 7 — Trust UI (citations & source passages)

Goal: analysts can verify every claim in one click — this is what makes the product usable.

- [x] Citation chips/links on assistant messages (company, filing type, date, page/section)
- [x] Source passage panel — show underlying excerpt for selected citation
- [x] Empty states (no threads, no corpus match)
- [x] Error states (auth expired, retrieval failure, grounding failure, network/CORS)
- [x] Loading/streaming status during assistant run
- [ ] Verify: click a citation → see the exact passage from the filing

---

## Phase 8 — Pilot readiness

Goal: 5 senior analysts can use it for a week and report ≥3 hours saved per analyst per week.

- [x] README "Running locally" section — copy-paste commands for backend + frontend + env vars
- [x] Document how to ingest/update the corpus
- [ ] Smoke-test all 10 example questions from the client brief
- [ ] Confirm chat history persists across sessions
- [ ] Confirm ~40-user scale assumptions (no hardcoded single-user shortcuts)
- [ ] Basic structured logging on backend (`structlog`) for debugging failed turns
- [ ] Review latency: streaming starts within a few seconds for typical queries

---

## Phase 9 — Deployment (Railway)

- [ ] Railway: backend service (Uvicorn, env vars, `ALLOWED_ORIGINS`)
- [ ] Railway: frontend service (Vite build, `VITE_*` env vars at build time)
- [ ] Supabase: re-enable email confirmation for production if disabled during dev
- [ ] Run `alembic upgrade head` against production Supabase (direct connection)
- [ ] Run ingestion against production database
- [ ] End-to-end test on deployed URLs with a real Driftwood-style email account

---

## Quick reference

| Doc | Purpose |
| --- | ------- |
| [client-brief.md](client-brief.md) | What Driftwood needs and example questions |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, data model, streaming contract |
| [REQUEST_LIFECYCLE.md](REQUEST_LIFECYCLE.md) | Query request and response flow through frontend/backend |
| [INGESTION_AND_RETRIEVAL.md](INGESTION_AND_RETRIEVAL.md) | Corpus ingestion, embeddings, database writes, and search |
| [guides/supabase-setup.md](guides/supabase-setup.md) | Hosted Postgres + Auth |
| [guides/backend-setup.md](guides/backend-setup.md) | FastAPI + Alembic commands |
| [guides/frontend-setup.md](guides/frontend-setup.md) | Vite + React setup and checks |
