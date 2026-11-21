"""Isolated local sandbox environment providing minimalist Pi-style file and execution tools with resource limits."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

try:  # POSIX-only; imported eagerly so child processes never take an import lock.
    import resource
except ImportError:  # pragma: no cover - Windows
    resource = None  # type: ignore[assignment]


@dataclass
class ResourceLimits:
    """Production execution limits for sandboxed child processes."""

    max_memory_mb: Optional[int] = 512
    max_cpu_seconds: Optional[int] = 30
    max_open_files: Optional[int] = 256
    allow_network: bool = True


def _create_posix_preexec(limits: Optional[ResourceLimits]) -> Optional[Callable[[], None]]:
    """Create a POSIX preexec_fn to set RLIMIT limits before process starts."""
    if not limits or sys.platform == "win32":
        return None

    def _preexec() -> None:
        if resource is None:
            return
        try:
            if limits.max_memory_mb:
                limit_bytes = limits.max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
            if limits.max_cpu_seconds:
                resource.setrlimit(resource.RLIMIT_CPU, (limits.max_cpu_seconds, limits.max_cpu_seconds))
            if limits.max_open_files:
                resource.setrlimit(resource.RLIMIT_NOFILE, (limits.max_open_files, limits.max_open_files))
        except Exception:
            pass

    return _preexec


class IsolatedSandbox:
    """An isolated filesystem and execution environment for a single Worker Agent."""

    def __init__(
        self,
        base_dir: Optional[str] = None,
        cleanup: bool = False,
        allowed_files: Optional[List[str]] = None,
        resource_limits: Optional[ResourceLimits] = None,
    ):
        self.cleanup = cleanup
        self.allowed_files = allowed_files
        self.resource_limits = resource_limits or ResourceLimits()
        if base_dir:
            self.root = Path(base_dir).resolve()
            self.root.mkdir(parents=True, exist_ok=True)
            self._is_temp = False
        else:
            self._temp_dir = tempfile.mkdtemp(prefix="triad_sandbox_")
            self.root = Path(self._temp_dir).resolve()
            self._is_temp = True

    def resolve_path(self, relative_path: str) -> Path:
        """Resolve and validate that the target path does not escape sandbox root."""
        p = (self.root / relative_path).resolve()
        try:
            p.relative_to(self.root)
        except ValueError:
            raise PermissionError(f"Access denied: path '{relative_path}' escapes sandbox boundary.")
        return p

    def is_file_allowed(self, relative_path: str) -> bool:
        # ``None`` means unrestricted; an explicitly empty allowlist denies all
        # writes so a slice with no target files cannot escape context isolation.
        if self.allowed_files is None:
            return True
        norm = os.path.normpath(relative_path)
        for allowed in self.allowed_files:
            if norm == os.path.normpath(allowed):
                return True
        return False

    def read_file(self, relative_path: str) -> str:
        """Minimal read tool."""
        p = self.resolve_path(relative_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        return p.read_text(encoding="utf-8")

    def write_file(self, relative_path: str, content: str) -> None:
        """Minimal write tool."""
        if not self.is_file_allowed(relative_path):
            raise PermissionError(f"Write not permitted for target '{relative_path}'. Allowed: {self.allowed_files}")
        p = self.resolve_path(relative_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def edit_file(self, relative_path: str, target: str, replacement: str) -> bool:
        """Minimal search-and-replace edit tool."""
        if not self.is_file_allowed(relative_path):
            raise PermissionError(f"Edit not permitted for target '{relative_path}'.")
        p = self.resolve_path(relative_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        content = p.read_text(encoding="utf-8")
        if target not in content:
            return False
        new_content = content.replace(target, replacement, 1)
        p.write_text(new_content, encoding="utf-8")
        return True

    def mount_artifacts_from(self, source_sandbox: IsolatedSandbox, files: Optional[List[str]] = None) -> List[str]:
        """
        Mount / copy verified upstream artifacts into this sandbox.
        Essential for DAG wave execution where downstream slices consume upstream modules.
        """
        mounted = []
        source_files = source_sandbox.get_all_written_files()
        for rel_path, content in source_files.items():
            if files is None or rel_path in files:
                p = self.resolve_path(rel_path)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
                mounted.append(rel_path)
        return mounted

    def exec_command(self, cmd: str, timeout_seconds: int = 30) -> Tuple[int, str, str]:
        """Minimal exec tool running inside the sandbox root directory with isolated PYTHONPATH and resource limits."""
        env = dict(os.environ)
        # Ensure root directory is on PYTHONPATH for clean relative imports
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{self.root}:{existing_pythonpath}" if existing_pythonpath else str(self.root)
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        if not self.resource_limits.allow_network:
            # Block outbound socket traffic by setting dummy local non-existent proxies
            env["http_proxy"] = "http://127.0.0.1:0"
            env["https_proxy"] = "http://127.0.0.1:0"
            env["all_proxy"] = "socks5://127.0.0.1:0"
            env["NO_PROXY"] = "localhost,127.0.0.1"

        preexec = _create_posix_preexec(self.resource_limits)

        try:
            res = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=env,
                preexec_fn=preexec,
            )
            return res.returncode, res.stdout, res.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout_seconds} seconds."
        except Exception as e:
            return -1, "", str(e)

    def list_files(self, pattern: str = "**/*") -> List[str]:
        """List all relative file paths in the sandbox, ignoring cache and bytecode."""
        results = []
        ignored_parts = {"__pycache__", ".pytest_cache", ".git", ".venv"}
        for p in self.root.glob(pattern):
            if p.is_file():
                rel = p.relative_to(self.root)
                # Ignore bytecode and internal test caches
                if any(part in ignored_parts or part.startswith(".") for part in rel.parts):
                    continue
                if rel.suffix in {".pyc", ".pyo", ".pyd"}:
                    continue
                results.append(str(rel))
        return sorted(results)

    def get_all_written_files(self) -> Dict[str, str]:
        """Retrieve a mapping of all files written in the sandbox."""
        files = {}
        for rel in self.list_files():
            files[rel] = self.read_file(rel)
        return files

    def sync_to(self, destination_dir: str, overwrite: bool = True) -> List[str]:
        """Copy all files from this sandbox to a destination directory."""
        dest_root = Path(destination_dir).resolve()
        synced = []
        for rel, content in self.get_all_written_files().items():
            target_p = dest_root / rel
            if not target_p.exists() or overwrite:
                target_p.parent.mkdir(parents=True, exist_ok=True)
                target_p.write_text(content, encoding="utf-8")
                synced.append(rel)
        return synced

    def close(self) -> None:
        """Clean up temporary sandbox directory if enabled."""
        if self._is_temp and self.cleanup and self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> IsolatedSandbox:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
