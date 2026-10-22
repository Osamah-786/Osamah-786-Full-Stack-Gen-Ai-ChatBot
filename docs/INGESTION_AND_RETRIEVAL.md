# Ingestion and Retrieval

This guide documents the local corpus pipeline and the runtime hybrid retriever. Ingestion is an operator-run workflow; no ingestion HTTP endpoint or background worker is defined.

## Data lifecycle and commands

Run commands from the repository root unless a step explicitly says otherwise.

```mermaid
flowchart LR
  SEC[SEC EDGAR HTML] --> Download[data/download.py]
  Download --> Raw[data/downloads/<year> + manifest.json]
  Raw --> Convert[data/convert_to_markdown.py]
  Convert --> MD[data/markdown/<year> + manifest.json]
  MD --> Import[data/import_source_documents.py]
  Import --> SD[(source_documents)]
  MD --> Chunks[backend/ingest/load_document_chunks.py]
  SD --> Chunks
  Chunks --> Docling[DocumentConverter + HybridChunker]
  Docling --> MiniLM[all-MiniLM-L6-v2, 384d]
  MiniLM --> Persist[(document_chunks.embedding_384)]
  Persist --> Retrieval[vector + English FTS + RRF]
  Retrieval --> Context[ranked passages + neighbors]
  Context --> Agent[PydanticAI grounded answer]
```

1. **Download:** `data/download.py` uses Python's stdlib HTTP client against SEC submission/filing endpoints. Tickers, count, output folder, and contact `USER_AGENT` are constants in the script. It writes year-organized HTML and `data/downloads/manifest.json`. `CLEAR_OUTPUT_DIR = True` removes the previous downloads directory before downloading; preserve any needed corpus separately before running it.
2. **Convert:** `data/convert_to_markdown.py` reads the downloads manifest, discovers `.htm`/`.html` recursively, converts with Docling `DocumentConverter`, preserves relative year/folder layout, and writes Markdown plus a matching manifest in `data/markdown/`. It copies matching filing metadata and records `source_local_path`.
3. **Import filing records:** `data/import_source_documents.py` validates each manifest path is within `data/markdown`, loads Markdown and filing metadata, then upserts into `source_documents` by `accession_number` using the service-role Supabase REST client. `--dry-run` validates and reports DB matches without writes; it still needs configured Supabase connectivity.
4. **Chunk/embed/store:** `backend/ingest/load_document_chunks.py` reads Markdown and manifest, requires each filing to exist in `source_documents` and the stored Markdown to match, converts Markdown to a Docling document, measures hierarchical chunks, then persists contextualized HybridChunker chunks. The `--dry-run` mode chunks all manifest filings locally and does not connect to the database or generate embeddings.

Commands:

```powershell
# Optional corpus refresh; edit USER_AGENT first.
uv run data/download.py

# Markdown extraction; Docling is installed from backend's ingest extra.
uv run --project backend --extra ingest python data/convert_to_markdown.py

# Validate / write source_documents.
uv run --project backend python data/import_source_documents.py --dry-run
uv run --project backend python data/import_source_documents.py

# Chunk-only preview, one-chunk DB pilot, then all missing/changed chunks.
uv run --project backend python -m ingest.load_document_chunks --dry-run
uv run --project backend python -m ingest.load_document_chunks --pilot
uv run --project backend python -m ingest.load_document_chunks --all
```

From `backend/`, `uv run python -m ingest.load_source_documents` dispatches to the source importer. The chunk module accepts one of `--dry-run`, `--pilot`, or `--all`. `load_source_documents.py` delegates to the data importer; it is not a separate implementation.

## Chunking and embeddings

`backend/ingest/load_document_chunks.py` configures Docling's `HybridChunker` with the Hugging Face tokenizer for `sentence-transformers/all-MiniLM-L6-v2`, `merge_peers=True`, and `max_tokens=254`. The model has a 256-word-piece input limit including special tokens; 254 is the operational cap. Contextualized chunk text is token-count checked and any oversized result is split at tokenizer offsets without dropping text. The script also counts `HierarchicalChunker` output for progress/diagnostics; hierarchical chunks are not separately stored as vectors.

`backend/app/embeddings.py` lazily loads and caches one Sentence Transformers model with `lru_cache`. `embed_documents()` supports batches (default batch size 32), normalizes embeddings, converts values to Python floats, and checks each vector has exactly 384 dimensions. `embed_query()` uses the same model and normalization. The model's first use may fetch model files from Hugging Face.

Metadata stored per chunk includes ticker, filing type/date, fiscal year, accession number, Markdown path, headings, model name, vector dimensions, and content hash. `page_number` is the minimum reliable page provenance reported by Docling, or null; section is derived from headings. PostgreSQL computes `search_vector` from `chunk_text` using English text search.

## Persistence, idempotency, and recovery

- Schema table is **`public.document_chunks`**, linked to `source_documents` by `source_document_id`; all new local vectors go into `embedding_384 vector(384)`. The legacy `embedding vector(1536)` remains and is not used by this ingestion/retrieval path.
- Ingestion compares existing row text, page, section, token count, metadata/provenance, model ID, dimension, and non-null vector length. Matching chunks are skipped; changed/new chunks are embedded again and updated/inserted by `(source_document_id, chunk_index)`.
- Embeddings are computed in batches of 32. PostgreSQL writes are committed in batches of 4 with a transaction-scoped 60-second statement timeout. There is no transaction covering every document or the full corpus.
- In `--all`, stale trailing chunk indices are deleted after processing a filing, including the no-pending-chunks case. `--pilot` chooses at most one pending chunk from the first manifest filing and does not clean stale rows. Re-running `--all` is the explicit way to reconcile the corpus; do not assume a failed run rolled back earlier commits.
- After writes, the script queries stored rows and checks vector dimension, generated search vector, and chunk text. The source-document importer likewise reads back and verifies accession numbers after upserts.
- The `--dry-run` chunk preview does not validate database content equality or embedding results; it confirms files parse and chunking completes.

## Retrieval details

`backend/app/retrieval/queries.py` runs two independent, filtered searches over the same corpus:

1. **Semantic:** query embedding from `app.embeddings.embed_query()`; cosine distance against `DocumentChunk.embedding_384`; fixed caller limit, default 50 candidates. Optional filters are ticker, fiscal year, and filing type.
2. **Lexical:** `websearch_to_tsquery('english', query)` over generated `search_vector`, ranked by `ts_rank_cd`; same optional filing filters and candidate limit. Blank/limit-zero input returns no hits. PostgreSQL English configuration handles stop words; there is no external stop-word API/library.
3. **Fusion:** `backend/app/retrieval/fusion.py` combines rankings using Reciprocal Rank Fusion, default `k=60`. It deduplicates IDs within each ranking and breaks score ties by chunk UUID string.
4. **Context:** `DocumentRetriever` in `retriever.py` defaults to 50 candidates per modality, 10 fused results, then retrieves one adjacent chunk before/after each anchor from the same source. Neighbor rows are marked `is_neighbor` and have no direct fused rank. Phase 6 calls can use different bounded limits (for example, the agent search tool requests 30 candidates and 5 final results).
5. **Grounded generation:** `chat.orchestrator.prepare_turn()` runs the initial retrieval. `assistant.agent` can call bounded search/read tools, and the grounding validator accepts citations only for passages collected in the request's `DocumentAgentDeps.passages` map.

There is no BM25 implementation, external reranker, score normalization across vector and lexical scores, query rewrite, or faceted browsing. No vector-store extension beyond PostgreSQL pgvector is used.

## Database/index compatibility

Migrations `backend/alembic/versions/0001_initial.py` and `0002_local_embeddings.py` own the schema. Migration 0002 verifies the current `embedding` column is exactly `vector(1536)` before adding `embedding_384 vector(384)` and an HNSW cosine index. The old 1536 column/index is retained. The new model and retrieval must continue to use exactly 384 dimensions; changing the encoder requires a new additive/migration and explicit re-embedding plan. The GIN index on generated English `search_vector` supports keyword retrieval.

Apply migrations from `backend/` with `uv run alembic upgrade head` and a Supabase direct/session connection in `DATABASE_URL`; do not use a transaction pooler for migrations. Schema migrations are not part of the ingestion commands.

## Known limitations and debugging

- The last recorded user output in this conversation showed `--all` stopped after four filings because one Docling chunk had 310 tokens. The current checked-out script contains `split_oversized_text()` to split oversized chunks at tokenizer offsets. The inspected ingest unit tests do not directly test this split path, and the corpus was not re-run during the documentation audit.
- No prior PostgreSQL connection-error transcript was found in the repository or supplied text available to this documentation task. Its exact cause and resolution cannot be confirmed. Treat database connectivity as unverified until the command succeeds against the intended development project.
- A direct-connection failure can stem from a wrong direct host/password, URL-unescaped password characters, network/IPv6 reachability, or using a pooler URL where a session connection is required. Check only the sanitized hostname/port and connection mode; never paste the password or full credential URL into logs or issues.
- `uv` may warn that an outer active virtualenv differs from `backend/.venv`; run the repository commands with `uv run` from the indicated project context. Use `--active` only when intentionally choosing another environment.
- Before debugging database persistence, first run `--dry-run` to isolate Markdown/Docling chunk errors. Then verify `.env` has the correct development `DATABASE_URL` and Supabase keys, apply migrations, check that source documents are present, and run `--pilot` before `--all`.
- `data/download.py` clears `data/downloads` by default. It is a destructive local file operation for that corpus folder; verify backups and configured output before using it.

## Related files

- Chunk loader: [`../backend/ingest/load_document_chunks.py`](../backend/ingest/load_document_chunks.py)
- Embeddings: [`../backend/app/embeddings.py`](../backend/app/embeddings.py)
- Retrieval: [`../backend/app/retrieval/`](../backend/app/retrieval/)
- Models/migrations: [`../backend/app/database/models/`](../backend/app/database/models/) and [`../backend/alembic/`](../backend/alembic/)
- Product checklist: [todos.md](todos.md)
