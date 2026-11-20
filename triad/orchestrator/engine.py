"""TriadEngine: High-throughput async parallel orchestrator with 0-token verification gates."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Dict, List, Optional
from triad.agents.architect import ArchitectAgent
from triad.agents.verifier import DeterministicVerifier
from triad.agents.worker import WorkerAgent
from triad.core.llm import BaseLLMProvider, get_llm_provider
from triad.core.models import ExecutionResult, SwarmMetrics, TaskSlice, VerificationResult, WorkloadSpec
from triad.core.sandbox import IsolatedSandbox
from triad.core.token_tracker import TokenTracker


class TriadEngine:
    """Core orchestrator executing the Triad Swarm pattern."""

    def __init__(
        self,
        llm: Optional[BaseLLMProvider] = None,
        max_concurrency: int = 4,
        max_healing_attempts: int = 2,
        output_dir: Optional[str] = None,
    ):
        self.llm = llm or get_llm_provider()
        self.max_concurrency = max_concurrency
        self.max_healing_attempts = max_healing_attempts
        self.output_dir = output_dir

        self.tracker = TokenTracker()
        self.architect = ArchitectAgent(llm=self.llm, tracker=self.tracker)
        self.verifier = DeterministicVerifier(tracker=self.tracker)
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def execute_workload(self, spec: WorkloadSpec) -> SwarmMetrics:
        """Execute complete end-to-end workload through the Triad Swarm."""
        start_time = time.perf_counter()

        # Step 1: Architect Decomposition
        slices = await self.architect.decompose_workload(spec)
        if not slices:
            raise ValueError(f"Architect failed to produce any task slices for workload: {spec.name}")

        # Step 2: Parallel Async Worker Fan-out
        worker_tasks = [
            self._process_slice_with_concurrency(slice_item, idx)
            for idx, slice_item in enumerate(slices)
        ]

        results = await asyncio.gather(*worker_tasks, return_exceptions=True)

        # Collect results and sync to target directory if specified
        successful_slices = 0
        cumulative_worker_time = 0.0

        for idx, res in enumerate(results):
            if isinstance(res, Exception):
                continue
            exec_res, verif_res, sand, worker_elapsed = res
            cumulative_worker_time += worker_elapsed
            if verif_res.passed:
                successful_slices += 1
                if self.output_dir:
                    sand.sync_to(self.output_dir)
            sand.close()

        total_wall_clock = time.perf_counter() - start_time
        speedup = (
            cumulative_worker_time / total_wall_clock
            if total_wall_clock > 0 and cumulative_worker_time > 0
            else 1.0
        )
        success_rate = (successful_slices / len(slices)) * 100.0 if slices else 0.0

        # Compute consolidated metrics
        metrics = SwarmMetrics(
            workload_name=spec.name,
            total_agents_invoked=1 + len(slices),  # 1 Architect + N isolated Workers
            active_worker_concurrency=min(self.max_concurrency, len(slices)),
            wall_clock_seconds=round(total_wall_clock, 3),
            cumulative_worker_seconds=round(cumulative_worker_time, 3),
            parallel_speedup=round(speedup, 2),
            total_tokens=self.tracker.total_tokens,
            prompt_tokens=self.tracker.total_prompt_tokens,
            completion_tokens=self.tracker.total_completion_tokens,
            cached_tokens=self.tracker.total_cached_tokens,
            zero_token_verifications=self.tracker.zero_token_events,
            llm_verifications=0,  # 0 LLM verifications!
            tasks_total=len(slices),
            tasks_succeeded=successful_slices,
            success_rate=round(success_rate, 2),
            estimated_cost_usd=round(self.tracker.total_cost_usd, 5),
        )

        return metrics

    async def _process_slice_with_concurrency(
        self,
        task_slice: TaskSlice,
        worker_index: int,
    ) -> tuple[ExecutionResult, VerificationResult, IsolatedSandbox, float]:
        """Acquire semaphore and execute worker implementation + verification loop."""
        async with self.semaphore:
            worker_t0 = time.perf_counter()
            worker_id = f"worker_{worker_index+1}_{task_slice.slice_id}"
            worker = WorkerAgent(worker_id=worker_id, llm=self.llm, tracker=self.tracker)
            sandbox = IsolatedSandbox(cleanup=False, allowed_files=task_slice.target_files + list(task_slice.acceptance_tests.keys()))

            error_trace: Optional[str] = None
            exec_res: Optional[ExecutionResult] = None
            verif_res: Optional[VerificationResult] = None

            for attempt in range(1, self.max_healing_attempts + 1):
                exec_res = await worker.execute_slice(
                    task_slice=task_slice,
                    sandbox=sandbox,
                    previous_error=error_trace,
                    iteration=attempt,
                )

                if exec_res.status != "success":
                    error_trace = exec_res.error_message or "Worker execution failed"
                    continue

                # Run Deterministic Verifier (0 Tokens)
                verif_res = self.verifier.verify(task_slice, sandbox)
                if verif_res.passed:
                    break
                else:
                    error_trace = verif_res.failure_trace

            assert exec_res is not None
            assert verif_res is not None
            worker_elapsed = time.perf_counter() - worker_t0
            return exec_res, verif_res, sandbox, worker_elapsed
