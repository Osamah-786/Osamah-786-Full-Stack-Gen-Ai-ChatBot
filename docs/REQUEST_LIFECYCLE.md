# Request Lifecycle

This describes the current chat request path from the React workspace through FastAPI and back to persisted UI history.

## Routes and request shape

Backend routes are registered by `backend/app/main.py` from `backend/app/api/chat.py`:

| Method and path | Authentication | Behavior |
| --- | --- | --- |
| `GET /health` | None | Returns `{"status":"ok"}`. |
| `GET /chat/threads` | Supabase bearer token | Lists the authenticated user's threads through the user-scoped Supabase client/RLS. |
| `POST /chat/threads` | Supabase bearer token | Upserts the user row and creates a thread. |
| `GET /chat/threads/{thread_id}/messages` | Supabase bearer token | Checks ownership, then loads ordered persisted UI message objects. |
| `POST /chat/stream` | Supabase bearer token | Validates thread access and latest user text, prepares a grounded answer, streams it, then persists the turn. |

`StreamRequest` in `backend/app/api/chat.py` accepts `threadId` as a UUID and `messages` as UI messages with `id`, `role`, and `parts`. Extra message fields are allowed. The handler selects the latest `role == "user"` entry and concatenates its `text` parts; it returns `422` if no user message or nonempty text is present.

The frontend sends `{ threadId, messages }` as JSON to `POST /chat/stream`, with `Authorization: Bearer <Supabase access token>` and `Accept: text/event-stream`. There is no separate REST query schema. Browser values are parsed/typed in `frontend/src/lib/api.ts`; backend input validation is Pydantic's `StreamRequest` and nested `UIMessage`.

## Execution sequence

```mermaid
sequenceDiagram
  actor Analyst
  participant Chat as frontend/src/pages/ChatWorkspace.tsx
  participant Client as frontend/src/lib/api.ts
  participant Route as backend/app/api/chat.py
  participant Auth as backend/app/auth/dependencies.py
  participant Orchestrator as backend/app/chat/orchestrator.py
  participant Retriever as backend/app/retrieval/retriever.py
  participant Agent as backend/app/assistant/agent.py
  participant Validator as backend/app/grounding/validator.py
  participant DB as Postgres/Supabase
  participant Groq
  Analyst->>Chat: Submit question
  Chat->>Client: streamChat(threadId, messages, callbacks)
  Client->>Auth: Send bearer token; resolve get_current_user
  Auth->>DB: Supabase Auth get_user(access_token)
  Route->>DB: get_thread_access(thread_id, user_id)
  Route->>Orchestrator: prepare_turn(text, user_id, thread_id)
  Orchestrator->>Retriever: search(question)
  Retriever->>DB: vector + full-text candidate queries
  Retriever->>Retriever: RRF, load top chunks and adjacent passages
  Orchestrator->>Agent: run_agent(prompt, typed deps)
  Agent->>Groq: Generate GroundedAnswer; call bounded retrieval tools if needed
  Agent-->>Orchestrator: Typed answer/citation IDs/excerpts
  Orchestrator->>Validator: Validate answer, markers, excerpts and available passage IDs
  Orchestrator-->>Route: PreparedTurn + trusted filing metadata
  Route-->>Client: text-delta and data-citations SSE events
  Route->>DB: Persist user/assistant messages + citations + thread update
  Client->>Chat: Update answer and citation state
  Chat->>Client: GET /chat/threads/{id}/messages after successful stream
  Client->>DB: Through FastAPI, reload persisted history
```

## Exact module responsibilities

1. **Capture / local UI state:** `frontend/src/pages/ChatWorkspace.tsx` has `ThreadChat.sendMessage()`. It trims the textarea, appends a local user message and empty assistant message, then disables submission while the stream is active.
2. **HTTP and SSE:** `frontend/src/lib/api.ts` `api.streamChat()` gets the current session, makes the authenticated `fetch`, reads SSE frames, and calls text/citation callbacks. Ordinary JSON calls use `frontend/src/lib/http.ts` via `api.get/post`; `http.ts` adds the bearer token, checks the configured origin, applies a 15-second timeout, and raises `ApiError`.
3. **Auth:** FastAPI dependencies `get_current_user()` and `get_authenticated_client()` are defined in `backend/app/auth/dependencies.py`. The former validates the bearer token through `get_user_client(...).auth.get_user(...)`; absent/invalid tokens return `401`.
4. **Ownership:** `backend/app/database/chats.py:get_thread_access()` uses the backend service-role Supabase client to load the thread and explicitly compare its `user_id` with the authenticated user. It raises `404` for missing threads and `403` for another user's thread.
5. **Retrieval:** `backend/app/chat/orchestrator.py:prepare_turn()` calls `DocumentRetriever.search()`. The retriever embeds the query with the same local model as ingestion, runs vector and Postgres text searches, fuses ranked IDs with RRF, loads the selected chunks, and adds neighboring chunks. No external reranker is implemented.
6. **Answer generation:** `backend/app/assistant/agent.py:run_agent()` invokes the cached PydanticAI agent. `get_agent()` configures `OpenAIChatModel` with `OpenAIProvider(base_url=settings.groq_base_url, api_key=settings.groq_api_key)`; this is the OpenAI-compatible SDK/provider adapter pointed at Groq. The output type is `GroundedAnswer` from `backend/app/assistant/outputs.py`.
7. **Agent access:** Agent tools `search_filings`, `read_chunk`, and `read_surrounding_chunks` use `DocumentRetriever`; they do not let the model issue arbitrary SQL. `DocumentAgentDeps` carries user/thread IDs, a SQLAlchemy session factory, and passages usable for citation.
8. **Grounding:** `backend/app/grounding/validator.py:validate_answer()` requires nonempty answer text, unique citation indices/chunks, markers matching citation indices, a marker in each answer paragraph, citations from the available passage map, and excerpts found in those passages. Insufficient-evidence answers must be explicit, uncited, and have no citation markers. `trusted_citations()` enriches verified citations from retrieved passage metadata.
9. **Stream and persist:** `backend/app/chat/streaming.py` creates UI messages with a text part and optional `data-citations` part and serializes start/text/citations/finish SSE frames. `api/chat.py` emits the validated response and then calls `persist_turn()` in `backend/app/database/chats.py`; SQLAlchemy commits the two chat messages, citation rows, and thread timestamp together. A persistence failure emits an `error` event instead of successful finish.
10. **Render/history:** `ChatWorkspace.tsx` displays text, turns known citation markers into buttons, opens a panel with exact excerpt and filing data, and reloads history after a successful send. `safeSourceUrl()` permits HTTPS SEC hostnames only. History content is stored in `chat_messages.content` JSONB; citation rows additionally live in `message_citations`.

## Response contract and errors

The Pydantic agent result is:

```json
{
  "answer": "Text with validated citation markers [1].",
  "citations": [{"citation_index": 1, "chunk_id": "uuid", "excerpt": "Verified excerpt"}],
  "insufficient_evidence": false
}
```

The HTTP endpoint returns an SSE stream rather than that JSON object. It uses `text-delta` events for answer text and one `data-citations` event whose entries include `citation_index`, `document_chunk_id`, `excerpt`, `ticker`, `company_name`, `filing_type`, `filing_date`, `page_number`, `section`, and `source_url`. The final sentinel is `data: [DONE]`. This project has no typed tabular result in the current contract.

Boundary behavior currently includes `401` for absent/invalid credentials, `403` for thread ownership mismatch, `404` for missing thread, `422` for invalid/no user text, `503` for retrieval SQL errors, and `502` for grounding or answer-generation failures. Message persistence failures happen after streaming begins and are represented as an SSE `error` event. `ChatWorkspace.chatErrorMessage()` maps common failures to user-facing text; `api.streamChat()` handles malformed/incomplete stream and network failures.

## Related docs

- [Architecture and database map](ARCHITECTURE.md)
- [Ingestion and retrieval details](INGESTION_AND_RETRIEVAL.md)
- [Backend API implementation](../backend/app/api/README.md)
