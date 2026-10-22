# Frontend

The frontend is a browser-only React/TypeScript SPA built with Vite. It provides Supabase email sign-in, protected chat routes, thread history, a custom SSE reader, and citation/source display. It currently uses hand-authored CSS (`src/App.css`, `src/index.css`); Tailwind-related packages are listed but not wired into `vite.config.ts` or the styles, and shadcn is not installed despite older setup-plan references.

## Run and check

```powershell
pnpm install
pnpm dev
pnpm lint
pnpm build
```

`pnpm build` runs TypeScript project builds and Vite production build. No frontend test runner is installed. Configure `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_ANON_KEY` in `.env` using `.env.example`; all `VITE_*` variables are browser-visible. Never place Groq, service-role, or database credentials there.

## Runtime flow

`src/main.tsx` mounts `App`; `App.tsx` handles Supabase session state and route protection. `pages/SignInPage.tsx` and `SignUpPage.tsx` use the browser Supabase client. `pages/ChatWorkspace.tsx` loads threads/history and renders messages, streams answers through `lib/api.ts`, and opens the citation detail panel. JSON calls use `lib/http.ts`, which injects the session bearer token. Styling/theme is currently global CSS, not a component library.

## Folder map

| File | Purpose |
| --- | --- |
| `package.json` / `pnpm-lock.yaml` | Scripts, declared dependencies, and pinned pnpm resolution. |
| `vite.config.ts` | React Vite plugin and `@` source alias. |
| `tsconfig*.json` | TypeScript compiler configuration for app and tooling. |
| `eslint.config.js` | Frontend lint rules. |
| `.env.example` | Placeholder browser-safe configuration. |
| `index.html` | Vite document shell and root mount. |

- [`src/README.md`](src/README.md) — app entry, styles, and source tree.
- [`src/pages/README.md`](src/pages/README.md) — auth and chat routes.
- [`src/lib/README.md`](src/lib/README.md) — configuration, auth client, API and HTTP.
- [`src/assets/README.md`](src/assets/README.md) — imported static assets.
- [`public/README.md`](public/README.md) — static files served without bundling.

Compatibility boundary: request payloads and SSE event types must match `backend/app/api/chat.py` and `backend/app/chat/streaming.py`. Citation data comes from persisted message parts and is validated before display. No table result type or AI SDK package is currently installed.
