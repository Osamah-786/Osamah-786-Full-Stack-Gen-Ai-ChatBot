# Phase 6 — LLM Agent and Grounding Plan

> **Status:** The current implementation has the typed PydanticAI agent, bounded retrieval tools, orchestrator, citation validator, AI SDK-compatible SSE framing, and chat/citation persistence described here. This file is retained as its design record. Runtime paths and remaining unverified checks are in [REQUEST_LIFECYCLE.md](REQUEST_LIFECYCLE.md) and [todos.md](todos.md).

## Original goal

Replace the stub response in `POST /chat/stream` with an answer grounded in the Phase 5 retrieval results. Return typed citations, reject unsupported or malformed citations before they reach the user, stream the validated answer in the existing AI SDK-compatible protocol, and persist the turn and its citation rows.

## Current baseline and prerequisites

- The Phase 5 retrieval modules now provide semantic search, Postgres full-text search, RRF, and neighboring passage context. The retriever is synchronous and takes a SQLAlchemy session from its caller.
- `backend/app/api/chat.py` authenticates the user, checks thread ownership, validates the latest user text, invokes the orchestrator, and streams a grounded answer. Preserve those route and request contracts.
- `backend/app/database/chats.py::persist_turn` writes both messages, citation rows, and the thread update in one SQLAlchemy transaction after validating ownership.
- Existing migrations define `chat_messages`, `message_citations`, and the citation foreign keys. No schema migration was needed for this answer contract.
- Settings include `groq_api_key`, `groq_base_url`, and `groq_chat_model`. The agent currently uses `groq_chat_model`; `groq_grounding_model` is configured but unused.
- A previous corpus run stopped after four of 25 filings. The current chunker has an oversized-chunk split path, but a later full run is not confirmed.

## Original recommended implementation order

### 1. Define the typed agent contract

Add `backend/app/assistant/outputs.py` with Pydantic models for:

- `Citation`: a retrieved `chunk_id` plus an exact supporting excerpt (and a stable citation index if the stream/UI contract needs it).
- `GroundedAnswer`: answer text plus its structured citations.
- `SourcePassage` only if the existing `RetrievedPassage` result cannot already provide the citation metadata. Avoid maintaining duplicate passage schemas.

Keep source metadata authoritative on the backend. Build company, filing, date, page, section, excerpt, and source URL from the actual retrieved passage; do not accept those fields as model-created facts.

### 2. Write the product instructions

Add `backend/app/assistant/instructions.md` and load it as the PydanticAI agent instructions. It should state:

- Answer only from passages returned by retrieval tools.
- Cite each factual claim using the citation format in the typed output.
- Use only the provided passage IDs and quote exact supporting text.
- Say that the corpus does not provide enough evidence when evidence is absent or incomplete; do not fill gaps with outside knowledge.
- Do not recommend securities, predict returns, or give investment advice.
- Do not infer causation or conclusions (for example, that generative AI improved margins) unless the filings explicitly support them.

Instructions support the policy; the validator below enforces the parts that can be checked deterministically.

### 3. Add typed runtime dependencies and agent tools

Add `backend/app/assistant/deps.py` with a `DocumentAgentDeps` dataclass. Pass request-specific dependencies explicitly: authenticated user ID, thread ID, the document retriever (or a safe factory for it), and the set of passages available to cite. Do not use module-level database sessions or credentials.

Add `backend/app/assistant/agent.py` with one PydanticAI agent using the configured Groq-compatible chat model. Use the locked PydanticAI version and existing OpenAI-compatible SDK/provider configuration with `groq_base_url` and the secret key from settings. Do not add dependencies unless the locked provider genuinely requires one.

Register bounded tools that delegate to the retrieval layer, never to generated SQL:

- `search_filings`: query with bounded result counts and optional ticker/year/form filters.
- `read_chunk`: fetch one passage by ID and return its authoritative metadata.
- `read_surrounding_chunks`: fetch adjacent chunks for a known passage.

Each tool must return typed passage data. Cap per-call results and total tool calls so the agent cannot expand its context without bound. Tools should only expose the shared SEC corpus; thread/user identity remains enforced by the API before agent execution.

### 4. Validate evidence before streaming

Add `backend/app/grounding/validator.py` with deterministic validation over the agent output and the passages retrieved for this request:

1. Every cited `chunk_id` exists in the allowed retrieved/tool-returned passage set.
2. Every excerpt is an exact substring of its cited passage after a narrowly defined whitespace normalization.
3. Citation indices/markers are unique, valid, and actually referenced by the answer.
4. A substantive answer has at least one citation. An explicit insufficient-evidence response may have none.
5. Reject citations to duplicate IDs if the output format requires one entry per source; otherwise normalize duplicates deterministically.

On a violation, fail closed with a controlled grounding error; never send an unvalidated answer as if it were supported. Build citation display metadata from the matching `RetrievedPassage` after validation.

### 5. Orchestrate one chat turn

Add `backend/app/chat/orchestrator.py` to coordinate one request:

1. Rely on the existing route to verify the bearer token and thread ownership before doing retrieval or LLM work.
2. Parse the latest user text using the existing request schema.
3. Create a request-scoped database session/retriever and typed `DocumentAgentDeps`.
4. Retrieve initial passages, then run the PydanticAI agent with those passages and the bounded tools.
5. Validate `GroundedAnswer`; build trusted citation metadata from retrieved records.
6. Only after validation succeeds, return a result ready for streaming and persistence.

Use server-persisted thread history for model context if conversational history is included; do not treat client-supplied assistant messages as trusted evidence. Keep retrieval and grounding callable without a Groq call for unit tests.

### 6. Stream validated output using the existing protocol (implemented)

`backend/app/chat/streaming.py` formats the response as an AI SDK-compatible UI message stream (`x-vercel-ai-ui-message-stream: v1` and start/text/finish framing). Citation/source metadata is sent as a structured data part. Compatibility is implemented by the custom frontend SSE parser; no Vercel AI SDK frontend package is installed.

For the first version, complete and validate the structured agent result before emitting answer text. Then emit that validated text in deltas and its citation data before the finish event. This adds some time-to-first-token but ensures a validation failure cannot leak unsupported partial text. Keep the stream format compatible with the installed frontend AI SDK version.

Replace only the stub section of `backend/app/api/chat.py` with a call to the orchestrator and streaming adapter. Preserve routes, request/response wire shape, auth dependencies, and existing error semantics.

### 7. Persist the complete turn and citations

Persist only after the agent result passes validation and the stream completes successfully. The turn should contain:

- The user message and assistant AI SDK-compatible message JSON.
- One `message_citations` row per accepted citation, linked to the assistant message and the exact `document_chunk_id`; store the verified excerpt and stable citation index.
- The thread title/update timestamp using existing behavior.

Prefer one database transaction for the two messages, citation rows, and thread update. Because the current REST `persist_turn` performs multiple requests and has no citation insert, implement a focused persistence operation that returns the assistant message ID and rolls back the entire turn on failure. Re-check thread ownership inside the privileged transaction or ensure the existing verified owner ID is passed and compared there. Never log message bodies, excerpts, tokens, or API keys.

### 8. Handle errors at the API boundary

Map failures to safe public messages while logging only redacted diagnostic context:

- Invalid request remains `422`; missing/unauthorized thread remains `404`/`403` from current behavior.
- Retrieval/database failure returns a controlled service error.
- Groq/PydanticAI provider failure returns `502`.
- Grounding validation failure returns a controlled error and does not persist or emit answer text.
- Persistence failure emits the existing stream error event, with no success/finish signal that implies the turn was saved.

Preserve cancellation behavior and close request-scoped sessions if the client disconnects.

## Tests

Use PydanticAI's test models or a small fake agent; tests must not call Groq or Supabase.

- **Grounding validator:** valid cited excerpt; unknown chunk ID; fabricated excerpt; missing/invalid citation marker; no evidence; permitted insufficient-evidence response.
- **Agent/tools:** dependency injection, tool limits, tool outputs restricted to retrieved/source passages, and structured output validation.
- **Message conversion:** latest user input parsing, persisted history conversion, assistant UI message/citation part mapping.
- **Orchestrator:** retrieve → agent → validate order; no persistence on model/validation failure; successful result includes only trusted passage metadata.
- **Streaming:** expected AI SDK event order, citation metadata, `[DONE]`, and failure behavior without leaking unvalidated text.
- **Persistence:** assistant message ID links citation rows; transaction rollback on any write failure; owner checks remain enforced.

## Verification and completion criteria

1. Run backend unit tests, Ruff, and import checks.
2. Test stream framing with the frontend's installed AI SDK parser or an equivalent contract test.
3. Run optional database integration tests only against the configured development Supabase project; do not use production credentials for test writes.
4. After ingestion is confirmed complete, manually evaluate the client brief's example questions. Verify each returned citation points to an actual retrieved chunk and that its excerpt exists in that chunk.
5. Explicitly check the under-specified question and the generative-AI-margin question for an evidence-limited answer.
6. Reload chat history and confirm assistant messages and citation rows remain linked.

The answer-quality checks against the client-brief questions are not implied by unit tests or by the existence of an agent. Keep those checks pending until they have been run against the intended ingested corpus and the results reviewed.

## Expected files

- `backend/app/assistant/instructions.md`
- `backend/app/assistant/deps.py`
- `backend/app/assistant/outputs.py`
- `backend/app/assistant/agent.py`
- `backend/app/grounding/validator.py`
- `backend/app/chat/orchestrator.py`
- `backend/app/chat/streaming.py`
- Focused updates to `backend/app/api/chat.py` and `backend/app/database/chats.py` (and persistence tests)
- Phase 6 unit tests under `backend/tests/`

No schema migration or new dependency is expected: the citation table and Groq/PydanticAI dependencies already exist. Confirm the transaction/persistence path against the configured Supabase development environment before using it for live chat.

## References

- [Project Phase 6 checklist](todos.md#phase-6--llm-agent--grounding)
- [Project backend and streaming architecture](ARCHITECTURE.md#request-and-security-boundaries)
- [PydanticAI dependencies](https://pydantic.dev/docs/ai/core-concepts/dependencies/)
- [PydanticAI tools](https://pydantic.dev/docs/ai/tools-toolsets/tools/)
