# Retrieval tests

- `test_queries.py` checks SQL construction for `embedding_384`, metadata filters, PostgreSQL English full-text search, and invalid/blank inputs.
- `test_fusion.py` checks rank fusion, duplicate handling, and deterministic ties.
- `test_retriever.py` checks query orchestration, filters, anchor rank, and neighboring passage ordering.

These tests mock the session/query boundary and do not establish live corpus relevance. Run with `uv run pytest tests/retrieval` from `backend/`.
