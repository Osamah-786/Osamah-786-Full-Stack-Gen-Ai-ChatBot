# Grounding tests

`test_validator.py` covers exact cited excerpts, trusted metadata, missing/invalid passages, citation markers, and explicit insufficient-evidence answers. Preserve these grounding invariants when changing outputs or prompts. Run with `uv run pytest tests/grounding` from `backend/`.
