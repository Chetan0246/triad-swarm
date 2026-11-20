"""Tests for Spec Generator Agent (triad new)."""

import pytest
from triad.agents.spec_generator import SpecGeneratorAgent
from triad.core.llm import MockLLMProvider
from triad.core.models import WorkloadSpec


@pytest.mark.asyncio
async def test_spec_generator_from_prompt():
    mock_llm = MockLLMProvider()
    agent = SpecGeneratorAgent(llm=mock_llm)

    spec = await agent.generate_spec(
        prompt="Add an async sliding-window rate limiter with memory backend",
        repo_map="class Server:\n    def route(): pass",
    )

    assert isinstance(spec, WorkloadSpec)
    assert "sliding-window-rate-limiter" in spec.name or "add-an-async" in spec.name
    assert len(spec.acceptance_criteria) >= 2


def test_spec_generator_safe_json_parsing():
    agent = SpecGeneratorAgent(llm=MockLLMProvider())
    raw_json = """
    ```json
    {
      "name": "token-bucket-limiter",
      "description": "Async token bucket algorithm",
      "acceptance_criteria": [
        "Consume tokens on request",
        "Refill tokens on clock tick"
      ],
      "initial_files": {}
    }
    ```
    """
    spec = agent._parse_spec(raw_json, fallback_prompt="Token bucket limiter")
    assert spec.name == "token-bucket-limiter"
    assert len(spec.acceptance_criteria) == 2
