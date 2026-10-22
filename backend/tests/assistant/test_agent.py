from pydantic_ai.models.test import TestModel

from app.assistant.agent import build_agent
from app.assistant.deps import DocumentAgentDeps


def test_agent_builds_with_typed_dependencies_and_offline_model():
    agent = build_agent(TestModel(call_tools=[]))
    assert agent.deps_type is DocumentAgentDeps
    assert agent.output_type is not None
    assert set(agent._function_toolset.tools) == {
        "search_filings",
        "read_chunk",
        "read_surrounding_chunks",
    }
