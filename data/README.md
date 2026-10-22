# Data tools and corpus

This directory holds local SEC filing inputs, Docling Markdown output, and operator-run data scripts. `downloads/` and `markdown/` are generated corpus folders and their payloads are gitignored; scripts and this guide are tracked.

## Files

- `download.py` — stdlib SEC EDGAR downloader; parameters and contact `USER_AGENT` are constants at the top. **It deletes the existing downloads directory by default** (`CLEAR_OUTPUT_DIR = True`) before fetching.
- `convert_to_markdown.py` — converts all manifest-listed local HTML files recursively with Docling and preserves year/relative folder structure in Markdown output.
- `import_source_documents.py` — maps Markdown manifest fields to `source_documents`, upserts by accession number through the Supabase service-role client, and verifies stored accession numbers. Supports `--dry-run`.
- `downloads/` — generated year-organized source HTML and manifest.
- `markdown/` — generated year-organized Markdown and manifest, consumed by the source importer and backend chunker.

## Workflow

Run from repository root:

```powershell
# Edit USER_AGENT in download.py before contacting SEC.
uv run data/download.py
uv run --project backend --extra ingest python data/convert_to_markdown.py
uv run --project backend python data/import_source_documents.py --dry-run
uv run --project backend python data/import_source_documents.py
uv run --project backend python -m ingest.load_document_chunks --dry-run
```

The source import writes database rows; it requires backend `.env` Supabase settings. Actual chunk embedding/storage is an explicit separate command (`--pilot` or `--all`); see [ingestion and retrieval](../docs/INGESTION_AND_RETRIEVAL.md). Do not put raw source payloads or secrets in documentation or Git.
