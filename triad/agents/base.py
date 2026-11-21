"""Base agent interface and execution harness."""

from __future__ import annotations

import time
from typing import Optional

from triad.core.llm import BaseLLMProvider, LLMResponse
from triad.core.token_tracker import TokenTracker


class BaseAgent:
    """Minimal agent base class with automated token logging."""

    def __init__(
        self,
        agent_id: str,
        role: str,
        llm: BaseLLMProvider,
        tracker: TokenTracker,
    ):
        self.agent_id = agent_id
        self.role = role
        self.llm = llm
        self.tracker = tracker

    async def prompt_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        phase: Optional[str] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Query LLM and record token metrics automatically."""
        t0 = time.perf_counter()
        res = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=json_mode,
            temperature=temperature,
        )
        duration = time.perf_counter() - t0

        self.tracker.record_usage(
            agent_id=self.agent_id,
            phase=phase or self.role,
            prompt_tokens=res.prompt_tokens,
            completion_tokens=res.completion_tokens,
            cached_tokens=res.cached_tokens,
            duration_seconds=duration,
        )
        if res.cached_tokens > 0:
            self.tracker.record_cache_hit(self.agent_id, res.cached_tokens)
        return res
