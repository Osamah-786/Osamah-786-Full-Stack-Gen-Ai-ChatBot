# Frontend setup

The React/Vite SPA already exists in `frontend/`. It uses React Router, Supabase JS, native `fetch`, and CSS. No Vercel AI SDK, shadcn component set, or frontend test runner is present in the current implementation.

## Configure and run

From repository root:

```powershell
if (!(Test-Path frontend/.env)) { Copy-Item frontend/.env.example frontend/.env }
Set-Location frontend
pnpm install
pnpm dev
```

Set `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_ANON_KEY` in `frontend/.env`. These variables are public in the built browser bundle; only the Supabase anon/public key is allowed there. Never add Groq, service-role, or database credentials.

## Checks

Run from `frontend/`:

```powershell
pnpm lint
pnpm build
```

The build includes TypeScript compilation (`tsc -b`) and Vite bundling. Verify auth and chat interactions manually in a browser configured to the same local backend CORS origin.

## Request integration

`src/lib/api.ts` sends the user's Supabase access token to the FastAPI backend and parses SSE events from `POST /chat/stream`. Route and message types must match `backend/app/api/chat.py`; stream event names must match `backend/app/chat/streaming.py`. See [request lifecycle](../REQUEST_LIFECYCLE.md).
