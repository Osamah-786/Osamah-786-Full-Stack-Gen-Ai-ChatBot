# Phase 4: Ingestion Pipeline Plan

> **Status:** This is the original plan, not a runbook. The downloader, Docling converter, source-document importer, and chunk loader now exist. The current commands, split behavior, dimensions, idempotency, and unverified database connection/corpus status are documented in [INGESTION_AND_RETRIEVAL.md](INGESTION_AND_RETRIEVAL.md) and [todos.md](todos.md). Full-corpus completion is not confirmed.

## Current foundation

The backend defines `SourceDocument` and `DocumentChunk`, and provides a source importer. The schema keeps legacy `embedding vector(1536)` alongside `embedding_384 vector(384)` and its HNSW index, added by migration `0002_local_embeddings`. Local embeddings use `sentence-transformers/all-MiniLM-L6-v2`; ingestion caps chunks at 254 tokenizer tokens. See the current implementation guide for exact run/recovery behavior.

## Original implementation steps

1. **Read the local corpus and manifest.** Use `data/markdown/` and its manifest. Match each Markdown file to its existing `source_documents` row by accession number; do not recreate source rows.

2. **Parse Markdown with Docling.** Load each Markdown file through `DocumentConverter` to create a `DoclingDocument`, which Docling's chunkers consume. See [Docling's converter documentation](https://docling-project.github.io/docling/reference/document_converter/).

3. **Compare hierarchical and hybrid chunks.** Inspect `HierarchicalChunker` output to understand section and element boundaries. Use `HybridChunker` for candidate embedding chunks: it refines hierarchical chunks by splitting oversized chunks and merging compatible undersized chunks. Use its contextualized serialization as embedding input. See [Docling's chunking documentation](https://docling-project.github.io/docling/concepts/chunking/).

4. **Keep within the embedding model limit.** Use the model's Hugging Face tokenizer for Docling chunking, with a 254-token cap to leave room for special tokens within the model's 256-token limit. The model returns 384 dimensions. See the [model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).

5. **Attach filing and section metadata.** Store the chunk text, sequential chunk index, token count, Docling heading/section metadata, and filing metadata such as ticker, form, fiscal year, and accession number. Markdown may not preserve page boundaries. Store `page_number = null` unless Docling provides a reliable page number; do not infer one.

6. **Write chunks idempotently.** Link each chunk to its `source_document_id` and use the existing unique constraint on `(source_document_id, chunk_index)`. Write local vectors only to `embedding_384`; keep the original `embedding` column untouched until a separately reviewed cleanup migration. Reruns should update changed chunks and remove stale trailing chunks when a document's chunk count shrinks.

7. **Run a one-chunk pilot first.** The explicit `--pilot` command reads one filing, creates one embedding, and writes one chunk to `embedding_384`. Verify the stored vector has 384 values, its foreign key points to the correct source document, and the generated search vector exists. Spot-check the Apple revenue table passage.

8. **Test locally, then ingest incrementally.** Unit tests should mock embedding and database calls and cover chunk text, token limits, metadata, and rerun behavior. After the one-chunk pilot succeeds, run the full corpus with progress reporting and resume/skip behavior.

## Data-quality check

A previous random audit found duplicated filing text and blank table rows in at least one converted Markdown file. Inspect the pilot chunk previews for this noise before embedding the full corpus.

## Original run boundary

No embeddings or database writes have been run as part of preparing this plan. The pilot and full ingestion should be run as separate steps, with the one-chunk result checked before proceeding to the corpus.
