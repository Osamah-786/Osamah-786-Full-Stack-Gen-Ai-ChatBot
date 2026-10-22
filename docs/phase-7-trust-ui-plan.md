# Phase 7 — Trust UI Implementation Plan

> **Status:** The current frontend now types and parses `data-citations`, renders citation controls and a source excerpt panel, and distinguishes several error/loading/empty states. This document is the original implementation plan; verify click-through and reload behavior manually before treating its last acceptance item as complete. See [todos.md](todos.md).

## Goal

Make each answer verifiable in the chat: analysts can connect an answer citation to its filing, date, page or section, and exact supporting excerpt. The UI should also explain empty, loading, authentication, retrieval, grounding, and network states without presenting unsupported content as trustworthy.

## Current state

- `frontend/src/pages/ChatWorkspace.tsx` already has the conversation sidebar, empty-thread screens, a basic message list, a streaming indicator, and a generic error message.
- `frontend/src/lib/api.ts` parses `text-delta` and `data-citations` events, validates citation entries, and reloads history after success.
- The frontend message type includes typed citation data.
- Assistant citation markers are interactive controls and the source panel displays filing metadata, excerpt, and a validated SEC link.
- `frontend/src/lib/http.ts` defines `ApiError` for ordinary JSON requests. Streaming uses its own `fetch` path in `api.ts` and maps stream/network failures to `ApiError` instances there.
- Phase 6 sends citation metadata as a `data-citations` stream part and persists the same part with the assistant message. Each citation currently includes `citation_index`, `document_chunk_id`, `excerpt`, `ticker`, `company_name`, `filing_type`, `filing_date`, `page_number`, `section`, and `source_url`.
- `GET /chat/threads/{thread_id}/messages` returns persisted message content, including the stored citation part. No schema change or new source-passage endpoint is required for the current excerpt display requirement.

## Data and UI contract

Extend the frontend message-part type to a small discriminated union:

```ts
type Citation = {
  citation_index: number
  document_chunk_id: string
  excerpt: string
  ticker: string
  company_name: string
  filing_type: string
  filing_date: string
  page_number: number | null
  section: string | null
  source_url: string
}

type MessagePart =
  | { type: 'text'; text: string }
  | { type: 'data-citations'; data: Citation[] }
```

Treat all fetched and streamed data as untrusted at the UI boundary. Validate the citation array before rendering: require a positive integer index, a nonempty excerpt and document ID, and expected metadata types. Ignore malformed citation entries while keeping the answer text visible; show a clear unavailable-source state if the analyst opens a citation whose metadata is incomplete. Never construct HTML from answer text or excerpt content.

## Original implementation steps

### 1. Carry citation data through the stream and history

Update `frontend/src/lib/api.ts` to recognize `data-citations` events and expose them to `ChatWorkspace.tsx`, alongside text deltas. Keep the existing POST URL, Supabase bearer-token behavior, and request body. Add narrow stream-error parsing for:

- non-2xx response details, including expired auth;
- backend `error` events;
- a stream that ends before `[DONE]`;
- fetch/network failures and malformed event payloads.

Do not install the Vercel AI SDK just for this UI: the project currently uses its own SSE reader and the backend already emits the needed protocol parts.

Merge incoming citation parts into the in-flight assistant message without replacing its accumulated text. Keep the post-success history reload so the displayed conversation reflects persisted messages. Handle a missing citation part as a valid case for an explicit insufficient-evidence answer.

### 2. Make answer references clickable

In `ChatWorkspace.tsx`, separate text parts from citation data parts. Render answer text safely and convert only known `[n]` markers into buttons/links using the matching citation index. Keep unknown or malformed markers as plain text. If a citation is present but the answer contains no visible marker, render a compact citation list beneath that assistant answer so the source remains reachable.

Each citation control should have an accessible name containing the company, filing type, date, and page/section when present. It must work with keyboard focus and activation, expose selected state, and open the corresponding source passage in the panel.

### 3. Add the source passage panel

Add a small citation detail panel within the existing chat workspace. Selecting a citation shows:

- company and ticker;
- filing type and filing date;
- page and section when available;
- the exact verified excerpt from the citation;
- a link to `source_url`, opening in a new tab with safe `rel` attributes.

The selected citation should be identifiable from its message and index, and the panel should close with a button and Escape. On narrow screens, render it as a dismissible drawer or stacked panel so it does not squeeze the message area. Focus should move sensibly when it opens and return to the triggering citation when it closes.

The Phase 7 requirement is to show the cited excerpt, which Phase 6 already persists. Do not fetch or display entire filing documents in this phase; that would need a separate, explicitly scoped backend data contract.

### 4. Complete the trust states

Retain the existing no-conversation and no-message screens, but verify they remain useful when loading is complete and no data exists. Add a retrieval-specific no-match state for a successful answer that reports insufficient evidence; do not present it as a generic failure. Keep the existing new-chat action available.

Show differentiated, actionable errors:

- **Authentication:** session expired or unavailable; invite the user to sign in again.
- **Retrieval/service:** documents could not be searched; offer retry without implying the corpus had no match.
- **Grounding:** answer could not be verified; do not display partial or unvalidated answer text.
- **Persistence:** answer could not be saved; report that history may not retain it.
- **Network/CORS:** API could not be reached; distinguish this from a backend HTTP error where possible.
- **Message history:** history failed to load; keep the thread context and provide a retry control.

Keep messages, citations, and excerpts out of console logs. The API error text is useful for rendering but should not be copied into telemetry without redaction.

### 5. Polish streaming and citation behavior

Show the existing loading and streaming state during their correct lifecycle: loading history, waiting for a response, receiving text, and finalizing/persisting. Disable duplicate submissions while a turn is active. If the backend emits an error after text deltas because persistence failed, preserve the visible answer but clearly label the save failure; do not show a saved-state indicator.

When a new assistant result arrives, clear a previously selected citation if it belongs to another message. Selecting citations from older messages should continue to work after history reload.

### 6. Style within the current frontend

Use the existing `App.css` and current component structure. Add only the styles needed for citation controls, focus/selected states, the excerpt panel, and its responsive layout. Preserve the current light chat theme and existing layout. Avoid adding a UI framework or changing route/auth architecture.

## Likely files

- `frontend/src/lib/api.ts` — citation typing and SSE citation/error events.
- `frontend/src/pages/ChatWorkspace.tsx` — message citation rendering, selected source state, and empty/error/loading behavior.
- `frontend/src/App.css` — citation and source panel styles, responsive behavior, and visible focus states.

Keep changes in these files unless implementation reveals a concrete need for one small chat component. No backend, database schema, migration, or dependency change is expected.

## Verification plan

### Automated checks

- Run frontend lint and production build/type-check.
- Add focused tests if the frontend has a test runner; do not introduce one solely for this phase. At minimum, exercise a small pure citation parser/validator if it is extracted from the page.
- Verify stream parsing handles split network chunks, multiple events in one chunk, `data-citations`, `[DONE]`, malformed data, and backend error events.
- Verify answer rendering turns matching `[n]` markers into safe citation controls while preserving ordinary text, unknown markers, and newlines.
- Verify citation data remains attached to a message after the API history reload.

### Manual browser checks

1. Open a thread with an assistant response containing one citation; confirm company, filing, date, page/section, and excerpt.
2. Click the inline citation; confirm the matching source panel opens and the SEC source link works.
3. Use keyboard only to focus/open/close the citation panel and verify focus return.
4. Test several citations, repeated markers, and a response with no citations because evidence is insufficient.
5. Reload the page and open the same thread; citations and excerpts must still be present.
6. Test no threads, a new empty thread, no corpus match, expired auth, retrieval failure, grounding failure, persistence failure, and offline/network failure.
7. Test desktop and narrow viewport layouts; confirm the panel does not hide the answer or composer.

## Acceptance criteria

- Every valid citation marker can open its matching source details in one action.
- The panel shows metadata and the exact persisted excerpt, with a safe link to the source filing.
- Citation information survives send completion, history reload, and page reload.
- Missing/malformed citation metadata never creates a broken or misleading link.
- Insufficient evidence, loading, and failure states are visually and semantically distinct.
- Keyboard, screen-reader labels, focus visibility, and small-screen layout are usable.
- Frontend lint/build pass, and Phase 7 manual checks are recorded before checking off the verification item in `todos.md`.

## Out of scope

- Changes to retrieval ranking, LLM prompts, grounding policy, or chat persistence schema.
- Fetching whole filings or adding a new chunk-read endpoint.
- Replacing the existing SSE client with a new chat SDK.
- New design system, analytics, or unrelated chat features.
