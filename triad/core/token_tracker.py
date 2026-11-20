"""Thread-safe, async-safe token accounting with cost modeling, cache hit tracking, and audit trails."""

from __future__ import annotations

import asyncio
import threading
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TokenRecord(BaseModel):
    """An individual token transaction."""
    agent_id: str
    phase: str  # "architect", "worker", "verifier", "healing"
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int = 0
    total_tokens: int
    duration_seconds: float = 0.0
    cost_usd: float = 0.0
    metadata: Dict[str, str] = Field(default_factory=dict)


# Default pricing per million tokens (USD)
# Gemini 2.5 Flash / GPT-4o mini blended tier
DEFAULT_PROMPT_PRICE_PER_M = 0.15
DEFAULT_COMPLETION_PRICE_PER_M = 0.60
DEFAULT_CACHED_PROMPT_PRICE_PER_M = 0.0375


class TokenTracker:
    """Thread-safe, async-safe central token ledger for the Triad Swarm."""

    def __init__(
        self,
        prompt_price_per_m: float = DEFAULT_PROMPT_PRICE_PER_M,
        completion_price_per_m: float = DEFAULT_COMPLETION_PRICE_PER_M,
        cached_price_per_m: float = DEFAULT_CACHED_PROMPT_PRICE_PER_M,
    ):
        self.prompt_price_per_m = prompt_price_per_m
        self.completion_price_per_m = completion_price_per_m
        self.cached_price_per_m = cached_price_per_m

        self._records: List[TokenRecord] = []
        self._zero_token_passes: int = 0
        self._cache_hits: int = 0
        self._cache_tokens_saved: int = 0
        self._traceback_tokens_saved: int = 0
        self._lock = threading.Lock()

    def record_usage(
        self,
        agent_id: str,
        phase: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int = 0,
        duration_seconds: float = 0.0,
        metadata: Optional[Dict[str, str]] = None,
    ) -> TokenRecord:
        """Record an LLM token transaction and calculate USD cost."""
        net_prompt = max(0, prompt_tokens - cached_tokens)
        cost = (
            (net_prompt / 1_000_000.0) * self.prompt_price_per_m
            + (cached_tokens / 1_000_000.0) * self.cached_price_per_m
            + (completion_tokens / 1_000_000.0) * self.completion_price_per_m
        )
        total = prompt_tokens + completion_tokens

        record = TokenRecord(
            agent_id=agent_id,
            phase=phase,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            total_tokens=total,
            duration_seconds=duration_seconds,
            cost_usd=round(cost, 6),
            metadata=metadata or {},
        )

        with self._lock:
            self._records.append(record)

        return record

    def record_zero_token_event(self, agent_id: str = "verifier", reason: str = "deterministic_pass") -> None:
        """Explicitly log a deterministic 0-token verification or cache event."""
        with self._lock:
            self._zero_token_passes += 1

    def record_cache_hit(self, agent_id: str, tokens_saved: int) -> None:
        """Record an exact prompt cache hit."""
        with self._lock:
            self._cache_hits += 1
            self._cache_tokens_saved += tokens_saved

    def record_traceback_pruning_savings(self, tokens_saved: int) -> None:
        """Record tokens eliminated by the TracebackPruner."""
        with self._lock:
            self._traceback_tokens_saved += tokens_saved

    @property
    def total_prompt_tokens(self) -> int:
        with self._lock:
            return sum(r.prompt_tokens for r in self._records)

    @property
    def total_completion_tokens(self) -> int:
        with self._lock:
            return sum(r.completion_tokens for r in self._records)

    @property
    def total_cached_tokens(self) -> int:
        with self._lock:
            return sum(r.cached_tokens for r in self._records)

    @property
    def total_tokens(self) -> int:
        with self._lock:
            return sum(r.total_tokens for r in self._records)

    @property
    def total_cost_usd(self) -> float:
        with self._lock:
            return sum(r.cost_usd for r in self._records)

    @property
    def zero_token_events(self) -> int:
        with self._lock:
            return self._zero_token_passes

    @property
    def cache_hits(self) -> int:
        with self._lock:
            return self._cache_hits

    @property
    def cache_tokens_saved(self) -> int:
        with self._lock:
            return self._cache_tokens_saved

    @property
    def traceback_tokens_saved(self) -> int:
        with self._lock:
            return self._traceback_tokens_saved

    def get_summary_by_phase(self) -> Dict[str, Dict[str, float]]:
        """Group usage by execution phase."""
        summary: Dict[str, Dict[str, float]] = {}
        with self._lock:
            for r in self._records:
                if r.phase not in summary:
                    summary[r.phase] = {
                        "count": 0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "cached_tokens": 0,
                        "total_tokens": 0,
                        "cost_usd": 0.0,
                    }
                summary[r.phase]["count"] += 1
                summary[r.phase]["prompt_tokens"] += r.prompt_tokens
                summary[r.phase]["completion_tokens"] += r.completion_tokens
                summary[r.phase]["cached_tokens"] += r.cached_tokens
                summary[r.phase]["total_tokens"] += r.total_tokens
                summary[r.phase]["cost_usd"] += r.cost_usd

        return summary

    def get_summary_by_agent(self) -> Dict[str, Dict[str, float]]:
        """Group usage by specific agent."""
        summary: Dict[str, Dict[str, float]] = {}
        with self._lock:
            for r in self._records:
                if r.agent_id not in summary:
                    summary[r.agent_id] = {
                        "calls": 0,
                        "total_tokens": 0,
                        "cost_usd": 0.0,
                    }
                summary[r.agent_id]["calls"] += 1
                summary[r.agent_id]["total_tokens"] += r.total_tokens
                summary[r.agent_id]["cost_usd"] += r.cost_usd
        return summary

    def generate_markdown_report(self) -> str:
        """Format token metrics into a clean Markdown table with cache and pruning stats."""
        phase_stats = self.get_summary_by_phase()
        lines = [
            "### 📊 Triad Swarm Token Economics Report",
            "",
            "| Phase | Invocations | Prompt Tokens | Completion Tokens | Total Tokens | Zero-Token Passes | Est. Cost ($) |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
        for phase, data in phase_stats.items():
            lines.append(
                f"| `{phase}` | {int(data['count'])} | {int(data['prompt_tokens']):,} | "
                f"{int(data['completion_tokens']):,} | **{int(data['total_tokens']):,}** | "
                f"— | ${data['cost_usd']:.4f} |"
            )

        # Append zero-token verifications
        lines.append(
            f"| `deterministic_verifier` | {self._zero_token_passes} | 0 | 0 | **0** | {self._zero_token_passes} | $0.0000 |"
        )
        lines.append(
            f"| **TOTAL** | **{len(self._records) + self._zero_token_passes}** | "
            f"**{self.total_prompt_tokens:,}** | **{self.total_completion_tokens:,}** | "
            f"**{self.total_tokens:,}** | **{self._zero_token_passes}** | **${self.total_cost_usd:.4f}** |"
        )

        # Add advanced optimizations summary
        if self._cache_hits > 0 or self._traceback_tokens_saved > 0:
            lines.extend([
                "",
                "#### ⚡ Efficiency Gains",
                f"- **Exact Prompt Cache Hits:** `{self._cache_hits}` hits ({self._cache_tokens_saved:,} tokens saved)",
                f"- **Traceback Pruning Savings:** `{self._traceback_tokens_saved:,}` tokens eliminated from retry prompts",
            ])

        return "\n".join(lines)
