import pytest
from triad.core.llm import MockLLMProvider, get_llm_provider


@pytest.mark.asyncio
async def test_mock_llm_deterministic_generation():
    mock = MockLLMProvider()
    mock.register_response("calculate_fib", '{"files": {"fib.py": "def fib(n): return 1"}}')

    res = await mock.generate(prompt="Please calculate_fib in python")
    assert "fib.py" in res.content
    assert res.total_tokens > 0


@pytest.mark.asyncio
async def test_mock_llm_json_mode():
    mock = MockLLMProvider()
    res = await mock.generate(prompt="any query", json_mode=True)
    assert "status" in res.content
    assert res.prompt_tokens > 0
    assert res.completion_tokens > 0


def test_provider_factory():
    provider = get_llm_provider("mock")
    assert isinstance(provider, MockLLMProvider)
