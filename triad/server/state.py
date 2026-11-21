"""Thread-safe and async-safe Job Manager and Event Bus for Triad Server."""

from __future__ import annotations

import asyncio
import time
import uuid
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional

from pydantic import BaseModel, Field

from triad.core.logging import get_logger
from triad.server.metrics import metrics_registry

logger = get_logger("server.state")


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
TERMINAL_EVENTS = {"job_completed", "job_failed", "job_cancelled"}


class JobEvent(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    event_type: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)


class JobRecord(BaseModel):
    job_id: str
    name: str
    status: JobStatus = JobStatus.QUEUED
    created_at: float = Field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration_seconds: Optional[float] = None
    workload_spec: Dict[str, Any]
    output_dir: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    artifacts: List[str] = Field(default_factory=list)
    events: List[JobEvent] = Field(default_factory=list)


class JobManager:
    """Manages active and historical jobs with pub/sub event streaming."""

    def __init__(self) -> None:
        self._jobs: Dict[str, JobRecord] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    def create_job(self, name: str, workload_spec: Dict[str, Any], output_dir: Optional[str] = None) -> JobRecord:
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        record = JobRecord(
            job_id=job_id,
            name=name,
            workload_spec=workload_spec,
            output_dir=output_dir,
        )
        self._jobs[job_id] = record
        self._subscribers[job_id] = []
        metrics_registry.set_active_jobs(len(self._tasks))
        logger.info(f"Created job {job_id}: '{name}'", extra={"extra_fields": {"job_id": job_id}})
        return record

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 50, offset: int = 0) -> List[JobRecord]:
        all_jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return all_jobs[offset : offset + limit]

    def register_task(self, job_id: str, task: asyncio.Task) -> None:
        self._tasks[job_id] = task
        metrics_registry.set_active_jobs(len(self._tasks))

    def unregister_task(self, job_id: str) -> None:
        self._tasks.pop(job_id, None)
        metrics_registry.set_active_jobs(len(self._tasks))

    async def emit_event(
        self, job_id: str, event_type: str, message: str, data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Broadcast an event to job history and all active SSE subscribers."""
        record = self.get_job(job_id)
        evt = JobEvent(
            event_type=event_type,
            message=message,
            data=data or {},
        )
        if record:
            record.events.append(evt)

        queues = self._subscribers.get(job_id, [])
        for q in list(queues):
            try:
                await q.put(evt)
            except Exception:
                pass

    async def subscribe(self, job_id: str) -> AsyncGenerator[str, None]:
        """Subscribe to real-time events for a job via Server-Sent Events."""
        record = self.get_job(job_id)
        if not record:
            return

        # Snapshot and replay existing events
        existing_events = list(record.events)
        for existing in existing_events:
            yield f"data: {existing.model_dump_json()}\n\n"

        # Return immediately if record is already in terminal status (avoid SSE hang)
        if record.status in TERMINAL_STATUSES:
            return

        queue: asyncio.Queue[JobEvent] = asyncio.Queue()
        if job_id not in self._subscribers:
            self._subscribers[job_id] = []
        self._subscribers[job_id].append(queue)

        try:
            if record.status in TERMINAL_STATUSES:
                while not queue.empty():
                    evt = queue.get_nowait()
                    yield f"data: {evt.model_dump_json()}\n\n"
                return

            while True:
                evt = await queue.get()
                yield f"data: {evt.model_dump_json()}\n\n"
                if evt.event_type in TERMINAL_EVENTS:
                    break
        finally:
            if job_id in self._subscribers and queue in self._subscribers[job_id]:
                self._subscribers[job_id].remove(queue)

    def cancel_job(self, job_id: str) -> bool:
        record = self.get_job(job_id)
        if not record:
            return False

        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            record.status = JobStatus.CANCELLED
            record.completed_at = time.time()
            if record.started_at:
                record.duration_seconds = record.completed_at - record.started_at
            metrics_registry.record_job_cancelled()
            self.unregister_task(job_id)
            asyncio.create_task(self.emit_event(job_id, "job_cancelled", f"Job {job_id} cancelled by user request."))
            return True
        return False


# Global JobManager instance
job_manager = JobManager()
