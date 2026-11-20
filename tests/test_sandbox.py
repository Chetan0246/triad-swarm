import os
import pytest
from triad.core.sandbox import IsolatedSandbox


def test_sandbox_write_read_edit():
    with IsolatedSandbox(cleanup=True) as sb:
        sb.write_file("src/hello.py", "print('hello')\n")
        content = sb.read_file("src/hello.py")
        assert content == "print('hello')\n"

        # Edit
        edited = sb.edit_file("src/hello.py", "hello", "world")
        assert edited is True
        assert sb.read_file("src/hello.py") == "print('world')\n"


def test_sandbox_path_traversal_prevention():
    with IsolatedSandbox(cleanup=True) as sb:
        with pytest.raises(PermissionError):
            sb.write_file("../forbidden.txt", "exploit")

        with pytest.raises(PermissionError):
            sb.read_file("/etc/passwd")


def test_sandbox_allowed_files_restriction():
    with IsolatedSandbox(cleanup=True, allowed_files=["allowed.py"]) as sb:
        sb.write_file("allowed.py", "x = 1")
        assert sb.read_file("allowed.py") == "x = 1"

        with pytest.raises(PermissionError):
            sb.write_file("unauthorized.py", "y = 2")


def test_sandbox_exec_command():
    with IsolatedSandbox(cleanup=True) as sb:
        code = "print('Triad Output')"
        sb.write_file("test.py", code)
        ret, stdout, stderr = sb.exec_command("python3 test.py")
        assert ret == 0
        assert "Triad Output" in stdout
