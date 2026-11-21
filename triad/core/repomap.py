"""AST-based repository mapping for brownfield project comprehension.

Extracts exported symbols, class hierarchies, and type signatures across Python
and TypeScript files to provide the Architect with bounded (<1,000 tokens)
codebase context without quadratic file reading costs.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import List, Set, Tuple

DEFAULT_IGNORED_DIRS: Set[str] = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".triad_cache",
    "dist",
    "build",
    ".egg-info",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
}


class RepoMapGenerator:
    """Generates concise, token-budgeted AST summaries of existing codebases."""

    def __init__(self, root_dir: str = ".", max_tokens: int = 1200):
        self.root_dir = Path(root_dir).resolve()
        self.max_tokens = max_tokens

    def _read_gitignore(self) -> Set[str]:
        """Parse basic .gitignore patterns if present."""
        gi_path = self.root_dir / ".gitignore"
        ignored = set(DEFAULT_IGNORED_DIRS)
        if gi_path.exists():
            for line in gi_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    clean = line.rstrip("/").lstrip("/")
                    ignored.add(clean)
        return ignored

    def _parse_python_ast(self, content: str) -> List[str]:
        """Extract classes, methods, and functions from Python source via AST."""
        lines: List[str] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                bases = [ast.unparse(b) for b in node.bases] if node.bases else []
                bases_str = f"({', '.join(bases)})" if bases else ""
                lines.append(f"  class {node.name}{bases_str}:")
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        is_async = "async " if isinstance(item, ast.AsyncFunctionDef) else ""
                        args_list = []
                        for arg in item.args.args:
                            arg_str = arg.arg
                            if arg.annotation:
                                arg_str += f": {ast.unparse(arg.annotation)}"
                            args_list.append(arg_str)
                        ret_ann = f" -> {ast.unparse(item.returns)}" if item.returns else ""
                        lines.append(f"    {is_async}def {item.name}({', '.join(args_list)}){ret_ann}: ...")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                is_async = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
                args_list = []
                for arg in node.args.args:
                    arg_str = arg.arg
                    if arg.annotation:
                        arg_str += f": {ast.unparse(arg.annotation)}"
                    args_list.append(arg_str)
                ret_ann = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                lines.append(f"  {is_async}def {node.name}({', '.join(args_list)}){ret_ann}: ...")
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                annotation = f": {ast.unparse(node.annotation)}" if node.annotation else ""
                lines.append(f"  {node.target.id}{annotation} = ...")
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        lines.append(f"  {target.id} = ...")

        return lines

    def _parse_ts_signatures(self, content: str) -> List[str]:
        """Extract exported interfaces, classes, and functions from TypeScript/JavaScript source."""
        lines: List[str] = []
        # Matches exported classes, interfaces, types, functions
        patterns = [
            r"export\s+interface\s+([A-Za-z0-9_]+(?:\s*<[^>]+>)?(?:\s+extends\s+[^{]+)?)",
            r"export\s+class\s+([A-Za-z0-9_]+(?:\s+extends\s+[A-Za-z0-9_]+)?(?:\s+implements\s+[^{]+)?)",
            r"export\s+type\s+([A-Za-z0-9_]+(?:\s*<[^>]+>)?\s*=\s*[^;\n]+)",
            r"export\s+(?:async\s+)?function\s+([A-Za-z0-9_]+\s*\([^)]*\)(?:\s*:\s*[^{;\n]+)?)",
            r"export\s+const\s+([A-Za-z0-9_]+\s*:\s*[^=\n]+)",
        ]
        for line in content.splitlines():
            line_str = line.strip()
            for pat in patterns:
                m = re.search(pat, line_str)
                if m:
                    lines.append(f"  {m.group(0).rstrip(' {')}")
                    break
        return lines

    def generate_map(self) -> str:
        """Scan workspace and generate bounded markdown summary of key interfaces."""
        ignored = self._read_gitignore()
        file_maps: List[Tuple[str, List[str]]] = []

        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".")]
            for file in sorted(files):
                if file.startswith("."):
                    continue
                file_path = Path(root) / file
                rel_path = file_path.relative_to(self.root_dir).as_posix()

                # Check if ignored
                if any(part in ignored for part in rel_path.split("/")):
                    continue

                if file.endswith(".py"):
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        signatures = self._parse_python_ast(content)
                        if signatures:
                            file_maps.append((rel_path, signatures))
                    except Exception:
                        pass
                elif file.endswith((".ts", ".tsx", ".js", ".jsx")):
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        signatures = self._parse_ts_signatures(content)
                        if signatures:
                            file_maps.append((rel_path, signatures))
                    except Exception:
                        pass

        # Assemble summary within max_tokens budget (approx 4 chars per token)
        max_chars = self.max_tokens * 4
        output_lines = ["### 🗺️ Project Repository AST Map"]
        current_chars = len(output_lines[0])
        files_included = 0

        for rel_path, sigs in file_maps:
            entry_header = f"\n📁 `{rel_path}`:"
            entry_body = "\n" + "\n".join(sigs)
            entry_total = entry_header + entry_body

            if current_chars + len(entry_total) > max_chars:
                remaining = len(file_maps) - files_included
                output_lines.append(f"\n[... {remaining} additional modules truncated for token budget ...]")
                break

            output_lines.append(entry_total)
            current_chars += len(entry_total)
            files_included += 1

        if len(output_lines) <= 1:
            return "### 🗺️ Project Repository AST Map\n*(No public classes or exported signatures detected)*"

        return "\n".join(output_lines)
