"""TriadEngine: High-throughput async DAG orchestrator with 0-token verification gates, prompt caching, and distributed tracing."""

from __future__ import annotations

import asyncio
import sys
import time
import traceback
from typing import Dict, List, Optional, Set, Tuple

from triad.agents.architect import ArchitectAgent
from triad.agents.verifier import DeterministicVerifier
from triad.agents.worker import WorkerAgent
from triad.core.cache import PromptCacheManager
from triad.core.llm import BaseLLMProvider, CachedLLMProvider, get_llm_provider
from triad.core.models import ExecutionResult, SwarmMetrics, TaskSlice, VerificationResult, WorkloadSpec
from triad.core.router import ModelRouter
from triad.core.sandbox import IsolatedSandbox
from triad.core.telemetry import SwarmTracer
from triad.core.token_tracker import TokenTracker
from triad.orchestrator.scheduler import DAGScheduler


class TriadEngine:
    """Core orchestrator executing the advanced Triad Swarm pattern."""

    def __init__(
        self,
        llm: Optional[BaseLLMProvider] = None,
        architect_llm: Optional[BaseLLMProvider] = None,
        worker_llm: Optional[BaseLLMProvider] = None,
        router: Optional[ModelRouter] = None,
        max_concurrency: int = 4,
        max_healing_attempts: int = 3,
        output_dir: Optional[str] = None,
        enable_cache: bool = True,
        cache_dir: Optional[str] = None,
        trace_output_path: Optional[str] = None,
        enable_tracing: bool = True,
    ):
        self.enable_cache = enable_cache
        self.cache_manager = PromptCacheManager(cache_dir=cache_dir) if enable_cache else None
        self.llm: BaseLLMProvider

        if router:
            self.architect_llm = router.get_architect_llm()
            self.worker_llm = router.get_worker_llm()
            self.llm = self.architect_llm
            # Share the router's cache manager so cache statistics are not split
            # across two independent caches.
            self.cache_manager = getattr(router, "cache_manager", None) or self.cache_manager
        else:
            raw_llm = llm or get_llm_provider()
            if enable_cache and not isinstance(raw_llm, CachedLLMProvider):
                self.llm = CachedLLMProvider(raw_llm, cache=self.cache_manager)
            else:
                self.cache_manager = getattr(raw_llm, "cache", None) or self.cache_manager
                self.llm = raw_llm

            self.architect_llm = architect_llm or self.llm
            self.worker_llm = worker_llm or self.llm

        if max_concurrency < 1:
            raise ValueError(f"max_concurrency must be >= 1, got {max_concurrency}")
        if max_healing_attempts < 1:
            raise ValueError(f"max_healing_attempts must be >= 1, got {max_healing_attempts}")
        self.max_concurrency = max_concurrency
        self.max_healing_attempts = max_healing_attempts
        self.output_dir = output_dir
        self.trace_output_path = trace_output_path
        self.enable_tracing = enable_tracing

        self.tracker = TokenTracker()
        self.tracer = SwarmTracer(trace_name="triad_swarm_engine")
        self.architect = ArchitectAgent(llm=self.architect_llm, tracker=self.tracker)
        self.verifier = DeterministicVerifier(tracker=self.tracker)
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def execute_workload(
        self,
        spec: WorkloadSpec,
        slices: Optional[List[TaskSlice]] = None,
        repo_map: Optional[str] = None,
    ) -> SwarmMetrics:
        """Execute complete end-to-end workload through the DAG-scheduled Triad Swarm."""
        start_time = time.perf_counter()
        workload_span = self.tracer.start_span(
            name=f"Workload: {spec.name}",
            phase="orchestration",
            agent_id="engine",
            metadata={"spec_name": spec.name},
        )

        # Step 1: Architect Decomposition (if not already provided)
        if not slices:
            arch_span = self.tracer.start_span(
                name="Architect Decomposition",
                phase="architect",
                agent_id=self.architect.agent_id,
            )
            slices = await self.architect.decompose_workload(spec, repo_map=repo_map)
            arch_span.finish(status="success", metadata={"slice_count": len(slices)})

        if not slices:
            workload_span.finish(status="failure")
            raise ValueError(f"Architect failed to produce any task slices for workload: {spec.name}")

        # Step 2: DAG Dependency Resolution and Topological Wave Planning
        scheduler = DAGScheduler(slices)
        slice_events: Dict[str, asyncio.Event] = {s.slice_id: asyncio.Event() for s in slices}
        verified_sandboxes: Dict[str, IsolatedSandbox] = {}
        all_sandboxes: List[IsolatedSandbox] = []
        failed_slices: Set[str] = set()

        # Step 3: Reactive Parallel Streaming Fan-Out
        async def run_slice_task(
            slice_item: TaskSlice, index: int
        ) -> Tuple[Optional[ExecutionResult], Optional[VerificationResult], Optional[IsolatedSandbox], float]:
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
                    upstream_sandboxes=[
                        verified_sandboxes[d] for d in slice_item.dependencies if d in verified_sandboxes
                    ],
                )

                if sand is not None:
                    all_sandboxes.append(sand)

                if verif_res and verif_res.passed and sand:
                    verified_sandboxes[slice_item.slice_id] = sand
                else:
                    failed_slices.add(slice_item.slice_id)

                slice_events[slice_item.slice_id].set()
                return exec_res, verif_res, sand, elapsed
            except Exception:
                failed_slices.add(slice_item.slice_id)
                slice_events[slice_item.slice_id].set()
                raise

        worker_tasks = [run_slice_task(slice_item, idx) for idx, slice_item in enumerate(slices)]

        try:
            # Slices run reactively as soon as their dependencies are ready
            results = await asyncio.gather(*worker_tasks, return_exceptions=True)

            successful_slices = 0
            cumulative_worker_time = 0.0

            for _idx, res in enumerate(results):
                if isinstance(res, BaseException):
                    print(f"Error executing slice task: {res!r}", file=sys.stderr)
                    traceback.print_exception(type(res), res, res.__traceback__, file=sys.stderr)
                    continue
                _exec_res, verif_res, sand, worker_elapsed = res
                cumulative_worker_time += worker_elapsed

                if verif_res and verif_res.passed and sand:
                    successful_slices += 1
                    if self.output_dir and sand is not None:
                        sand.sync_to(self.output_dir)
        finally:
            # Ensure all sandboxes (verified or failed) are cleanly closed
            for sand in all_sandboxes:
                sand.close()

        total_wall_clock = time.perf_counter() - start_time
        speedup = (
            cumulative_worker_time / total_wall_clock if total_wall_clock > 0 and cumulative_worker_time > 0 else 1.0
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
    ) -> Tuple[Optional[ExecutionResult], Optional[VerificationResult], Optional[IsolatedSandbox], float]:
        """Acquire semaphore and execute worker implementation + verification loop with artifact cascading."""
        if not task_slice.slice_id or not task_slice.target_files:
            raise ValueError(f"Task slice '{task_slice.slice_id}' is invalid: target_files cannot be empty.")

        async with self.semaphore:
            worker_t0 = time.perf_counter()
            worker_id = f"worker_{worker_index + 1}_{task_slice.slice_id}"
            worker = WorkerAgent(worker_id=worker_id, llm=self.worker_llm, tracker=self.tracker)

            sandbox = IsolatedSandbox(
                cleanup=True,
                allowed_files=task_slice.target_files + list(task_slice.acceptance_tests.keys()),
            )

            try:
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
                    exec_res = await worker.execute_slice(
                        task_slice=task_slice,
                        sandbox=sandbox,
                        previous_error=error_trace,
                        iteration=attempt,
                    )

                    if exec_res.status != "success":
                        error_trace = exec_res.error_message or "Worker execution failed"
                        continue

                    # Run Deterministic Verifier (0 Tokens) off the event loop so
                    # concurrent slices are not serialized by pytest subprocesses.
                    verif_res = await asyncio.to_thread(
                        self.verifier.verify,
                        task_slice,
                        sandbox,
                        timeout_seconds=task_slice.timeout_seconds,
                    )
                    if verif_res.passed:
                        break
                    else:
                        # Use pruned traceback to reduce token consumption on healing
                        error_trace = verif_res.pruned_traceback or verif_res.failure_trace

                if exec_res is None:
                    # Constructor validation guarantees max_healing_attempts >= 1 and that
                    # execute_slice returns or raises; this is a defensive fallback.
                    exec_res = ExecutionResult(
                        slice_id=task_slice.slice_id,
                        worker_id=worker_id,
                        status="error",
                        error_message="Worker produced no execution result",
                    )

                worker_elapsed = time.perf_counter() - worker_t0
                span.finish(
                    status="success" if verif_res is not None and verif_res.passed else "failure",
                    metadata={"attempts": exec_res.iterations},
                )

                # verif_res can be None when every attempt ended before verification
                # (worker returned non-success on all attempts); the caller treats
                # this as a failed slice via `verif_res and verif_res.passed`.
                return exec_res, verif_res, sandbox, worker_elapsed
            except BaseException:
                # The caller only tracks sandboxes that are returned successfully,
                # so close this one here to avoid leaking temp directories on
                # cancellation or unexpected errors.
                sandbox.close()
                raise
