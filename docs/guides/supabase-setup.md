# Supabase setup

We use Supabase for **Postgres** (users, chats, source documents, chunks, embeddings, and citations) and **Auth** (email sign-in only). You need one hosted Supabase project before wiring up `backend/` and `frontend/`.

## 1. Create an account

1. Go to [supabase.com](https://supabase.com) and sign up (GitHub or email).
2. Confirm your email if prompted.
3. You land in the [dashboard](https://supabase.com/dashboard). The free tier is enough for local development.

## 2. Create a project

1. Open [New project](https://supabase.com/dashboard/new).
2. Pick your organization (a personal org is created automatically on first signup).
3. Set a **project name** (e.g. `Document Copilot`).
4. Choose a **database password** — save it somewhere safe; you need it for direct DB access and `supabase link`.
5. Pick a **region** close to you.
6. Click **Create new project** and wait until the dashboard reports it is ready.

## 3. Collect credentials

The running app reads the following exact variable names. Store private credentials only in `backend/.env`; `frontend/.env` is compiled into browser-visible code.

| Value | Where to find it | Used by |
| ----- | ---------------- | ------- |
| **Project URL** | Dashboard → **Project Settings** → **API** → Project URL | Frontend + backend |
| **anon (public) key** | Same page → `anon` `public` key | Frontend (browser-safe) |
| **service_role (secret) key** | Same page → `service_role` `secret` key | Backend only — never expose to the browser |
| **Project ref** | Dashboard URL `supabase.com/dashboard/project/<ref>` | Identifying the project in dashboard/database settings |
| **Direct database connection string** | Dashboard → **Project Settings** → **Database** → Connection string | Alembic migrations and backend DB access |
| **Database password** | What you set at project creation | Direct Postgres connection |

Backend variable mapping: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and `DATABASE_URL`. Frontend mapping: `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`. Also configure `VITE_API_BASE_URL` for the backend origin. Copy safe placeholders from `backend/.env.example` and `frontend/.env.example`; do not print or commit real values.

Keep `service_role` out of git, client bundles, and frontend env files.

## 4. Auth settings (email only)

This app uses email auth only — no Google/SSO.

1. Dashboard → **Authentication** → **Providers**.
2. Leave **Email** enabled.
3. For local dev, you may want **Authentication** → **Email** → disable "Confirm email" so sign-up works without inbox access (re-enable for production).

## 5. Database schema management

Document Copilot uses Alembic from the Python backend to manage database schema. Do not create production tables manually in the Supabase dashboard.

Alembic migrations create and update:

- the `vector` extension for `pgvector`
- source document and chunk tables
- embedding columns
- generated full-text search columns
- HNSW and GIN indexes
- chat and citation tables
- row-level security policies

Use the direct/session database connection string for Alembic and SQLAlchemy. Do not use the transaction pooler connection string for migrations. The configured current migrations create `users`, `source_documents`, `document_chunks`, `chat_threads`, `chat_messages`, and `message_citations`, including pgvector/full-text indexes and RLS policies.

From `backend/`:

```bash
uv run alembic upgrade head
```

See [Backend setup](backend-setup.md) for the Alembic workflow.

## Next steps

- [Backend setup](backend-setup.md) — Python service + Supabase client
- [Frontend setup](frontend-setup.md) — React app + `@supabase/supabase-js`
