"""Prometheus OpenMetrics exposition registry for Triad Swarm."""

from __future__ import annotations

from typing import Dict, List, Optional


class PrometheusMetricsRegistry:
    """Production Prometheus metric collector and text formatter without third-party dependencies."""

    def __init__(self) -> None:
        self.jobs_total: Dict[str, int] = {
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }
        self.tokens_total: Dict[str, int] = {
            "architect": 0,
            "worker": 0,
        }
        self.verification_events_total: Dict[str, int] = {
            "pass": 0,
            "fail": 0,
        }
        self.cache_hits_total: int = 0
        self.active_jobs: int = 0
        self.job_durations: List[float] = []

    def record_job_completed(self, duration_seconds: float) -> None:
        self.jobs_total["completed"] += 1
        self.observe_duration(duration_seconds)

    def record_job_failed(self, duration_seconds: Optional[float] = None) -> None:
        self.jobs_total["failed"] += 1
        if duration_seconds is not None:
            self.observe_duration(duration_seconds)

    def record_job_cancelled(self) -> None:
        self.jobs_total["cancelled"] += 1

    def record_tokens(self, role: str, count: int) -> None:
        norm_role = "architect" if "arch" in role.lower() else "worker"
        self.tokens_total[norm_role] = self.tokens_total.get(norm_role, 0) + count

    def record_verification(self, passed: bool) -> None:
        key = "pass" if passed else "fail"
        self.verification_events_total[key] += 1

    def record_cache_hit(self) -> None:
        self.cache_hits_total += 1

    def set_active_jobs(self, count: int) -> None:
        self.active_jobs = max(0, count)

    def observe_duration(self, duration: float) -> None:
        self.job_durations.append(duration)
        if len(self.job_durations) > 1000:
            self.job_durations = self.job_durations[-1000:]

    def to_prometheus_text(self) -> str:
        """Format metrics into standard OpenMetrics text representation."""
        lines = []

        # Counter: triad_jobs_total
        lines.append("# HELP triad_jobs_total Total number of swarm workloads processed by outcome.")
        lines.append("# TYPE triad_jobs_total counter")
        for status, count in sorted(self.jobs_total.items()):
            lines.append(f'triad_jobs_total{{status="{status}"}} {count}')

        # Counter: triad_tokens_total
        lines.append("# HELP triad_tokens_total Total tokens consumed segmented by agent role.")
        lines.append("# TYPE triad_tokens_total counter")
        for role, count in sorted(self.tokens_total.items()):
            lines.append(f'triad_tokens_total{{role="{role}"}} {count}')

        # Counter: triad_verification_events_total
        lines.append("# HELP triad_verification_events_total Deterministic 0-token verifier gate events.")
        lines.append("# TYPE triad_verification_events_total counter")
        for outcome, count in sorted(self.verification_events_total.items()):
            lines.append(f'triad_verification_events_total{{status="{outcome}"}} {count}')

        # Counter: triad_cache_hits_total
        lines.append("# HELP triad_cache_hits_total Total multi-tier prompt cache hits (<1ms latency).")
        lines.append("# TYPE triad_cache_hits_total counter")
        lines.append(f"triad_cache_hits_total {self.cache_hits_total}")

        # Gauge: triad_active_jobs
        lines.append("# HELP triad_active_jobs Currently active running swarm workloads.")
        lines.append("# TYPE triad_active_jobs gauge")
        lines.append(f"triad_active_jobs {self.active_jobs}")

        # Summary / Histogram metrics: triad_job_duration_seconds
        lines.append("# HELP triad_job_duration_seconds Summary of swarm workload completion durations.")
        lines.append("# TYPE triad_job_duration_seconds summary")
        count = len(self.job_durations)
        total_sum = sum(self.job_durations)
        avg = total_sum / count if count > 0 else 0.0
        lines.append(f"triad_job_duration_seconds_count {count}")
        lines.append(f"triad_job_duration_seconds_sum {total_sum:.4f}")
        lines.append(f'triad_job_duration_seconds{{quantile="0.5"}} {avg:.4f}')

        lines.append("")
        return "\n".join(lines)


# Global singleton metrics registry
metrics_registry = PrometheusMetricsRegistry()
