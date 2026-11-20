"""TriadEngine: High-throughput async DAG orchestrator with 0-token verification gates, prompt caching, and distributed tracing."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from triad.agents.architect import ArchitectAgent
from triad.agents.verifier import DeterministicVerifier
from triad.agents.worker import WorkerAgent
from triad.core.cache import PromptCacheManager
from triad.core.llm import BaseLLMProvider, CachedLLMProvider, get_llm_provider
from triad.core.models import ExecutionResult, SwarmMetrics, TaskSlice, VerificationResult, WorkloadSpec
from triad.core.sandbox import IsolatedSandbox
from triad.core.telemetry import SwarmTracer
from triad.core.token_tracker import TokenTracker
from triad.orchestrator.scheduler import DAGScheduler


class TriadEngine:
    """Core orchestrator executing the advanced Triad Swarm pattern."""

    def __init__(
        self,
        llm: Optional[BaseLLMProvider] = None,
        max_concurrency: int = 4,
        max_healing_attempts: int = 3,
        output_dir: Optional[str] = None,
        enable_cache: bool = True,
        cache_dir: Optional[str] = None,
        trace_output_path: Optional[str] = None,
        enable_tracing: bool = True,
    ):
        raw_llm = llm or get_llm_provider()
        self.enable_cache = enable_cache
        if enable_cache and not isinstance(raw_llm, CachedLLMProvider):
            self.cache_manager = PromptCacheManager(cache_dir=cache_dir)
            self.llm: BaseLLMProvider = CachedLLMProvider(raw_llm, cache=self.cache_manager)
        else:
            self.cache_manager = getattr(raw_llm, "cache", None) or PromptCacheManager()
            self.llm = raw_llm

        self.max_concurrency = max_concurrency
        self.max_healing_attempts = max_healing_attempts
        self.output_dir = output_dir
        self.trace_output_path = trace_output_path
        self.enable_tracing = enable_tracing

        self.tracker = TokenTracker()
        self.tracer = SwarmTracer(trace_name="triad_swarm_engine")
        self.architect = ArchitectAgent(llm=self.llm, tracker=self.tracker)
        self.verifier = DeterministicVerifier(tracker=self.tracker)
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def execute_workload(self, spec: WorkloadSpec) -> SwarmMetrics:
        """Execute complete end-to-end workload through the DAG-scheduled Triad Swarm."""
        start_time = time.perf_counter()
        workload_span = self.tracer.start_span(
            name=f"Workload: {spec.name}",
            phase="orchestration",
            agent_id="engine",
            metadata={"spec_name": spec.name},
        )

        # Step 1: Architect Decomposition
        arch_span = self.tracer.start_span(
            name="Architect Decomposition",
            phase="architect",
            agent_id=self.architect.agent_id,
        )
        slices = await self.architect.decompose_workload(spec)
        arch_span.finish(status="success", metadata={"slice_count": len(slices)})

        if not slices:
            workload_span.finish(status="failure")
            raise ValueError(f"Architect failed to produce any task slices for workload: {spec.name}")

        # Step 2: DAG Dependency Resolution and Topological Wave Planning
        scheduler = DAGScheduler(slices)
        slice_events: Dict[str, asyncio.Event] = {s.slice_id: asyncio.Event() for s in slices}
        verified_sandboxes: Dict[str, IsolatedSandbox] = {}
        failed_slices: Set[str] = set()

        # Step 3: Reactive Parallel Streaming Fan-Out
        async def run_slice_task(slice_item: TaskSlice, index: int) -> Tuple[Optional[ExecutionResult], Optional[VerificationResult], Optional[IsolatedSandbox], float]:
            try:
                # Wait for all direct upstream dependencies to complete successfully
                for dep_id in slice_item.dependencies:
                    if dep_id in failed_slices:
                        failed_slices.add(slice_item.slice_id)
                        slice_events[slice_item.slice_id].set()
                        return None, None, None, 0.0
                    await slice_events[dep_id].wait()
                    if dep_id in failed_slices:
                        failed_slices.add(slice_item.slice_id)
                        slice_events[slice_item.slice_id].set()
                        return None, None, None, 0.0

                exec_res, verif_res, sand, elapsed = await self._process_slice_with_concurrency(
                    task_slice=slice_item,
                    worker_index=index,
                    upstream_sandboxes=[verified_sandboxes[d] for d in slice_item.dependencies if d in verified_sandboxes],
                )

                if verif_res and verif_res.passed and sand:
                    verified_sandboxes[slice_item.slice_id] = sand
                else:
                    failed_slices.add(slice_item.slice_id)

                slice_events[slice_item.slice_id].set()
                return exec_res, verif_res, sand, elapsed
            except Exception as e:
                failed_slices.add(slice_item.slice_id)
                slice_events[slice_item.slice_id].set()
                raise e

        worker_tasks = [
            run_slice_task(slice_item, idx)
            for idx, slice_item in enumerate(slices)
        ]

        # Slices run reactively as soon as their dependencies are ready
        results = await asyncio.gather(*worker_tasks, return_exceptions=True)

        successful_slices = 0
        cumulative_worker_time = 0.0

        for idx, res in enumerate(results):
            if isinstance(res, Exception) or res is None:
                continue
            exec_res, verif_res, sand, worker_elapsed = res
            cumulative_worker_time += worker_elapsed

            if verif_res and verif_res.passed and sand:
                successful_slices += 1
                if self.output_dir:
                    sand.sync_to(self.output_dir)

        # Cleanup sandboxes
        for sand in verified_sandboxes.values():
            sand.close()

        total_wall_clock = time.perf_counter() - start_time
        speedup = (
            cumulative_worker_time / total_wall_clock
            if total_wall_clock > 0 and cumulative_worker_time > 0
            else 1.0
        )
        success_rate = (successful_slices / len(slices)) * 100.0 if slices else 0.0

        workload_span.finish(status="success" if successful_slices == len(slices) else "partial")

        # Export trace if requested
        if self.trace_output_path:
            self.tracer.export_chrome_trace(self.trace_output_path)

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
            cache_hits=self.tracker.cache_hits,
            cache_tokens_saved=self.tracker.cache_tokens_saved,
            execution_waves=len(scheduler.waves),
            traceback_tokens_saved=self.tracker.traceback_tokens_saved,
            trace_events=[s.model_dump() for s in self.tracer.get_spans()],
        )

        return metrics

    async def _process_slice_with_concurrency(
        self,
        task_slice: TaskSlice,
        worker_index: int,
        upstream_sandboxes: Optional[List[IsolatedSandbox]] = None,
    ) -> Tuple[ExecutionResult, VerificationResult, IsolatedSandbox, float]:
        """Acquire semaphore and execute worker implementation + verification loop with artifact cascading."""
        async with self.semaphore:
            worker_t0 = time.perf_counter()
            worker_id = f"worker_{worker_index+1}_{task_slice.slice_id}"
            worker = WorkerAgent(worker_id=worker_id, llm=self.llm, tracker=self.tracker)

            sandbox = IsolatedSandbox(
                cleanup=False,
                allowed_files=task_slice.target_files + list(task_slice.acceptance_tests.keys()),
            )

            # Artifact Cascading: mount upstream verified dependencies into this sandbox
            if upstream_sandboxes:
                for up_sand in upstream_sandboxes:
                    sandbox.mount_artifacts_from(up_sand)

            error_trace: Optional[str] = None
            exec_res: Optional[ExecutionResult] = None
            verif_res: Optional[VerificationResult] = None

            span = self.tracer.start_span(
                name=f"Slice {task_slice.slice_id}",
                phase="worker",
                agent_id=worker_id,
                metadata={"title": task_slice.title},
            )

            for attempt in range(1, self.max_healing_attempts + 1):
                attempt_phase = "execution" if attempt == 1 else "healing"
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
                verif_res = self.verifier.verify(task_slice, sandbox, timeout_seconds=task_slice.timeout_seconds)
                if verif_res.passed:
                    break
                else:
                    # Use pruned traceback to reduce token consumption on healing
                    error_trace = verif_res.pruned_traceback or verif_res.failure_trace

            assert exec_res is not None
            assert verif_res is not None
            worker_elapsed = time.perf_counter() - worker_t0
            span.finish(status="success" if verif_res.passed else "failure", metadata={"attempts": exec_res.iterations})

            return exec_res, verif_res, sandbox, worker_elapsed
