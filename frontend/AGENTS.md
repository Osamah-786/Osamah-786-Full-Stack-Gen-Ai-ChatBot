# Frontend agent instructions

Read [repository instructions](../AGENTS.md) first. This is a Vite + React + strict TypeScript browser SPA, not Next.js. See [frontend README](README.md) and [architecture](../docs/ARCHITECTURE.md) for current implementation details.

## Current stack and conventions

- React, React Router, Supabase JS, Vite, TypeScript, ESLint, and hand-authored global CSS.
- Tailwind-related packages are listed as dependencies but are not wired into the Vite config or current styles, which use `src/App.css` and `src/index.css`; shadcn/ui components are not installed. Do not claim they exist or redesign styling tooling without a task requiring it.
- Package manager is pnpm; preserve `pnpm-lock.yaml` and `.npmrc` minimum-release-age policy.
- Use native `fetch` through `src/lib/http.ts` and `src/lib/api.ts`, not another HTTP client.
- Keep browser environment reads in `src/lib/env.ts`; every `VITE_*` value is public at build time.
- Keep Supabase Auth in the browser client, but never expose service-role, Groq, or direct database credentials.
- Do not add a frontend test runner unless explicitly requested; current verification is `pnpm lint` and `pnpm build` plus manual browser checks.

## API and trust contracts

- `ChatWorkspace` calls `api.streamChat()` for `POST /chat/stream`. Preserve `threadId`, message parts, bearer token, SSE `text-delta` and `data-citations` handling, and history reload behavior.
- Backend API paths/schemas are in `backend/app/api/chat.py`; stream framing is in `backend/app/chat/streaming.py`.
- Render assistant text as text, never inject HTML. Citation controls may only use valid `data-citations` entries; source links must remain HTTPS SEC URLs.
- Backend answer output has text/citations/insufficient-evidence only; do not invent a structured table payload in the UI.

## Commands

Run from `frontend/`:

```powershell
pnpm install
pnpm dev
pnpm lint
pnpm build
```

Before changing dependencies, check if native browser or existing React/CSS functionality is sufficient. Make the smallest change, preserve auth and responsive behavior, and avoid unrelated files.
