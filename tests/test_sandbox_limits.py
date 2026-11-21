"""Tests for sandbox resource limits and execution safety."""

import sys
from pathlib import Path

from triad.core.sandbox import IsolatedSandbox, ResourceLimits, _create_posix_preexec


def test_resource_limits_dataclass():
    limits = ResourceLimits(
        max_memory_mb=256,
        max_cpu_seconds=10,
        max_open_files=128,
        allow_network=False,
    )
    assert limits.max_memory_mb == 256
    assert limits.max_cpu_seconds == 10
    assert limits.max_open_files == 128
    assert limits.allow_network is False


def test_preexec_creation():
    limits = ResourceLimits(max_memory_mb=512)
    preexec = _create_posix_preexec(limits)
    if sys.platform != "win32":
        assert callable(preexec)
    else:
        assert preexec is None


def test_sandbox_context_manager(tmp_path: Path):
    with IsolatedSandbox(base_dir=str(tmp_path), cleanup=False) as sb:
        sb.write_file("test.txt", "hello production")
        assert sb.read_file("test.txt") == "hello production"


def test_sandbox_network_blocking_env(tmp_path: Path):
    limits = ResourceLimits(allow_network=False)
    with IsolatedSandbox(base_dir=str(tmp_path), resource_limits=limits) as sb:
        code = 'import os; print("proxy=" + os.environ.get("http_proxy", ""))'
        rc, out, err = sb.exec_command(f"python3 -c '{code}'")
        assert rc == 0
        assert "proxy=http://127.0.0.1:0" in out


def test_sandbox_cpu_limit_timeout(tmp_path: Path):
    limits = ResourceLimits(max_cpu_seconds=2)
    with IsolatedSandbox(base_dir=str(tmp_path), resource_limits=limits) as sb:
        # Timeout at python level or subproc level
        code = "import time; time.sleep(10)"
        rc, out, err = sb.exec_command(f"python3 -c '{code}'", timeout_seconds=1)
        assert rc == -1
        assert "timed out" in err.lower()
