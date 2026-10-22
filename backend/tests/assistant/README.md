# Assistant tests

`test_agent.py` checks PydanticAI agent construction with typed dependencies and an offline model. It does not call the configured Groq endpoint or validate client-brief answer quality. Run with `uv run pytest tests/assistant` from `backend/`.
