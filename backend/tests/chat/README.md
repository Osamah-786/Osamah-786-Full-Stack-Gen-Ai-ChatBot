# Chat tests

- `test_orchestrator.py` checks retrieve/agent/validate coordination and trusted citation mapping.
- `test_streaming.py` checks citation parts and stream framing.
- `test_persistence.py` checks transactional citation linkage and thread ownership.

These tests do not exercise a live provider or Supabase instance. Run with `uv run pytest tests/chat` from `backend/`.
