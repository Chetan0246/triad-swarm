"""FastAPI Production Server for Triad Swarm."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from triad import __version__
from triad.agents.spec_generator import SpecGeneratorAgent
from triad.core.cache import PromptCacheManager
from triad.core.llm import (
    MockLLMProvider,
    populate_mock_telemetry_defaults,
)
from triad.core.logging import get_logger
from triad.core.models import WorkloadSpec
from triad.core.router import ModelRouter
from triad.orchestrator.engine import TriadEngine
from triad.server.metrics import metrics_registry
from triad.server.state import JobStatus, job_manager

logger = get_logger("server.api")

app = FastAPI(
    title="Triad Swarm Engine API",
    description="High-Throughput, Zero-Token Verification Multi-Agent Swarm Production Daemon",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for dashboards, monitoring frontends, and external microservices.
# The API is token/header based rather than cookie based, so credentials must be
# disabled: browsers reject a wildcard origin combined with credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

SERVER_START_TIME = time.time()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class CreateJobRequest(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    workload_spec: Optional[Dict[str, Any]] = None
    concurrency: int = Field(default_factory=lambda: _env_int("TRIAD_CONCURRENCY", 4), ge=1, le=32)
    provider_name: str = "mock"
    architect_model: Optional[str] = None
    worker_model: Optional[str] = None
    output_dir: Optional[str] = None
    enable_cache: bool = Field(default_factory=lambda: _env_bool("TRIAD_ENABLE_CACHE", True))
    async_mode: bool = True


class JobResponse(BaseModel):
    job_id: str
    name: str
    status: JobStatus
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration_seconds: Optional[float] = None
    metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    artifacts: List[str] = Field(default_factory=list)


@app.get("/healthz", tags=["Probes"])
async def health_check() -> Dict[str, Any]:
    """Kubernetes liveness probe."""
    return {
        "status": "healthy",
        "service": "triad-swarm",
        "version": __version__,
        "uptime_seconds": round(time.time() - SERVER_START_TIME, 2),
    }


@app.get("/readyz", tags=["Probes"])
async def readiness_check() -> Dict[str, Any]:
    """Kubernetes readiness probe."""
    return {
        "status": "ready",
        "active_jobs": len(job_manager._tasks),
        "total_jobs_tracked": len(job_manager._jobs),
    }


@app.get("/metrics", response_class=PlainTextResponse, tags=["Observability"])
async def prometheus_metrics() -> PlainTextResponse:
    """Prometheus OpenMetrics exposition endpoint."""
    text_content = metrics_registry.to_prometheus_text()
    return PlainTextResponse(
        content=text_content,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


async def _execute_swarm_job(job_id: str, req: CreateJobRequest, spec: WorkloadSpec) -> None:
    """Background task runner for executing a swarm job."""
    record = job_manager.get_job(job_id)
    if not record:
        return

    record.status = JobStatus.RUNNING
    record.started_at = time.time()
    await job_manager.emit_event(
        job_id,
        "job_started",
        f"Execution initiated with concurrency {req.concurrency}",
        {"spec_name": spec.name, "concurrency": req.concurrency},
    )

    try:
        # Configure model routing with a shared cache so the engine and router
        # do not maintain two independent caches.
        cache_manager = (
            PromptCacheManager(cache_dir=os.environ.get("TRIAD_CACHE_DIR") or None) if req.enable_cache else None
        )
        router = ModelRouter(
            architect_spec=req.architect_model or req.provider_name,
            worker_spec=req.worker_model or req.provider_name,
            enable_cache=req.enable_cache,
            cache_manager=cache_manager,
        )

        arch_llm = router.get_architect_llm()
        raw_arch = getattr(arch_llm, "provider", arch_llm)
        if isinstance(raw_arch, MockLLMProvider):
            populate_mock_telemetry_defaults(raw_arch)
        raw_worker = getattr(router.get_worker_llm(), "provider", router.get_worker_llm())
        if isinstance(raw_worker, MockLLMProvider):
            populate_mock_telemetry_defaults(raw_worker)

        engine = TriadEngine(
            router=router,
            max_concurrency=req.concurrency,
            output_dir=req.output_dir or f"out/{job_id}",
            enable_cache=req.enable_cache,
        )

        metrics = await engine.execute_workload(spec)

        record.status = JobStatus.COMPLETED
        record.completed_at = time.time()
        record.duration_seconds = record.completed_at - record.started_at
        cache_hits_val = getattr(metrics, "cache_hits", 0)
        if cache_hits_val == 0 and engine.cache_manager:
            cache_hits_val = getattr(engine.cache_manager, "total_hits", 0)

        record.metrics = {
            "wall_clock_seconds": metrics.wall_clock_seconds,
            "total_tokens": metrics.total_tokens,
            "zero_token_verifications": metrics.zero_token_verifications,
            "tasks_total": metrics.tasks_total,
            "tasks_succeeded": metrics.tasks_succeeded,
            "estimated_cost_usd": metrics.estimated_cost_usd,
            "cache_hits": cache_hits_val,
        }

        # Update global Prometheus registry
        metrics_registry.record_job_completed(record.duration_seconds)
        phase_summary = engine.tracker.get_summary_by_phase()
        arch_tokens = int(phase_summary.get("architect", {}).get("total_tokens", 0))
        # Include healing/verifier phases in the worker token counter instead of
        # only counting the literal "worker" phase.
        worker_tokens = max(0, metrics.total_tokens - arch_tokens)
        metrics_registry.record_tokens("architect", arch_tokens)
        metrics_registry.record_tokens("worker", worker_tokens)
        for _ in range(metrics.zero_token_verifications):
            metrics_registry.record_verification(passed=True)

        # Collect written artifacts if output directory exists
        out_p = req.output_dir or f"out/{job_id}"
        if os.path.exists(out_p):
            for root, _, files in os.walk(out_p):
                for f in files:
                    rel = os.path.relpath(os.path.join(root, f), out_p)
                    record.artifacts.append(rel)

        await job_manager.emit_event(
            job_id,
            "job_completed",
            f"Job completed successfully in {record.duration_seconds:.2f}s",
            record.metrics,
        )
    except asyncio.CancelledError:
        # ``JobManager.cancel_job`` already marks the job cancelled and emits an
        # event; avoid double-counting metrics and duplicating the event.
        if record.status != JobStatus.CANCELLED:
            record.status = JobStatus.CANCELLED
            record.completed_at = time.time()
            if record.started_at:
                record.duration_seconds = record.completed_at - record.started_at
            metrics_registry.record_job_cancelled()
            await job_manager.emit_event(job_id, "job_cancelled", "Job cancelled during execution.")
    except Exception as e:
        record.status = JobStatus.FAILED
        record.completed_at = time.time()
        if record.started_at:
            record.duration_seconds = record.completed_at - record.started_at
        record.error = str(e)
        metrics_registry.record_job_failed(record.duration_seconds)
        await job_manager.emit_event(job_id, "job_failed", f"Job failed: {str(e)}", {"error": str(e)})
        logger.error(f"Error executing job {job_id}: {e}", exc_info=True)
    finally:
        job_manager.unregister_task(job_id)


@app.post("/api/v1/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED, tags=["Jobs"])
async def submit_job(req: CreateJobRequest, background_tasks: BackgroundTasks) -> JobResponse:
    """Submit a workload specification or natural language prompt for parallel swarm execution."""
    if not req.workload_spec and not req.prompt:
        raise HTTPException(status_code=400, detail="Must provide either 'workload_spec' or 'prompt'.")

    # Generate workload spec from prompt if prompt was provided
    if req.prompt and not req.workload_spec:
        router = ModelRouter(
            architect_spec=req.architect_model or req.provider_name,
            worker_spec=req.worker_model or req.provider_name,
            enable_cache=req.enable_cache,
        )
        arch_llm = router.get_architect_llm()
        raw_arch = getattr(arch_llm, "provider", arch_llm)
        if isinstance(raw_arch, MockLLMProvider):
            populate_mock_telemetry_defaults(raw_arch)

        gen = SpecGeneratorAgent(llm=arch_llm)
        try:
            spec = await gen.generate_spec(
                req.prompt,
                suggested_name=req.name or "dynamic-job",
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to generate workload spec from prompt: {exc}") from exc
    else:
        try:
            spec = WorkloadSpec(**req.workload_spec)  # type: ignore[arg-type]
        except (ValidationError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid workload_spec: {exc}") from exc

    record = job_manager.create_job(
        name=spec.name,
        workload_spec=spec.model_dump(),
        output_dir=req.output_dir,
    )

    if req.async_mode:
        task = asyncio.create_task(_execute_swarm_job(record.job_id, req, spec))
        job_manager.register_task(record.job_id, task)
    else:
        # Synchronous mode (waits for completion)
        await _execute_swarm_job(record.job_id, req, spec)
        record = job_manager.get_job(record.job_id) or record

    return JobResponse(
        job_id=record.job_id,
        name=record.name,
        status=record.status,
        created_at=record.created_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
        duration_seconds=record.duration_seconds,
        metrics=record.metrics,
        error=record.error,
        artifacts=record.artifacts,
    )


@app.get("/api/v1/jobs", response_model=List[JobResponse], tags=["Jobs"])
async def list_jobs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> List[JobResponse]:
    """List recent swarm jobs."""
    jobs = job_manager.list_jobs(limit=limit, offset=offset)
    return [
        JobResponse(
            job_id=j.job_id,
            name=j.name,
            status=j.status,
            created_at=j.created_at,
            started_at=j.started_at,
            completed_at=j.completed_at,
            duration_seconds=j.duration_seconds,
            metrics=j.metrics,
            error=j.error,
            artifacts=j.artifacts,
        )
        for j in jobs
    ]


@app.get("/api/v1/jobs/{job_id}", response_model=JobResponse, tags=["Jobs"])
async def get_job(job_id: str) -> JobResponse:
    """Retrieve full details, metrics, and artifact status for a specific job."""
    record = job_manager.get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return JobResponse(
        job_id=record.job_id,
        name=record.name,
        status=record.status,
        created_at=record.created_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
        duration_seconds=record.duration_seconds,
        metrics=record.metrics,
        error=record.error,
        artifacts=record.artifacts,
    )


@app.post("/api/v1/jobs/{job_id}/cancel", tags=["Jobs"])
async def cancel_job(job_id: str) -> Dict[str, Any]:
    """Gracefully cancel an active running swarm job."""
    success = job_manager.cancel_job(job_id)
    if not success:
        record = job_manager.get_job(job_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
        return {"job_id": job_id, "status": record.status, "message": "Job is not actively running."}
    return {"job_id": job_id, "status": JobStatus.CANCELLED, "message": "Cancellation initiated."}


@app.get("/api/v1/jobs/{job_id}/stream", tags=["Observability"])
async def stream_job_events(job_id: str) -> StreamingResponse:
    """Stream real-time topological events and verification telemetry via Server-Sent Events (SSE)."""
    record = job_manager.get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return StreamingResponse(
        job_manager.subscribe(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
