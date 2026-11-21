from triad.core.contracts import ASTContractValidator, TracebackPruner
from triad.core.models import InterfaceContract


def test_ast_type_hints_validation():
    code = "def compute_total(price: float, quantity: int) -> float:\n    return price * quantity\n"
    contract = InterfaceContract(
        module_path="calc.py",
        exported_symbols=["compute_total"],
        signatures={"compute_total": "def compute_total(price, quantity)"},
        type_hints={
            "compute_total": {
                "price": "float",
                "quantity": "int",
                "return": "float",
            }
        },
    )
    is_valid, errors = ASTContractValidator.validate_code(code, contract)
    assert is_valid
    assert len(errors) == 0

    # Test type mismatch
    bad_code = "def compute_total(price: str, quantity: int) -> int:\n    return 0\n"
    is_valid_bad, errors_bad = ASTContractValidator.validate_code(bad_code, contract)
    assert not is_valid_bad
    assert any("type hint mismatch" in e or "return type mismatch" in e for e in errors_bad)


def test_ast_required_classes_and_methods():
    code = "class EventDispatcher:\n    def dispatch(self, event: str) -> bool:\n        return True\n"
    contract = InterfaceContract(
        module_path="events.py",
        exported_symbols=["EventDispatcher"],
        required_classes={"EventDispatcher": ["dispatch", "subscribe"]},
    )
    is_valid, errors = ASTContractValidator.validate_code(code, contract)
    assert not is_valid
    assert any("missing required method 'subscribe'" in e for e in errors)


def test_ast_security_forbidden_imports():
    safe_code = "import math\nimport json\ndef run(): return math.sqrt(4)\n"
    unsafe_code = "import subprocess\nimport os\ndef run(): subprocess.run('ls')\n"

    contract = InterfaceContract(
        module_path="safe.py",
        exported_symbols=["run"],
        forbidden_imports=["subprocess", "pickle"],
    )

    is_valid_safe, err_safe = ASTContractValidator.validate_code(safe_code, contract)
    assert is_valid_safe

    is_valid_unsafe, err_unsafe = ASTContractValidator.validate_code(unsafe_code, contract)
    assert not is_valid_unsafe
    assert any("Forbidden module imported: 'subprocess'" in e for e in err_unsafe)


def test_typescript_static_contract_validation():
    ts_code = (
        "export function processItem(id: string): boolean { return true; }\n"
        "export class DataStore { items = []; }\n"
        "export const VERSION = '1.0.0';\n"
    )
    contract = InterfaceContract(
        module_path="index.ts",
        language="typescript",
        exported_symbols=["processItem", "DataStore", "VERSION", "missingExport"],
    )
    is_valid, errors = ASTContractValidator.validate_code(ts_code, contract)
    assert not is_valid
    assert len(errors) == 1
    assert "missingExport" in errors[0]


def test_traceback_pruner_compression():
    verbose_trace = (
        "============================= test session starts ==============================\n"
        "platform linux -- Python 3.13.0\n"
        "collecting ... collected 1 item\n"
        "test_service.py:10: in test_service\n"
        "    assert result == {'status': 'ok'}\n"
        "E   AssertionError: assert {'status': 'error'} == {'status': 'ok'}\n"
        "E     Differing items:\n"
        "E     {'status': 'error'} != {'status': 'ok'}\n"
        "FAILED test_service.py::test_service - AssertionError\n"
        "============================== 1 failed in 0.05s ==============================="
    )
    pruned = TracebackPruner.prune(verbose_trace, max_lines=6)
    assert "AssertionError" in pruned
    assert len(pruned.splitlines()) <= 6
    assert len(pruned) < len(verbose_trace)


def test_ast_annotated_assignment_exports():
    code = (
        "from typing import Final\n"
        "MAX_SIZE: int = 100\n"
        "API_VERSION: Final[str] = 'v1.0'\n"
        "def process(): return MAX_SIZE\n"
    )
    contract = InterfaceContract(
        module_path="constants.py",
        exported_symbols=["MAX_SIZE", "API_VERSION", "process"],
    )
    is_valid, errors = ASTContractValidator.validate_code(code, contract)
    assert is_valid, f"Expected valid, got: {errors}"
    assert len(errors) == 0


def test_ast_nested_forbidden_imports():
    # Nested inside a function body
    code = "def run_command(cmd: str):\n    import subprocess\n    return subprocess.run(cmd)\n"
    contract = InterfaceContract(
        module_path="worker.py",
        exported_symbols=["run_command"],
        forbidden_imports=["subprocess"],
    )
    is_valid, errors = ASTContractValidator.validate_code(code, contract)
    assert not is_valid
    assert any("Forbidden module imported: 'subprocess'" in e for e in errors)


def test_ast_relative_import_from_none():
    # from . import os or from . import helper where node.module is None
    code = "from . import os\ndef helper(): return True\n"
    contract = InterfaceContract(
        module_path="submodule.py",
        exported_symbols=["helper"],
        forbidden_imports=["os"],
    )
    is_valid, errors = ASTContractValidator.validate_code(code, contract)
    assert not is_valid
    assert any("Forbidden module imported: 'os'" in e for e in errors)


def test_ast_signature_parsing_with_defaults_args_kwargs():
    code = "def calculate(value: float = 10.0, *args, **kwargs) -> float:\n    return value\n"
    contract = InterfaceContract(
        module_path="math_ops.py",
        exported_symbols=["calculate"],
        signatures={"calculate": "def calculate(value=10.0, *args, **kwargs) -> float"},
    )
    is_valid, errors = ASTContractValidator.validate_code(code, contract)
    assert is_valid, f"Signature match failed: {errors}"
    assert len(errors) == 0
