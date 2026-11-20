"""Asymmetric Model Routing for Triad Swarm.

Enables economic and capability arbitrage across agent tiers:
- Architect: High-reasoning model (Gemini Pro, Claude 3.7 Sonnet, GPT-4o) for global DAG planning
- Workers: Fast, low-cost distilled models (Gemini Flash, GPT-4o-mini, Qwen 2.5 Coder via Ollama)
"""

from __future__ import annotations

import os
from typing import Any, Optional, Tuple
from triad.core.cache import PromptCacheManager
from triad.core.llm import (
    BaseLLMProvider,
    CachedLLMProvider,
    GeminiProvider,
    MockLLMProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
    get_llm_provider,
)


def parse_model_spec(spec: str) -> Tuple[str, Optional[str]]:
    """
    Parse model specification strings such as:
    - 'gemini/gemini-3.8-flash' -> ('gemini', 'gemini-3.8-flash')
    - 'openai/gpt-4o-mini' -> ('openai', 'gpt-4o-mini')
    - 'ollama/qwen2.5-coder:7b' -> ('ollama', 'qwen2.5-coder:7b')
    - 'mock' -> ('mock', None)
    """
    s = spec.strip().lower()
    if "/" in s:
        provider_part, model_part = s.split("/", 1)
        return provider_part.strip(), model_part.strip()
    return s, None


class ModelRouter:
    """
    Manages asymmetric provider routing between Architect and Worker agents.
    Prevents overpaying for simple worker edits while giving the architect sufficient reasoning depth.
    """

    def __init__(
        self,
        architect_spec: Optional[str] = None,
        worker_spec: Optional[str] = None,
        enable_cache: bool = True,
        cache_manager: Optional[PromptCacheManager] = None,
    ):
        self.architect_spec = (
            architect_spec
            or os.environ.get("TRIAD_ARCHITECT_MODEL")
            or os.environ.get("TRIAD_LLM_PROVIDER")
            or "gemini"
        )
        self.worker_spec = (
            worker_spec
            or os.environ.get("TRIAD_WORKER_MODEL")
            or os.environ.get("TRIAD_LLM_PROVIDER")
            or "gemini"
        )
        self.enable_cache = enable_cache
        self.cache_manager = cache_manager or (PromptCacheManager() if enable_cache else None)

        self._architect_llm: Optional[BaseLLMProvider] = None
        self._worker_llm: Optional[BaseLLMProvider] = None

    def _instantiate_provider(self, spec: str) -> BaseLLMProvider:
        """Instantiate an LLM provider based on spec string."""
        provider_name, model_name = parse_model_spec(spec)

        if provider_name == "mock":
            return MockLLMProvider()

        if provider_name in ("ollama", "local", "vllm", "openai-compatible"):
            return OpenAICompatibleProvider(
                model=model_name or "qwen2.5-coder:7b",
            )

        if provider_name == "openai":
            if not os.environ.get("OPENAI_API_KEY"):
                # Graceful fallback to mock if key missing
                return MockLLMProvider()
            return OpenAIProvider(model=model_name or "gpt-4o-mini")

        if provider_name == "gemini":
            if not os.environ.get("GEMINI_API_KEY"):
                # Graceful fallback to mock if key missing
                return MockLLMProvider()
            return GeminiProvider(model=model_name or "gemini-3.8-flash")

        # Generic fallback
        return get_llm_provider(provider_name=provider_name, model=model_name)

    def get_architect_llm(self) -> BaseLLMProvider:
        """Get or create the LLM provider for the Architect agent."""
        if self._architect_llm is None:
            raw = self._instantiate_provider(self.architect_spec)
            if self.enable_cache and self.cache_manager:
                self._architect_llm = CachedLLMProvider(raw, cache=self.cache_manager)
            else:
                self._architect_llm = raw
        return self._architect_llm

    def get_worker_llm(self, worker_id: Optional[str] = None) -> BaseLLMProvider:
        """Get or create the LLM provider for Worker agents."""
        if self._worker_llm is None:
            raw = self._instantiate_provider(self.worker_spec)
            if self.enable_cache and self.cache_manager:
                self._worker_llm = CachedLLMProvider(raw, cache=self.cache_manager)
            else:
                self._worker_llm = raw
        return self._worker_llm
