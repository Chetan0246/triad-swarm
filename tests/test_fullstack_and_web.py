"""Tests for Full-Stack (Frontend, Backend, Database) and Web/Asset verification in Triad Swarm."""

from triad.agents.verifier import DeterministicVerifier
from triad.core.contracts import ASTContractValidator
from triad.core.models import InterfaceContract, TaskSlice
from triad.core.sandbox import IsolatedSandbox
from triad.core.token_tracker import TokenTracker
from triad.orchestrator.scheduler import DAGScheduler


def test_html_and_css_web_contract_validation():
    """Verify that HTML and CSS assets validate deterministically without Python AST errors."""
    html_contract = InterfaceContract(
        module_path="templates/index.html",
        exported_symbols=["<form id=\"task-form\"", "class=\"btn-primary\"", "<table id=\"tasks-table\""],
        forbidden_imports=["<script src=\"http://malicious.com\""],
        language="html",
    )

    valid_html = """<!DOCTYPE html>
<html lang="en">
<head><title>Tasks</title></head>
<body>
  <form id="task-form">
    <button class="btn-primary">Submit</button>
  </form>
  <table id="tasks-table"></table>
</body>
</html>"""

    passed, errors = ASTContractValidator.validate_code(valid_html, html_contract)
    assert passed is True
    assert len(errors) == 0

    # Test missing element failure
    invalid_html = "<html><body>Missing table</body></html>"
    passed, errors = ASTContractValidator.validate_code(invalid_html, html_contract)
    assert passed is False
    assert any("Missing required" in e for e in errors)


def test_fullstack_dag_orchestration():
    """Verify that a multi-tier full-stack application DAG forms sequential waves: DB -> Backend -> Frontend."""
    slices = [
        TaskSlice(
            slice_id="slice_01_db",
            title="Database Layer",
            description="Create SQLite database models",
            target_files=["models.py"],
            contract=InterfaceContract(
                module_path="models.py",
                exported_symbols=["TaskModel", "init_db"],
                language="python",
            ),
            acceptance_tests={
                "tests/test_db.py": "def test_db(): assert True"
            },
            dependencies=[],
        ),
        TaskSlice(
            slice_id="slice_02_backend",
            title="FastAPI REST API",
            description="Create /api/tasks endpoints",
            target_files=["server.py"],
            contract=InterfaceContract(
                module_path="server.py",
                exported_symbols=["app"],
                language="python",
            ),
            acceptance_tests={
                "tests/test_api.py": "def test_api(): assert True"
            },
            dependencies=["slice_01_db"],
        ),
        TaskSlice(
            slice_id="slice_03_frontend",
            title="Tailwind Web UI",
            description="Create interactive dashboard page",
            target_files=["static/index.html"],
            contract=InterfaceContract(
                module_path="static/index.html",
                exported_symbols=["<main id=\"app\">", "class=\"container\""],
                language="html",
            ),
            acceptance_tests={
                "tests/test_ui.py": (
                    "def test_ui():\n"
                    "    with open('static/index.html') as f:\n"
                    "        content = f.read()\n"
                    "    assert 'id=\"app\"' in content\n"
                )
            },
            dependencies=["slice_02_backend"],
        ),
    ]

    scheduler = DAGScheduler(slices)
    waves = scheduler.waves
    assert len(waves) == 3
    assert waves[0][0].slice_id == "slice_01_db"
    assert waves[1][0].slice_id == "slice_02_backend"
    assert waves[2][0].slice_id == "slice_03_frontend"


def test_verifier_end_to_end_on_frontend_asset(tmp_path):
    """Verify that DeterministicVerifier handles static frontend assets with 0 tokens consumed."""
    tracker = TokenTracker()
    verifier = DeterministicVerifier(tracker)
    sandbox = IsolatedSandbox(base_dir=tmp_path)

    task_slice = TaskSlice(
        slice_id="slice_frontend",
        title="Web Interface Component",
        description="Write index.html component",
        target_files=["index.html"],
        contract=InterfaceContract(
            module_path="index.html",
            exported_symbols=["<div id=\"root\">", "Tailwind CSS"],
            language="html",
        ),
        acceptance_tests={},
        dependencies=[],
    )

    # Worker generates file in sandbox
    sandbox.write_file("index.html", "<html><body><!-- Tailwind CSS --><div id=\"root\">Dashboard</div></body></html>")

    result = verifier.verify(task_slice, sandbox)
    assert result.passed is True
    assert result.tokens_used == 0
    assert tracker.zero_token_events >= 1
