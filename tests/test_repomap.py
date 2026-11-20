"""Tests for Brownfield AST Repository Mapping."""

import tempfile
from pathlib import Path
from triad.core.repomap import RepoMapGenerator


def test_python_ast_extraction():
    code = """
class DataPipeline:
    \"\"\"Process raw telemetry streams.\"\"\"
    def __init__(self, buffer_size: int = 100):
        self.buffer_size = buffer_size

    async def ingest(self, payload: dict) -> bool:
        return True

def standalone_helper(x: int, y: int) -> int:
    return x + y
"""
    gen = RepoMapGenerator()
    lines = gen._parse_python_ast(code)
    text = "\n".join(lines)
    assert "class DataPipeline:" in text
    assert "async def ingest(self, payload: dict) -> bool: ..." in text
    assert "def standalone_helper(x: int, y: int) -> int: ..." in text


def test_typescript_signatures_extraction():
    ts_code = """
export interface UserPayload {
    id: string;
    roles: string[];
}

export class AuthenticationService {
    async verifyToken(token: string): Promise<boolean> {
        return true;
    }
}

export function computeHash(data: string): string {
    return data;
}
"""
    gen = RepoMapGenerator()
    lines = gen._parse_ts_signatures(ts_code)
    text = "\n".join(lines)
    assert "export interface UserPayload" in text
    assert "export class AuthenticationService" in text
    assert "export function computeHash(data: string): string" in text


def test_repomap_generator_end_to_end():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "core").mkdir()
        (root / "core" / "app.py").write_text("class Server:\n    def start(self, port: int) -> None: pass\n")
        (root / "ui").mkdir()
        (root / "ui" / "widget.ts").write_text("export interface ButtonProps { label: string }\n")

        gen = RepoMapGenerator(root_dir=tmpdir, max_tokens=500)
        repomap = gen.generate_map()

        assert "Project Repository AST Map" in repomap
        assert "core/app.py" in repomap
        assert "class Server:" in repomap
        assert "ui/widget.ts" in repomap
        assert "export interface ButtonProps" in repomap
