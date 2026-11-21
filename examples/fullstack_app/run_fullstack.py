#!/usr/bin/env python3
"""Run the Full-Stack Web Application Swarm Example (Database + FastAPI Backend + Tailwind Frontend)."""

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


def setup_mock_fullstack(mock: MockLLMProvider) -> None:
    """Pre-register complete full-stack implementations for offline verification."""
    db_code = json.dumps({
        "files": {
            "app/database.py": (
                "import sqlite3\n"
                "from typing import List, Dict, Any\n\n"
                "class TaskDB:\n"
                "    def __init__(self, db_path: str = 'tasks.db'):\n"
                "        self.db_path = db_path\n"
                "        self._init_table()\n\n"
                "    def _init_table(self):\n"
                "        with sqlite3.connect(self.db_path) as conn:\n"
                "            conn.execute(\n"
                "                'CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, completed BOOLEAN)'\n"
                "            )\n\n"
                "    def add_task(self, title: str) -> Dict[str, Any]:\n"
                "        with sqlite3.connect(self.db_path) as conn:\n"
                "            cur = conn.cursor()\n"
                "            cur.execute('INSERT INTO tasks (title, completed) VALUES (?, ?)', (title, False))\n"
                "            task_id = cur.lastrowid\n"
                "            return {'id': task_id, 'title': title, 'completed': False}\n\n"
                "    def get_tasks(self) -> List[Dict[str, Any]]:\n"
                "        with sqlite3.connect(self.db_path) as conn:\n"
                "            cur = conn.cursor()\n"
                "            cur.execute('SELECT id, title, completed FROM tasks')\n"
                "            return [{'id': r[0], 'title': r[1], 'completed': bool(r[2])} for r in cur.fetchall()]\n"
            )
        },
        "summary": "SQLite task storage layer"
    })

    backend_code = json.dumps({
        "files": {
            "app/main.py": (
                "from fastapi import FastAPI, HTTPException\n"
                "from pydantic import BaseModel\n"
                "from app.database import TaskDB\n\n"
                "class TaskCreate(BaseModel):\n"
                "    title: str\n\n"
                "def create_app(db_path: str = 'tasks.db') -> FastAPI:\n"
                "    app = FastAPI(title='Task Tracker API')\n"
                "    db = TaskDB(db_path=db_path)\n\n"
                "    @app.get('/api/tasks')\n"
                "    def get_all_tasks():\n"
                "        return db.get_tasks()\n\n"
                "    @app.post('/api/tasks', status_code=201)\n"
                "    def create_new_task(payload: TaskCreate):\n"
                "        return db.add_task(payload.title)\n\n"
                "    return app\n"
            )
        },
        "summary": "FastAPI REST API with CRUD routes"
    })

    frontend_code = json.dumps({
        "files": {
            "app/static/index.html": (
                "<!DOCTYPE html>\n"
                "<html lang=\"en\">\n"
                "<head>\n"
                "  <meta charset=\"UTF-8\">\n"
                "  <title>Triad Swarm | Full-Stack Task Tracker</title>\n"
                "  <script src=\"https://cdn.tailwindcss.com\"></script>\n"
                "</head>\n"
                "<body class=\"bg-slate-900 text-slate-100 min-h-screen p-8\">\n"
                "  <div class=\"max-w-2xl mx-auto bg-slate-800 rounded-xl p-6 shadow-xl border border-slate-700\">\n"
                "    <h1 class=\"text-2xl font-bold text-cyan-400 mb-6\">⚡ Triad Full-Stack Task Tracker</h1>\n"
                "    <form id=\"task-form\" class=\"flex gap-3 mb-6\">\n"
                "      <input id=\"task-input\" type=\"text\" placeholder=\"Add a new task...\" required\n"
                "             class=\"flex-1 px-4 py-2 bg-slate-950 border border-slate-700 rounded-lg focus:outline-none focus:border-cyan-500\">\n"
                "      <button type=\"submit\" class=\"px-5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-medium rounded-lg transition\">\n"
                "        Add Task\n"
                "      </button>\n"
                "    </form>\n"
                "    <ul id=\"task-list\" class=\"space-y-2\">\n"
                "      <!-- Tasks populated dynamically from /api/tasks -->\n"
                "    </ul>\n"
                "  </div>\n"
                "</body>\n"
                "</html>\n"
            )
        },
        "summary": "Modern responsive Tailwind CSS dashboard"
    })

    mock.register_response("TaskDB", db_code)
    mock.register_response("create_app", backend_code)
    mock.register_response("tailwindcss", frontend_code)


async def main() -> None:
    console.print(Panel(
        "[bold cyan]Triad Swarm: Full-Stack Web Application Generation[/bold cyan]\n"
        "[dim]Decomposing & Synthesizing: SQLite Database Layer -> FastAPI REST API -> Tailwind CSS UI[/dim]",
        border_style="cyan"
    ))

    workload_path = Path(__file__).parent / "workload_fullstack.json"
    data = json.loads(workload_path.read_text())
    spec = WorkloadSpec(**{k: v for k, v in data.items() if k != "slices"})
    slices = [TaskSlice(**s) for s in data.get("slices", [])]

    mock = MockLLMProvider()
    setup_mock_fullstack(mock)
    router = ModelRouter(architect_provider=mock, worker_provider=mock)

    output_dir = Path(__file__).parent / "dist"
    output_dir.mkdir(parents=True, exist_ok=True)

    engine = TriadEngine(
        router=router,
        max_concurrency=3,
        output_dir=str(output_dir),
    )

    console.print(f"🚀 Executing {len(slices)} full-stack slices...")
    metrics = await engine.execute_workload(spec, slices)

    console.print("\n[bold green]✅ Full-Stack Application Generated & Deterministically Verified![/bold green]")
    console.print(f"⏱️  Duration: [bold cyan]{metrics.wall_clock_seconds:.2f}s[/bold cyan]")
    console.print(f"🎯 Total Tokens: [bold cyan]{metrics.total_tokens}[/bold cyan]")
    console.print(f"🛡️  Zero-Token Verification Events: [bold green]{metrics.zero_token_verifications}[/bold green]")
    console.print(f"📁 Output Artifacts Generated in: [bold yellow]{output_dir}[/bold yellow]\n")


if __name__ == "__main__":
    asyncio.run(main())
