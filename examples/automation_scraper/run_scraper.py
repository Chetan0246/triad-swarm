#!/usr/bin/env python3
"""Run the Everyday Web Scraper & Report Generator Swarm Example."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from triad.core.llm import MockLLMProvider
from triad.core.models import TaskSlice, WorkloadSpec
from triad.core.router import ModelRouter
from triad.orchestrator.engine import TriadEngine

console = Console()


def setup_mock_scraper(mock: MockLLMProvider) -> None:
    """Pre-register complete scraper implementations for offline execution."""
    fetcher_code = json.dumps({
        "files": {
            "scraper/fetcher.py": (
                "def fetch_content(url: str, retries: int = 2) -> dict:\n"
                "    # Simulates clean HTTP response\n"
                "    sample_html = (\n"
                "        '<div class=\"card\"><h2><a href=\"/post1\">Headline 1</a></h2><p>Summary 1</p></div>\\n'\n"
                "        '<div class=\"card\"><h2><a href=\"/post2\">Headline 2</a></h2><p>Summary 2</p></div>'\n"
                "    )\n"
                "    return {'status_code': 200, 'url': url, 'content': sample_html}\n"
            )
        },
        "summary": "HTTP fetcher with simulated response"
    })

    parser_code = json.dumps({
        "files": {
            "scraper/parser.py": (
                "import re\n"
                "from typing import List, Dict, Any\n\n"
                "def parse_items(html_str: str) -> List[Dict[str, Any]]:\n"
                "    items = []\n"
                "    matches = re.findall(r'<a href=\"([^\"]+)\">([^<]+)</a>(?:</h2><p>([^<]+))?', html_str)\n"
                "    for href, title, summary in matches:\n"
                "        items.append({'title': title.strip(), 'link': href.strip(), 'summary': summary.strip() if summary else ''})\n"
                "    return items\n"
            )
        },
        "summary": "Regex-based HTML data extractor"
    })

    reporter_code = json.dumps({
        "files": {
            "scraper/reporter.py": (
                "from typing import List, Dict, Any\n\n"
                "def generate_report(items: List[Dict[str, Any]]) -> Dict[str, str]:\n"
                "    md_lines = ['| Title | Link | Summary |', '|---|---|---|']\n"
                "    html_rows = []\n"
                "    for it in items:\n"
                "        md_lines.append(f\"| {it.get('title')} | {it.get('link')} | {it.get('summary')} |\")\n"
                "        html_rows.append(f\"<tr><td>{it.get('title')}</td><td><a href='{it.get('link')}'>Link</a></td><td>{it.get('summary')}</td></tr>\")\n"
                "    html_doc = f\"<html><body><h2>Scraped Digest</h2><table>{''.join(html_rows)}</table></body></html>\"\n"
                "    return {'markdown': '\\n'.join(md_lines), 'html': html_doc}\n"
            )
        },
        "summary": "Multi-format report generator (HTML + Markdown)"
    })

    mock.register_response("fetch_content", fetcher_code)
    mock.register_response("parse_items", parser_code)
    mock.register_response("generate_report", reporter_code)


async def main() -> None:
    console.print(Panel(
        "[bold cyan]Triad Swarm: Everyday Web Scraper & Report Pipeline[/bold cyan]\n"
        "[dim]Decomposing & Synthesizing: HTTP Fetcher -> HTML Parser -> HTML/Markdown Report Generator[/dim]",
        border_style="cyan"
    ))

    workload_path = Path(__file__).parent / "workload_scraper.json"
    data = json.loads(workload_path.read_text())
    spec = WorkloadSpec(**{k: v for k, v in data.items() if k != "slices"})
    slices = [TaskSlice(**s) for s in data.get("slices", [])]

    mock = MockLLMProvider()
    setup_mock_scraper(mock)
    router = ModelRouter(architect_provider=mock, worker_provider=mock)

    output_dir = Path(__file__).parent / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)

    engine = TriadEngine(
        router=router,
        max_concurrency=3,
        output_dir=str(output_dir),
    )

    console.print(f"🚀 Executing {len(slices)} pipeline slices...")
    metrics = await engine.execute_workload(spec, slices)

    console.print("\n[bold green]✅ Automation Pipeline Generated & Deterministically Verified![/bold green]")
    console.print(f"⏱️  Duration: [bold cyan]{metrics.wall_clock_seconds:.2f}s[/bold cyan]")
    console.print(f"🎯 Total Tokens: [bold cyan]{metrics.total_tokens}[/bold cyan]")
    console.print(f"🛡️  Zero-Token Verification Events: [bold green]{metrics.zero_token_verifications}[/bold green]")
    console.print(f"📁 Output Artifacts Generated in: [bold yellow]{output_dir}[/bold yellow]\n")


if __name__ == "__main__":
    asyncio.run(main())
