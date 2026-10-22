# Ingestion tests

`test_load_document_chunks.py` verifies filing/embedding provenance metadata and that chunk-current detection requires matching text, metadata, model, dimension, and stored vector. It imports `backend/ingest/load_document_chunks.py`; no database or Docling corpus job is run. Run with `uv run pytest tests/ingest` from `backend/`.
