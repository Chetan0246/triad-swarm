"""Tests for Asymmetric Model Router and OpenAI-compatible provider."""

import pytest
from triad.core.llm import MockLLMProvider, OpenAICompatibleProvider
from triad.core.router import ModelRouter, parse_model_spec


def test_parse_model_spec():
    assert parse_model_spec("gemini/gemini-3.8-flash") == ("gemini", "gemini-3.8-flash")
    assert parse_model_spec("openai/gpt-4o") == ("openai", "gpt-4o")
    assert parse_model_spec("ollama/qwen2.5-coder:7b") == ("ollama", "qwen2.5-coder:7b")
    assert parse_model_spec("mock") == ("mock", None)


def test_asymmetric_model_router_instantiation():
    router = ModelRouter(
        architect_spec="mock",
        worker_spec="mock",
        enable_cache=False,
    )
    arch_llm = router.get_architect_llm()
    worker_llm = router.get_worker_llm("worker_01")

    assert isinstance(arch_llm, MockLLMProvider)
    assert isinstance(worker_llm, MockLLMProvider)


def test_openai_compatible_provider_defaults():
    provider = OpenAICompatibleProvider(
        base_url="http://localhost:11434/v1",
        model="qwen2.5-coder:7b",
    )
    assert provider.endpoint == "http://localhost:11434/v1/chat/completions"
    assert provider.model == "qwen2.5-coder:7b"
