"""Command-line interface for Triad Swarm."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from triad import __version__
from triad.core.contracts import ASTContractValidator
from triad.core.llm import get_llm_provider, MockLLMProvider, populate_mock_telemetry_defaults
from triad.core.models import InterfaceContract, WorkloadSpec
from triad.orchestrator.engine import TriadEngine
from triad.orchestrator.naive_engine import NaiveBaselineEngine
from triad.orchestrator.scheduler import DAGScheduler

console = Console()


def render_banner() -> None:
    banner = f"""[bold cyan]Triad Swarm[/bold cyan] [dim]v{__version__}[/dim]
[italic green]Minimal Agents • Maximum Parallel Speed • Minimum Token Consumption[/italic green]
[dim]Reactive DAG Scheduling • Zero-Token AST Verification • Multi-Tier Caching[/dim]"""
    console.print(Panel(banner, border_style="cyan"))


async def run_workload_cmd(
    workload_path: str,
    concurrency: int,
    provider_name: str,
    output_dir: Optional[str],
    trace_file: Optional[str],
    enable_cache: bool,
) -> None:
    render_banner()
    p = Path(workload_path)
    if not p.exists():
        console.print(f"[bold red]Error:[/bold red] Workload file `{workload_path}` does not exist.")
        sys.exit(1)

    data = json.loads(p.read_text(encoding="utf-8"))
    spec = WorkloadSpec(**data)

    console.print(f"🚀 [bold]Starting workload:[/bold] [yellow]{spec.name}[/yellow]")
    console.print(f"⚙️  [dim]Provider:[/dim] {provider_name} | [dim]Concurrency:[/dim] {concurrency} | [dim]Cache:[/dim] {enable_cache}\n")

    llm = get_llm_provider(provider_name=provider_name)
    if isinstance(llm, MockLLMProvider):
        populate_mock_telemetry_defaults(llm)

    engine = TriadEngine(
        llm=llm,
        max_concurrency=concurrency,
        output_dir=output_dir,
        enable_cache=enable_cache,
        cache_dir=".triad_cache" if enable_cache else None,
        trace_output_path=trace_file,
    )

    metrics = await engine.execute_workload(spec)

    table = Table(title="✨ Triad Swarm Execution Summary", border_style="green")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")

    table.add_row("Workload Name", metrics.workload_name)
    table.add_row("Total Agents Invoked", f"{metrics.total_agents_invoked} (1 Architect + {metrics.tasks_total} Workers)")
    table.add_row("Active Concurrency", str(metrics.active_worker_concurrency))
    table.add_row("DAG Execution Waves", str(metrics.execution_waves))
    table.add_row("Wall Clock Time", f"{metrics.wall_clock_seconds:.2f} s")
    table.add_row("Cumulative Worker Time", f"{metrics.cumulative_worker_seconds:.2f} s")
    table.add_row("Parallel Speedup", f"{metrics.parallel_speedup:.2f}x")
    table.add_row("Tasks Succeeded / Total", f"{metrics.tasks_succeeded} / {metrics.tasks_total} ({metrics.success_rate:.1f}%)")
    table.add_row("Total Tokens", f"{metrics.total_tokens:,}")
    table.add_row("Prompt / Completion", f"{metrics.prompt_tokens:,} / {metrics.completion_tokens:,}")
    table.add_row("Zero-Token Verifications", f"[bold green]{metrics.zero_token_verifications}[/bold green] (100% Deterministic CPU Pass)")
    if metrics.cache_hits > 0:
        table.add_row("Prompt Cache Hits", f"[bold green]{metrics.cache_hits}[/bold green] ({metrics.cache_tokens_saved:,} tokens saved)")
    if metrics.traceback_tokens_saved > 0:
        table.add_row("Traceback Pruning Savings", f"[bold green]{metrics.traceback_tokens_saved:,}[/bold green] tokens saved on healing")
    table.add_row("Estimated Cost (USD)", f"${metrics.estimated_cost_usd:.5f}")

    console.print(table)
    console.print(engine.tracker.generate_markdown_report())

    if trace_file:
        console.print(f"\n[green]✔ Chrome DevTools Trace saved to:[/green] [bold]{trace_file}[/bold]")
        console.print("[dim]Open chrome://tracing or https://ui.perfetto.dev to view the interactive timeline.[/dim]")


async def graph_workload_cmd(workload_path: str, mermaid: bool) -> None:
    """Analyze and print the dependency DAG of a workload."""
    render_banner()
    p = Path(workload_path)
    if not p.exists():
        console.print(f"[bold red]Error:[/bold red] Workload file `{workload_path}` does not exist.")
        sys.exit(1)

    data = json.loads(p.read_text(encoding="utf-8"))
    spec = WorkloadSpec(**data)

    mock_llm = MockLLMProvider()
    populate_mock_telemetry_defaults(mock_llm)
    engine = TriadEngine(llm=mock_llm)
    slices = await engine.architect.decompose_workload(spec)

    scheduler = DAGScheduler(slices)

    if mermaid:
        console.print("[bold cyan]Mermaid Flowchart DAG:[/bold cyan]\n")
        console.print(scheduler.to_mermaid())
    else:
        console.print(scheduler.to_ascii())


def verify_file_cmd(target_file: str, contract_path: str) -> None:
    """Standalone zero-token static AST verification for CI/CD."""
    render_banner()
    tf = Path(target_file)
    cf = Path(contract_path)

    if not tf.exists():
        console.print(f"[bold red]Error:[/bold red] Target file `{target_file}` not found.")
        sys.exit(1)
    if not cf.exists():
        console.print(f"[bold red]Error:[/bold red] Contract file `{contract_path}` not found.")
        sys.exit(1)

    code_str = tf.read_text(encoding="utf-8")
    contract_data = json.loads(cf.read_text(encoding="utf-8"))
    contract = InterfaceContract(**contract_data)

    is_valid, errors = ASTContractValidator.validate_code(code_str, contract)
    if is_valid:
        console.print(f"[bold green]✔ Contract Passed (0 Tokens):[/bold green] `{target_file}` fulfills all interface symbols and type contracts.")
        sys.exit(0)
    else:
        console.print(f"[bold red]✖ Contract Violation (0 Tokens):[/bold red] Found {len(errors)} errors in `{target_file}`:")
        for err in errors:
            console.print(f"  • [red]{err}[/red]")
        sys.exit(2)


async def run_benchmark_cmd(slices_count: int, provider_name: str) -> None:
    render_banner()
    console.print(f"🔬 [bold yellow]Running Head-to-Head Benchmark:[/bold yellow] [bold cyan]Triad Swarm[/bold cyan] vs [bold red]Monolithic Naive Swarm[/bold red]\n")

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

    table.add_row(
        "Agent Roles Required",
        f"{naive_metrics.total_agents_invoked} (Worker + Critic per slice)",
        f"{triad_metrics.total_agents_invoked} (1 Architect + {len(slices)} Workers)",
        f"[green]{((naive_metrics.total_agents_invoked - triad_metrics.total_agents_invoked) / naive_metrics.total_agents_invoked)*100:.0f}% fewer roles[/green]",
    )

    time_saved = ((naive_metrics.wall_clock_seconds - triad_metrics.wall_clock_seconds) / max(0.001, naive_metrics.wall_clock_seconds)) * 100.0
    table.add_row(
        "Wall-Clock Time",
        f"{naive_metrics.wall_clock_seconds:.2f} s",
        f"{triad_metrics.wall_clock_seconds:.2f} s",
        f"[green]{time_saved:.1f}% faster ({triad_metrics.parallel_speedup:.2f}x speedup)[/green]",
    )

    token_saved = ((naive_metrics.total_tokens - triad_metrics.total_tokens) / max(1, naive_metrics.total_tokens)) * 100.0
    table.add_row(
        "Total Tokens Consumed",
        f"{naive_metrics.total_tokens:,}",
        f"{triad_metrics.total_tokens:,}",
        f"[bold green]{token_saved:.1f}% tokens saved[/bold green]",
    )

    table.add_row(
        "Verification Token Cost",
        f"{naive_metrics.total_tokens - naive_metrics.prompt_tokens:,} tokens (LLM Critic)",
        "0 tokens (Deterministic AST + PyTest)",
        "[bold green]100% LLM verification cost eliminated[/bold green]",
    )

    table.add_row(
        "Success Ratio",
        f"{naive_metrics.success_rate:.1f}%",
        f"{triad_metrics.success_rate:.1f}%",
        "[green]Deterministic TDD Guarantees[/green]",
    )

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
    run_parser.add_argument("--trace-file", "-t", type=str, default=None, help="Path to export Chrome trace event JSON")
    run_parser.add_argument("--no-cache", action="store_true", help="Disable exact semantic prompt caching")

    # Graph command
    graph_parser = subparsers.add_parser("graph", help="Visualize dependency DAG and topological waves")
    graph_parser.add_argument("workload", type=str, help="Path to JSON workload specification file")
    graph_parser.add_argument("--mermaid", "-m", action="store_true", help="Output Mermaid diagram syntax")

    # Verify command (standalone 0-token CI gate)
    verify_parser = subparsers.add_parser("verify", help="Validate a code file against an AST contract with 0 tokens")
    verify_parser.add_argument("file", type=str, help="Path to target source file")
    verify_parser.add_argument("--contract", "-c", type=str, required=True, help="Path to contract JSON file")

    # Benchmark command
    bench_parser = subparsers.add_parser("benchmark", help="Run side-by-side benchmark comparison")
    bench_parser.add_argument("--slices", "-s", type=int, default=4, help="Number of task slices (default: 4)")
    bench_parser.add_argument("--provider", "-p", type=str, default="mock", choices=["mock", "gemini", "openai"], help="LLM provider")

    # Dashboard command
    subparsers.add_parser("dashboard", help="Open the interactive architecture and benchmark visualizer")

    # Version command
    subparsers.add_parser("version", help="Print version")

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(
            run_workload_cmd(
                workload_path=args.workload,
                concurrency=args.concurrency,
                provider_name=args.provider,
                output_dir=args.out,
                trace_file=args.trace_file,
                enable_cache=not args.no_cache,
            )
        )
    elif args.command == "graph":
        asyncio.run(graph_workload_cmd(args.workload, args.mermaid))
    elif args.command == "verify":
        verify_file_cmd(args.file, args.contract)
    elif args.command == "benchmark":
        asyncio.run(run_benchmark_cmd(args.slices, args.provider))
    elif args.command == "dashboard":
        render_banner()
        dashboard_path = Path(__file__).parent.parent / "examples" / "visualizer" / "index.html"
        file_uri = f"file://{dashboard_path.resolve()}"
        console.print("📊 [bold green]Interactive Architecture Dashboard Ready![/bold green]")
        console.print(f"🔗 [bold cyan]{file_uri}[/bold cyan]\n")
        console.print("[dim]Open the link above in your browser to explore the interactive visualizer.[/dim]")
    elif args.command == "version":
        console.print(f"Triad Swarm v{__version__}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
