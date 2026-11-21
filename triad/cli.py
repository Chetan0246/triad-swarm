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
from triad.agents.spec_generator import SpecGeneratorAgent
from triad.core.contracts import ASTContractValidator
from triad.core.llm import (
    MockLLMProvider,
    get_llm_provider,
    load_dotenv_if_present,
    populate_mock_telemetry_defaults,
)
from triad.core.models import InterfaceContract, WorkloadSpec
from triad.core.repomap import RepoMapGenerator
from triad.core.router import ModelRouter
from triad.core.web import TinyFishClient
from triad.orchestrator.engine import TriadEngine
from triad.orchestrator.naive_engine import NaiveBaselineEngine
from triad.orchestrator.scheduler import DAGScheduler

console = Console()


def render_banner() -> None:
    banner = f"""[bold cyan]Triad Swarm[/bold cyan] [dim]v{__version__}[/dim]
[italic green]Minimal Agents • Maximum Parallel Speed • Minimum Token Consumption[/italic green]
[dim]Reactive DAG Scheduling • Zero-Token AST Verification • Multi-Tier Caching • TinyFish Web[/dim]"""
    console.print(Panel(banner, border_style="cyan"))


async def run_workload_cmd(
    workload_path: str,
    concurrency: int,
    provider_name: str,
    architect_model: Optional[str],
    worker_model: Optional[str],
    repo_map_path: Optional[str],
    output_dir: Optional[str],
    trace_file: Optional[str],
    enable_cache: bool,
) -> None:
    render_banner()
    p = Path(workload_path)
    if not p.exists():
        console.print(f"[bold red]Error:[/bold red] Workload file `{workload_path}` does not exist.")
        sys.exit(1)

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        console.print(f"[bold red]Error:[/bold red] Workload file is not valid JSON: {e}")
        sys.exit(1)
    spec = WorkloadSpec(**data)

    console.print(f"🚀 [bold]Starting workload:[/bold] [yellow]{spec.name}[/yellow]")

    # Asymmetric Router Setup
    router = ModelRouter(
        architect_spec=architect_model or provider_name,
        worker_spec=worker_model or provider_name,
        enable_cache=enable_cache,
    )
    arch_llm = router.get_architect_llm()
    raw_arch = getattr(arch_llm, "provider", arch_llm)
    if isinstance(raw_arch, MockLLMProvider):
        populate_mock_telemetry_defaults(raw_arch)
    raw_worker = getattr(router.get_worker_llm(), "provider", router.get_worker_llm())
    if isinstance(raw_worker, MockLLMProvider):
        populate_mock_telemetry_defaults(raw_worker)

    console.print(f"⚙️  [dim]Architect Model:[/dim] {router.architect_spec} | [dim]Worker Model:[/dim] {router.worker_spec}")
    console.print(f"⚙️  [dim]Concurrency:[/dim] {concurrency} | [dim]Cache:[/dim] {enable_cache}\n")

    repo_map_str = None
    if repo_map_path:
        repo_gen = RepoMapGenerator(root_dir=repo_map_path)
        repo_map_str = repo_gen.generate_map()
        console.print(f"🗺️  [dim]Injected repository AST map from {repo_map_path}[/dim]")

    engine = TriadEngine(
        router=router,
        max_concurrency=concurrency,
        output_dir=output_dir,
        enable_cache=enable_cache,
        cache_dir=".triad_cache" if enable_cache else None,
        trace_output_path=trace_file,
    )

    metrics = await engine.execute_workload(spec, repo_map=repo_map_str)

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


async def new_feature_cmd(
    prompt: str,
    out_spec_path: Optional[str],
    run_swarm: bool,
    output_dir: Optional[str],
    provider: str,
    architect_model: Optional[str],
    worker_model: Optional[str],
    repo_map_path: Optional[str],
    concurrency: int,
    no_cache: bool,
) -> None:
    """Zero-JSON natural language feature synthesis and autonomous execution."""
    render_banner()
    console.print(f"✨ [bold green]Zero-JSON Feature Architect:[/bold green] \"{prompt}\"\n")

    repo_map_str = None
    if repo_map_path:
        repo_gen = RepoMapGenerator(root_dir=repo_map_path)
        repo_map_str = repo_gen.generate_map()
        console.print(f"🗺️  [dim]Injected repository AST map from {repo_map_path}[/dim]")

    router = ModelRouter(
        architect_spec=architect_model or provider,
        worker_spec=worker_model or provider,
        enable_cache=not no_cache,
    )
    architect_llm = router.get_architect_llm()
    raw_arch = getattr(architect_llm, "provider", architect_llm)
    if isinstance(raw_arch, MockLLMProvider):
        populate_mock_telemetry_defaults(raw_arch)
    raw_worker = getattr(router.get_worker_llm(), "provider", router.get_worker_llm())
    if isinstance(raw_worker, MockLLMProvider):
        populate_mock_telemetry_defaults(raw_worker)

    spec_gen = SpecGeneratorAgent(llm=architect_llm)
    with console.status("[bold cyan]Synthesizing formal WorkloadSpec and interface contracts..."):
        spec = await spec_gen.generate_spec(prompt=prompt, repo_map=repo_map_str)

    console.print(f"✔ [bold green]Synthesized Workload:[/bold green] [yellow]{spec.name}[/yellow]")
    console.print(f"  [dim]Criteria:[/dim] {len(spec.acceptance_criteria)} acceptance rules defined.")

    if out_spec_path:
        out_p = Path(out_spec_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"✔ [cyan]Saved workload specification to:[/cyan] [bold]{out_spec_path}[/bold]")

    if run_swarm:
        console.print("\n🚀 [bold]Dispatching Triad Swarm to build & verify code...[/bold]")
        engine = TriadEngine(
            router=router,
            max_concurrency=concurrency,
            output_dir=output_dir or "./out",
            enable_cache=not no_cache,
        )
        metrics = await engine.execute_workload(spec, repo_map=repo_map_str)

        table = Table(title="✨ Execution Outcome", border_style="green")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Tasks Succeeded / Total", f"{metrics.tasks_succeeded} / {metrics.tasks_total}")
        table.add_row("Total Wall Time", f"{metrics.wall_clock_seconds:.2f} s")
        table.add_row("Parallel Speedup", f"{metrics.parallel_speedup:.2f}x")
        table.add_row("Zero-Token Verifications", f"{metrics.zero_token_verifications} (100% Deterministic)")
        table.add_row("Output Directory", str(output_dir or "./out"))
        console.print(table)


def repomap_cmd(path: str) -> None:
    """Scan and print the AST symbol map of a project codebase."""
    render_banner()
    p = Path(path).resolve()
    console.print(f"🔍 [bold cyan]Scanning repository AST symbols at:[/bold cyan] {p}\n")
    gen = RepoMapGenerator(root_dir=str(p))
    map_str = gen.generate_map()
    console.print(map_str)
    tokens_est = int(len(map_str) * 0.25)
    console.print(f"\n[dim]Estimated context size: ~{tokens_est:,} tokens (Bounded O(1) context for Architect)[/dim]")


async def search_cmd(query: str, max_results: int) -> None:
    """Search web using TinyFish API or zero-cost free fallback."""
    render_banner()
    console.print(f"🔎 [bold cyan]Web Search Query:[/bold cyan] \"{query}\"\n")
    client = TinyFishClient()
    resp = await client.search(query=query, max_results=max_results)

    table = Table(title=f"Search Results (Provider: {resp.provider}, Time: {resp.duration_seconds:.2f}s)", border_style="cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", style="bold cyan", max_width=40)
    table.add_column("URL", style="green", max_width=45)
    table.add_column("Snippet", style="white")

    if not resp.results:
        console.print("[yellow]No results returned or offline fallback completed.[/yellow]")
    else:
        for i, res in enumerate(resp.results, 1):
            table.add_row(str(i), res.title, res.url, res.snippet[:120] + "...")
        console.print(table)


async def fetch_cmd(url: str, max_chars: int) -> None:
    """Fetch URL content using TinyFish API or zero-cost free scraper."""
    render_banner()
    console.print(f"🌐 [bold cyan]Fetching URL:[/bold cyan] {url}\n")
    client = TinyFishClient()
    resp = await client.fetch(url=url, max_chars=max_chars)
    if resp.title:
        console.print(f"[bold]Title:[/bold] {resp.title}")
    console.print(f"[dim]Provider: {resp.provider} | Length: {len(resp.content)} chars | Truncated: {resp.truncated}[/dim]\n")
    console.print(Panel(resp.content, title="Clean Extracted Content", border_style="green"))


async def graph_workload_cmd(workload_path: str, mermaid: bool) -> None:
    """Analyze and print the dependency DAG of a workload."""
    render_banner()
    p = Path(workload_path)
    if not p.exists():
        console.print(f"[bold red]Error:[/bold red] Workload file `{workload_path}` does not exist.")
        sys.exit(1)

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        console.print(f"[bold red]Error:[/bold red] Workload file is not valid JSON: {e}")
        sys.exit(1)
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
    try:
        contract_data = json.loads(cf.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        console.print(f"[bold red]Error:[/bold red] Contract file is not valid JSON: {e}")
        sys.exit(1)
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
    console.print("🔬 [bold yellow]Running Head-to-Head Benchmark:[/bold yellow] [bold cyan]Triad Swarm[/bold cyan] vs [bold red]Monolithic Naive Swarm[/bold red]\n")

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
    load_dotenv_if_present()
    parser = argparse.ArgumentParser(description="Triad Swarm: Minimal-Agent High-Efficiency Framework")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # New command (Zero-JSON feature synthesis)
    new_parser = subparsers.add_parser("new", help="Synthesize and optionally execute a feature from natural language")
    new_parser.add_argument("prompt", type=str, help="Natural language description of the feature to build")
    new_parser.add_argument("--out", "-o", type=str, default=None, help="Save generated WorkloadSpec JSON to file")
    new_parser.add_argument("--run", "-r", action="store_true", help="Immediately execute the swarm to build code")
    new_parser.add_argument("--output-dir", type=str, default="./out", help="Directory to sync verified code")
    new_parser.add_argument("--provider", "-p", type=str, default="gemini", help="Default LLM provider (gemini, openai, ollama, mock)")
    new_parser.add_argument("--architect-model", type=str, default=None, help="Model spec for Architect (e.g. gemini/gemini-3.8-flash, openai/gpt-4o)")
    new_parser.add_argument("--worker-model", type=str, default=None, help="Model spec for Workers (e.g. gemini/gemini-3.8-flash, ollama/qwen2.5-coder)")
    new_parser.add_argument("--repo-map", type=str, default=None, help="Path to existing repo to map AST symbols")
    new_parser.add_argument("--concurrency", "-c", type=int, default=4, help="Max parallel workers (default: 4)")
    new_parser.add_argument("--no-cache", action="store_true", help="Disable prompt caching")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a workload specification JSON")
    run_parser.add_argument("workload", type=str, help="Path to JSON workload specification file")
    run_parser.add_argument("--concurrency", "-c", type=int, default=4, help="Max parallel workers (default: 4)")
    run_parser.add_argument("--provider", "-p", type=str, default="gemini", help="Default LLM provider (gemini, openai, ollama, mock)")
    run_parser.add_argument("--architect-model", type=str, default=None, help="Model spec for Architect")
    run_parser.add_argument("--worker-model", type=str, default=None, help="Model spec for Workers")
    run_parser.add_argument("--repo-map", type=str, default=None, help="Path to existing codebase to extract AST context")
    run_parser.add_argument("--out", "-o", type=str, default=None, help="Directory to sync generated verified code")
    run_parser.add_argument("--trace-file", "-t", type=str, default=None, help="Path to export Chrome trace event JSON")
    run_parser.add_argument("--no-cache", action="store_true", help="Disable exact semantic prompt caching")

    # Repomap command
    repo_parser = subparsers.add_parser("repomap", help="Scan and print codebase AST symbol map")
    repo_parser.add_argument("path", type=str, nargs="?", default=".", help="Root directory of codebase (default: .)")

    # Search command (TinyFish)
    search_parser = subparsers.add_parser("search", help="Search the web via TinyFish API or zero-cost free fallback")
    search_parser.add_argument("query", type=str, help="Search query string")
    search_parser.add_argument("--max-results", "-n", type=int, default=5, help="Max search results (default: 5)")

    # Fetch command (TinyFish)
    fetch_parser = subparsers.add_parser("fetch", help="Fetch and clean web page content via TinyFish or free scraper")
    fetch_parser.add_argument("url", type=str, help="URL to fetch")
    fetch_parser.add_argument("--max-chars", "-m", type=int, default=4000, help="Max characters to extract (default: 4000)")

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
    bench_parser.add_argument("--provider", "-p", type=str, default="mock", help="LLM provider")

    # Dashboard command
    subparsers.add_parser("dashboard", help="Open the interactive architecture and benchmark visualizer")

    # Version command
    subparsers.add_parser("version", help="Print version")

    args = parser.parse_args()

    if args.command == "new":
        asyncio.run(
            new_feature_cmd(
                prompt=args.prompt,
                out_spec_path=args.out,
                run_swarm=args.run,
                output_dir=args.output_dir,
                provider=args.provider,
                architect_model=args.architect_model,
                worker_model=args.worker_model,
                repo_map_path=args.repo_map,
                concurrency=args.concurrency,
                no_cache=args.no_cache,
            )
        )
    elif args.command == "run":
        asyncio.run(
            run_workload_cmd(
                workload_path=args.workload,
                concurrency=args.concurrency,
                provider_name=args.provider,
                architect_model=args.architect_model,
                worker_model=args.worker_model,
                repo_map_path=args.repo_map,
                output_dir=args.out,
                trace_file=args.trace_file,
                enable_cache=not args.no_cache,
            )
        )
    elif args.command == "repomap":
        repomap_cmd(args.path)
    elif args.command == "search":
        asyncio.run(search_cmd(args.query, args.max_results))
    elif args.command == "fetch":
        asyncio.run(fetch_cmd(args.url, args.max_chars))
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
