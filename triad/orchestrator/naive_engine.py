"""NaiveBaselineEngine: Monolithic/Shared-Chat sequential agent for A/B benchmarking."""

from __future__ import annotations

import json
import time
from typing import List, Optional

from triad.core.llm import BaseLLMProvider, get_llm_provider
from triad.core.models import SwarmMetrics, TaskSlice, WorkloadSpec
from triad.core.sandbox import IsolatedSandbox
from triad.core.token_tracker import TokenTracker

NAIVE_SYSTEM_PROMPT = """You are an AI coding assistant in a chat thread.
You have access to the complete conversation history. Implement tasks sequentially as requested."""

CRITIC_SYSTEM_PROMPT = """You are a Code Critic Agent.
Review the following code and write an evaluation report whether it looks correct."""


class NaiveBaselineEngine:
    """Simulates standard sequential agent with shared context and LLM-based verification."""

    def __init__(
        self,
        llm: Optional[BaseLLMProvider] = None,
        slices: Optional[List[TaskSlice]] = None,
    ):
        self.llm = llm or get_llm_provider()
        self.slices = slices or []
        self.tracker = TokenTracker()

    async def execute_workload(self, spec: WorkloadSpec, slices: List[TaskSlice]) -> SwarmMetrics:
        """Run sequential baseline with accumulating conversation history and LLM Critic."""
        start_time = time.perf_counter()

        chat_history: List[str] = [f"Workload: {spec.name}\n{spec.description}"]

        sandbox = IsolatedSandbox(cleanup=True)
        tasks_succeeded = 0
        cumulative_time = 0.0

        for idx, task_slice in enumerate(slices):
            t0 = time.perf_counter()

            # Monolithic context accumulates all prior interactions
            prompt = (
                "Previous Context:\n" + "\n---\n".join(chat_history) + "\n\n"
                f"Now implement Task {idx + 1}: {task_slice.title}\n"
                f"Description: {task_slice.description}\n"
                f"Target Files: {task_slice.target_files}\n"
                f"Return JSON with files."
            )

            # 1. Sequential worker call with bloated context
            resp = await self.llm.generate(
                prompt=prompt,
                system_prompt=NAIVE_SYSTEM_PROMPT,
                json_mode=True,
            )
            worker_duration = time.perf_counter() - t0
            cumulative_time += worker_duration

            self.tracker.record_usage(
                agent_id="naive_monolithic_worker",
                phase="monolithic_chat",
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
                duration_seconds=worker_duration,
            )

            # Append to shared history
            chat_history.append(f"Worker {idx + 1} Output:\n{resp.content[:500]}...")

            # 2. LLM Critic / Verifier (Traditional chat swarm wastes tokens here!)
            t_critic = time.perf_counter()
            critic_prompt = f"Review this code implementation for task {task_slice.title}:\n\n{resp.content}"
            critic_resp = await self.llm.generate(
                prompt=critic_prompt,
                system_prompt=CRITIC_SYSTEM_PROMPT,
            )
            critic_duration = time.perf_counter() - t_critic
            cumulative_time += critic_duration

            self.tracker.record_usage(
                agent_id="naive_llm_critic",
                phase="llm_critic",
                prompt_tokens=critic_resp.prompt_tokens,
                completion_tokens=critic_resp.completion_tokens,
                duration_seconds=critic_duration,
            )

            # Parse and write files, then run tests serially
            try:
                data = json.loads(resp.content)
                files = data.get("files", {})
                for fp, content in files.items():
                    sandbox.write_file(fp, content)
            except Exception:
                pass

            if task_slice.acceptance_tests:
                for test_path, test_code in task_slice.acceptance_tests.items():
                    sandbox.write_file(test_path, test_code)
                test_files = list(task_slice.acceptance_tests.keys())
                sandbox.exec_command(f"python3 -m pytest {' '.join(test_files)} -q --tb=short")

            chat_history.append(f"Critic Review:\n{critic_resp.content[:300]}...")
            tasks_succeeded += 1

        total_wall_clock = time.perf_counter() - start_time
        sandbox.close()

        metrics = SwarmMetrics(
            workload_name=spec.name,
            total_agents_invoked=len(slices) * 2,  # Worker + Critic per task
            active_worker_concurrency=1,  # Strictly sequential
            wall_clock_seconds=round(total_wall_clock, 3),
            cumulative_worker_seconds=round(cumulative_time, 3),
            parallel_speedup=1.0,
            total_tokens=self.tracker.total_tokens,
            prompt_tokens=self.tracker.total_prompt_tokens,
            completion_tokens=self.tracker.total_completion_tokens,
            cached_tokens=0,
            zero_token_verifications=0,
            llm_verifications=len(slices),  # High token waste
            tasks_total=len(slices),
            tasks_succeeded=tasks_succeeded,
            success_rate=100.0 if tasks_succeeded == len(slices) else 0.0,
            estimated_cost_usd=round(self.tracker.total_cost_usd, 5),
        )

        return metrics
