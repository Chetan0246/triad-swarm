"""Distributed tracing, span metrics, and Perfetto / Chrome trace event exporters."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TraceSpan(BaseModel):
    """An individual operation span in the swarm lifecycle."""

    name: str
    phase: str
    agent_id: str
    start_time: float
    end_time: float = 0.0
    duration_seconds: float = 0.0
    status: str = "running"
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def finish(self, status: str = "success", metadata: Optional[Dict[str, Any]] = None) -> None:
        self.end_time = time.time()
        self.duration_seconds = max(0.0, self.end_time - self.start_time)
        self.status = status
        if metadata:
            self.metadata.update(metadata)


class SwarmTracer:
    """
    Records microsecond-precision trace spans across Architect, Workers, and Verifiers.
    Exports to Chrome Trace Event format (viewable in chrome://tracing or perfetto.dev)
    and Mermaid Gantt timeline.
    """

    def __init__(self, trace_name: str = "triad_swarm_run"):
        self.trace_name = trace_name
        self._spans: List[TraceSpan] = []
        self._lock = threading.Lock()
        self.start_wall_clock = time.time()

    def start_span(self, name: str, phase: str, agent_id: str, metadata: Optional[Dict[str, Any]] = None) -> TraceSpan:
        """Create and begin a new trace span."""
        span = TraceSpan(
            name=name,
            phase=phase,
            agent_id=agent_id,
            start_time=time.time(),
            metadata=metadata or {},
        )
        with self._lock:
            self._spans.append(span)
        return span

    def get_spans(self) -> List[TraceSpan]:
        with self._lock:
            return list(self._spans)

    def export_chrome_trace(self, output_path: str) -> None:
        """
        Export spans to Chrome Trace Event Format.
        Can be dragged directly into chrome://tracing or https://ui.perfetto.dev.
        """
        trace_events = []
        thread_ids: Dict[str, int] = {}
        with self._lock:
            for s in self._spans:
                # Ph: 'X' is Complete event (start and duration in microseconds)
                ts_micro = int((s.start_time - self.start_wall_clock) * 1_000_000)
                dur_micro = int(s.duration_seconds * 1_000_000)

                # Chrome Trace Event Format requires integer thread IDs; assign a
                # stable integer per agent for this export.
                tid = thread_ids.setdefault(s.agent_id, len(thread_ids) + 1)
                trace_events.append(
                    {
                        "name": s.name,
                        "cat": s.phase,
                        "ph": "X",
                        "ts": max(0, ts_micro),
                        "dur": max(10, dur_micro),
                        "pid": 1,
                        "tid": tid,
                        "args": {
                            "status": s.status,
                            **{k: str(v) for k, v in s.metadata.items()},
                        },
                    }
                )

        p = Path(output_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"traceEvents": trace_events, "displayTimeUnit": "ms"}, indent=2), encoding="utf-8")

    def generate_mermaid_gantt(self) -> str:
        """Generate a Mermaid Gantt diagram visualizing concurrent agent execution."""
        lines = [
            "gantt",
            f"    title Swarm Execution Timeline: {self.trace_name}",
            "    dateFormat X",
            "    axisFormat %s s",
            "    section Architect",
        ]

        with self._lock:
            # Sort spans by start time
            sorted_spans = sorted(self._spans, key=lambda s: s.start_time)
            sections_added = {"Architect"}

            for s in sorted_spans:
                sec_name = s.phase.title()
                if sec_name not in sections_added:
                    lines.append(f"    section {sec_name}")
                    sections_added.add(sec_name)

                start_rel = int((s.start_time - self.start_wall_clock) * 1000)
                dur_rel = max(10, int(s.duration_seconds * 1000))
                end_rel = start_rel + dur_rel

                status_modifier = "crit, " if s.status == "failure" else "active, " if s.status == "healing" else ""
                clean_name = s.name.replace(":", " ").replace("#", "")
                lines.append(f"    {clean_name} :{status_modifier}{start_rel}, {end_rel}")

        return "\n".join(lines)
