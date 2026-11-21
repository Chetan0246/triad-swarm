"""Runnable demonstration of the Triad Swarm executing a modular microservice workload."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from triad.core.llm import MockLLMProvider, get_llm_provider
from triad.core.models import WorkloadSpec
from triad.orchestrator.engine import TriadEngine

console = Console()


def setup_mock_data(mock: MockLLMProvider) -> None:
    """Register high-fidelity mock implementations for reproducible offline demo."""
    # Architect response
    architect_json = json.dumps({
        "slices": [
            {
                "slice_id": "slice_storage",
                "title": "Time-Series Ring Buffer Storage",
                "description": "Implement InMemoryRingBuffer with append and query_range",
                "target_files": ["telemetry/storage.py"],
                "contract": {
                    "module_path": "telemetry/storage.py",
                    "exported_symbols": ["InMemoryRingBuffer"],
                    "signatures": {
                        "append": "def append(self, timestamp: float, value: float) -> None",
                        "query_range": "def query_range(self, start_ts: float, end_ts: float) -> list"
                    },
                    "invariants": ["Points must remain ordered by timestamp"]
                },
                "acceptance_tests": {
                    "tests/test_storage.py": (
                        "from telemetry.storage import InMemoryRingBuffer\n"
                        "def test_buffer():\n"
                        "    buf = InMemoryRingBuffer(capacity=10)\n"
                        "    buf.append(1.0, 10.0)\n"
                        "    buf.append(2.0, 20.0)\n"
                        "    res = buf.query_range(0.0, 3.0)\n"
                        "    assert len(res) == 2\n"
                    )
                },
                "dependencies": []
            },
            {
                "slice_id": "slice_stats",
                "title": "Windowed Statistics Engine",
                "description": "Implement compute_percentiles and compute_mean",
                "target_files": ["telemetry/statistics.py"],
                "contract": {
                    "module_path": "telemetry/statistics.py",
                    "exported_symbols": ["compute_percentiles", "compute_mean"],
                    "signatures": {
                        "compute_percentiles": "def compute_percentiles(values: list, percentiles: list) -> dict",
                        "compute_mean": "def compute_mean(values: list) -> float"
                    },
                    "invariants": ["Mean of empty list is 0.0"]
                },
                "acceptance_tests": {
                    "tests/test_stats.py": (
                        "from telemetry.statistics import compute_percentiles, compute_mean\n"
                        "def test_stats():\n"
                        "    vals = [10.0, 20.0, 30.0, 40.0, 50.0]\n"
                        "    assert compute_mean(vals) == 30.0\n"
                        "    pcts = compute_percentiles(vals, [50, 90])\n"
                        "    assert 50 in pcts\n"
                    )
                },
                "dependencies": []
            },
            {
                "slice_id": "slice_alerts",
                "title": "Threshold Alert Evaluator",
                "description": "Implement AlertRule and evaluate_alerts",
                "target_files": ["telemetry/alerts.py"],
                "contract": {
                    "module_path": "telemetry/alerts.py",
                    "exported_symbols": ["AlertRule", "evaluate_alerts"],
                    "signatures": {
                        "evaluate_alerts": "def evaluate_alerts(rules: list, current_value: float) -> list"
                    },
                    "invariants": ["Returns triggered rule names"]
                },
                "acceptance_tests": {
                    "tests/test_alerts.py": (
                        "from telemetry.alerts import AlertRule, evaluate_alerts\n"
                        "def test_alerts():\n"
                        "    rule = AlertRule(name='HighLatency', threshold=100.0)\n"
                        "    triggered = evaluate_alerts([rule], 150.0)\n"
                        "    assert 'HighLatency' in triggered\n"
                    )
                },
                "dependencies": []
            },
            {
                "slice_id": "slice_exporter",
                "title": "Dashboard Exporter Payload Formatter",
                "description": "Implement format_dashboard_payload",
                "target_files": ["telemetry/exporter.py"],
                "contract": {
                    "module_path": "telemetry/exporter.py",
                    "exported_symbols": ["format_dashboard_payload"],
                    "signatures": {
                        "format_dashboard_payload": "def format_dashboard_payload(metric_name: str, stats: dict, alerts: list) -> dict"
                    },
                    "invariants": ["Must contain metric, stats, alerts, and timestamp keys"]
                },
                "acceptance_tests": {
                    "tests/test_exporter.py": (
                        "from telemetry.exporter import format_dashboard_payload\n"
                        "def test_exporter():\n"
                        "    p = format_dashboard_payload('cpu_load', {'mean': 45.2}, ['Warning'])\n"
                        "    assert p['metric'] == 'cpu_load'\n"
                        "    assert p['stats']['mean'] == 45.2\n"
                    )
                },
                "dependencies": []
            }
        ]
    })
    mock.register_response("Workload Name", architect_json)

    # Worker implementations
    storage_code = json.dumps({
        "files": {
            "telemetry/storage.py": (
                "class InMemoryRingBuffer:\n"
                "    def __init__(self, capacity: int = 1000):\n"
                "        self.capacity = capacity\n"
                "        self.buffer = []\n\n"
                "    def append(self, timestamp: float, value: float) -> None:\n"
                "        if len(self.buffer) >= self.capacity:\n"
                "            self.buffer.pop(0)\n"
                "        self.buffer.append((timestamp, value))\n\n"
                "    def query_range(self, start_ts: float, end_ts: float) -> list:\n"
                "        return [val for ts, val in self.buffer if start_ts <= ts <= end_ts]\n"
            )
        }
    })
    mock.register_response("slice_storage", storage_code)

    stats_code = json.dumps({
        "files": {
            "telemetry/statistics.py": (
                "def compute_mean(values: list) -> float:\n"
                "    if not values:\n"
                "        return 0.0\n"
                "    return sum(values) / len(values)\n\n"
                "def compute_percentiles(values: list, percentiles: list) -> dict:\n"
                "    if not values:\n"
                "        return {p: 0.0 for p in percentiles}\n"
                "    sorted_v = sorted(values)\n"
                "    res = {}\n"
                "    for p in percentiles:\n"
                "        idx = int((p / 100.0) * len(sorted_v))\n"
                "        idx = min(idx, len(sorted_v) - 1)\n"
                "        res[p] = sorted_v[idx]\n"
                "    return res\n"
            )
        }
    })
    mock.register_response("slice_stats", stats_code)

    alerts_code = json.dumps({
        "files": {
            "telemetry/alerts.py": (
                "class AlertRule:\n"
                "    def __init__(self, name: str, threshold: float):\n"
                "        self.name = name\n"
                "        self.threshold = threshold\n\n"
                "def evaluate_alerts(rules: list, current_value: float) -> list:\n"
                "    triggered = []\n"
                "    for r in rules:\n"
                "        if current_value >= r.threshold:\n"
                "            triggered.append(r.name)\n"
                "    return triggered\n"
            )
        }
    })
    mock.register_response("slice_alerts", alerts_code)

    exporter_code = json.dumps({
        "files": {
            "telemetry/exporter.py": (
                "import time\n\n"
                "def format_dashboard_payload(metric_name: str, stats: dict, alerts: list) -> dict:\n"
                "    return {\n"
                "        'metric': metric_name,\n"
                "        'stats': stats,\n"
                "        'alerts': alerts,\n"
                "        'timestamp': time.time(),\n"
                "    }\n"
            )
        }
    })
    mock.register_response("slice_exporter", exporter_code)


async def main():
    console.print(Panel(
        "[bold cyan]Triad Swarm Demo: High-Throughput Telemetry Pipeline[/bold cyan]\n"
        "[dim]Architecture: 1 Architect -> 4 Parallel Isolated Workers -> 0-Token AST & Pytest Gate[/dim]",
        border_style="cyan"
    ))

    # Read workload
    workload_path = Path(__file__).parent / "demo_workload.json"
    spec = WorkloadSpec(**json.loads(workload_path.read_text(encoding="utf-8")))

    # Select provider: check if real keys are available, else mock
    provider_name = os.environ.get("TRIAD_LLM_PROVIDER", "mock")
    llm = get_llm_provider(provider_name=provider_name)
    if isinstance(llm, MockLLMProvider):
        setup_mock_data(llm)

    out_dir = Path(__file__).parent / "dist" / "generated_telemetry_service"

    console.print(f"🚀 [bold]Dispatching Workload:[/bold] {spec.name}")
    console.print(f"📁 [dim]Target Output Directory:[/dim] {out_dir}")
    console.print(f"🤖 [dim]LLM Provider:[/dim] {type(llm).__name__}\n")

    engine = TriadEngine(
        llm=llm,
        max_concurrency=4,
        max_healing_attempts=2,
        output_dir=str(out_dir),
    )

    metrics = await engine.execute_workload(spec)

    # Print summary
    table = Table(title="🎉 Triad Swarm Execution Results", border_style="green")
    table.add_column("Property", style="bold cyan")
    table.add_column("Result", style="bold green")

    table.add_row("Agents Used", f"{metrics.total_agents_invoked} (1 Architect + {metrics.tasks_total} Workers)")
    table.add_row("Concurrency Level", f"{metrics.active_worker_concurrency} simultaneous workers")
    table.add_row("Wall-Clock Time", f"{metrics.wall_clock_seconds:.3f} s")
    table.add_row("Cumulative Worker Time", f"{metrics.cumulative_worker_seconds:.3f} s")
    table.add_row("Parallel Speedup", f"{metrics.parallel_speedup:.2f}x")
    table.add_row("Task Completion Rate", f"{metrics.tasks_succeeded}/{metrics.tasks_total} ({metrics.success_rate:.1f}%)")
    table.add_row("Total Tokens", f"{metrics.total_tokens:,}")
    table.add_row("Deterministic 0-Token Passes", f"{metrics.zero_token_verifications} passes (0 tokens wasted on LLM code reviews)")
    table.add_row("Estimated API Cost", f"${metrics.estimated_cost_usd:.5f}")

    console.print(table)
    console.print("\n" + engine.tracker.generate_markdown_report())

    console.print(f"\n✅ All generated files verified and synced to: [underline]{out_dir}[/underline]")


if __name__ == "__main__":
    asyncio.run(main())
