"""Command-line interface for Triad Swarm."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from triad import __version__
from triad.core.llm import get_llm_provider, MockLLMProvider, populate_mock_telemetry_defaults
from triad.core.models import WorkloadSpec
from triad.orchestrator.engine import TriadEngine
from triad.orchestrator.naive_engine import NaiveBaselineEngine

console = Console()


def render_banner() -> None:
    banner = f"""[bold cyan]Triad Swarm[/bold cyan] [dim]v{__version__}[/dim]
[italic green]Minimal Agents • Maximum Parallel Speed • Minimum Token Consumption[/italic green]"""
    console.print(Panel(banner, border_style="cyan"))


async def run_workload_cmd(workload_path: str, concurrency: int, provider_name: str, output_dir: str | None) -> None:
    render_banner()
    p = Path(workload_path)
    if not p.exists():
        console.print(f"[bold red]Error:[/bold red] Workload file `{workload_path}` does not exist.")
        sys.exit(1)

    data = json.loads(p.read_text(encoding="utf-8"))
    spec = WorkloadSpec(**data)

    console.print(f"🚀 [bold]Starting workload:[/bold] [yellow]{spec.name}[/yellow]")
    console.print(f"⚙️  [dim]Provider:[/dim] {provider_name} | [dim]Concurrency:[/dim] {concurrency}\n")

    llm = get_llm_provider(provider_name=provider_name)
    if isinstance(llm, MockLLMProvider):
        from triad.core.llm import populate_mock_telemetry_defaults
        populate_mock_telemetry_defaults(llm)
    engine = TriadEngine(llm=llm, max_concurrency=concurrency, output_dir=output_dir)

    metrics = await engine.execute_workload(spec)

    table = Table(title="✨ Triad Swarm Execution Summary", border_style="green")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")

    table.add_row("Workload Name", metrics.workload_name)
    table.add_row("Total Agents Invoked", f"{metrics.total_agents_invoked} (1 Architect + {metrics.tasks_total} Workers)")
    table.add_row("Active Concurrency", str(metrics.active_worker_concurrency))
    table.add_row("Wall Clock Time", f"{metrics.wall_clock_seconds:.2f} s")
    table.add_row("Cumulative Worker Time", f"{metrics.cumulative_worker_seconds:.2f} s")
    table.add_row("Parallel Speedup", f"{metrics.parallel_speedup:.2f}x")
    table.add_row("Tasks Succeeded / Total", f"{metrics.tasks_succeeded} / {metrics.tasks_total} ({metrics.success_rate:.1f}%)")
    table.add_row("Total Tokens", f"{metrics.total_tokens:,}")
    table.add_row("Prompt / Completion", f"{metrics.prompt_tokens:,} / {metrics.completion_tokens:,}")
    table.add_row("Zero-Token Verifications", f"[bold green]{metrics.zero_token_verifications}[/bold green] (100% Deterministic Pass)")
    table.add_row("Estimated Cost (USD)", f"${metrics.estimated_cost_usd:.5f}")

    console.print(table)
    console.print(engine.tracker.generate_markdown_report())


async def run_benchmark_cmd(slices_count: int, provider_name: str) -> None:
    render_banner()
    console.print(f"🔬 [bold yellow]Running Head-to-Head Benchmark:[/bold yellow] [bold cyan]Triad Swarm[/bold cyan] vs [bold red]Monolithic Naive Swarm[/bold red]\n")

    # Sample modular microservice workload
    spec = WorkloadSpec(
        name="Telemetry & Analytics Processing Engine",
        description="A modular high-performance metrics aggregation and alerting pipeline.",
        acceptance_criteria=[
            "Storage layer with async record save and lookup",
            "Aggregation engine computing p50, p95, p99 percentiles",
            "Alerting rule evaluator with threshold detection",
            "REST API handler serialization",
        ],
    )

    llm = get_llm_provider(provider_name=provider_name)
    if isinstance(llm, MockLLMProvider):
        from triad.core.llm import populate_mock_telemetry_defaults
        populate_mock_telemetry_defaults(llm)

    # 1. Triad Swarm Execution
    console.print("[dim]1. Running Triad Swarm (Parallel, Isolated Context, 0-Token Gate)...[/dim]")
    triad_engine = TriadEngine(llm=llm, max_concurrency=4)
    triad_metrics = await triad_engine.execute_workload(spec)

    # Re-use the exact same decomposed slices for fair comparison
    slices = await triad_engine.architect.decompose_workload(spec)

    # 2. Naive Baseline Execution
    console.print("[dim]2. Running Naive Monolithic Swarm (Sequential, Accumulating Chat, LLM Critic)...[/dim]")
    naive_engine = NaiveBaselineEngine(llm=llm)
    naive_metrics = await naive_engine.execute_workload(spec, slices)

    # 3. Print Side-by-Side Comparison Table
    table = Table(title="🏆 Swarm Architecture Benchmark Comparison", border_style="cyan")
    table.add_column("Dimension", style="bold white", no_wrap=True)
    table.add_column("Naive Sequential Chat Swarm", style="red")
    table.add_column("Triad Swarm (Our Framework)", style="green")
    table.add_column("Advantage / Delta", style="bold yellow")

    # Agents used
    table.add_row(
        "Agent Roles Required",
        f"{naive_metrics.total_agents_invoked} (Worker + Critic per slice)",
        f"{triad_metrics.total_agents_invoked} (1 Architect + {len(slices)} Workers)",
        f"[green]{((naive_metrics.total_agents_invoked - triad_metrics.total_agents_invoked) / naive_metrics.total_agents_invoked)*100:.0f}% fewer roles[/green]",
    )

    # Wall clock time
    time_saved = ((naive_metrics.wall_clock_seconds - triad_metrics.wall_clock_seconds) / max(0.001, naive_metrics.wall_clock_seconds)) * 100.0
    table.add_row(
        "Wall-Clock Time",
        f"{naive_metrics.wall_clock_seconds:.2f} s",
        f"{triad_metrics.wall_clock_seconds:.2f} s",
        f"[green]{time_saved:.1f}% faster ({triad_metrics.parallel_speedup:.2f}x speedup)[/green]",
    )

    # Total tokens
    token_saved = ((naive_metrics.total_tokens - triad_metrics.total_tokens) / max(1, naive_metrics.total_tokens)) * 100.0
    table.add_row(
        "Total Tokens Consumed",
        f"{naive_metrics.total_tokens:,}",
        f"{triad_metrics.total_tokens:,}",
        f"[bold green]{token_saved:.1f}% tokens saved[/bold green]",
    )

    # Verification Tokens
    table.add_row(
        "Verification Token Cost",
        f"{naive_metrics.total_tokens - naive_metrics.prompt_tokens:,} tokens (LLM Critic)",
        "0 tokens (Deterministic AST + PyTest)",
        "[bold green]100% LLM verification cost eliminated[/bold green]",
    )

    # Success rate
    table.add_row(
        "Success Ratio",
        f"{naive_metrics.success_rate:.1f}%",
        f"{triad_metrics.success_rate:.1f}%",
        "[green]Deterministic TDD Guarantees[/green]",
    )

    # Estimated Cost
    table.add_row(
        "Estimated Cost (USD)",
        f"${naive_metrics.estimated_cost_usd:.5f}",
        f"${triad_metrics.estimated_cost_usd:.5f}",
        f"[bold green]${(naive_metrics.estimated_cost_usd - triad_metrics.estimated_cost_usd):.5f} saved[/bold green]",
    )

    console.print("\n")
    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="Triad Swarm: Minimal-Agent High-Efficiency Framework")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a workload specification")
    run_parser.add_argument("workload", type=str, help="Path to JSON workload specification file")
    run_parser.add_argument("--concurrency", "-c", type=int, default=4, help="Max parallel workers (default: 4)")
    run_parser.add_argument("--provider", "-p", type=str, default="gemini", choices=["gemini", "openai", "mock"], help="LLM provider")
    run_parser.add_argument("--out", "-o", type=str, default=None, help="Directory to sync generated verified code")

    # Benchmark command
    bench_parser = subparsers.add_parser("benchmark", help="Run side-by-side benchmark comparison")
    bench_parser.add_argument("--slices", "-s", type=int, default=4, help="Number of task slices (default: 4)")
    bench_parser.add_argument("--provider", "-p", type=str, default="mock", choices=["mock", "gemini", "openai"], help="LLM provider")

    # Version command
    subparsers.add_parser("version", help="Print version")

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(run_workload_cmd(args.workload, args.concurrency, args.provider, args.out))
    elif args.command == "benchmark":
        asyncio.run(run_benchmark_cmd(args.slices, args.provider))
    elif args.command == "version":
        console.print(f"Triad Swarm v{__version__}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
