import pytest
from triad.core.contracts import ASTContractValidator
from triad.core.models import InterfaceContract


def test_ast_contract_success():
    code = """
class DataStore:
    def __init__(self):
        self.data = {}

def fetch_metric(metric_id: str, limit: int = 10) -> list:
    return []
"""
    contract = InterfaceContract(
        module_path="storage.py",
        exported_symbols=["DataStore", "fetch_metric"],
        signatures={"fetch_metric": "def fetch_metric(metric_id: str, limit: int) -> list"},
    )

    valid, errors = ASTContractValidator.validate_code(code, contract)
    assert valid is True
    assert len(errors) == 0


def test_ast_contract_missing_symbol():
    code = """
def other_func(): pass
"""
    contract = InterfaceContract(
        module_path="storage.py",
        exported_symbols=["ExpectedClass"],
    )

    valid, errors = ASTContractValidator.validate_code(code, contract)
    assert valid is False
    assert any("Missing required exported symbol: 'ExpectedClass'" in e for e in errors)


def test_ast_contract_signature_mismatch():
    code = """
def fetch_metric(wrong_param: str) -> list:
    return []
"""
    contract = InterfaceContract(
        module_path="storage.py",
        exported_symbols=["fetch_metric"],
        signatures={"fetch_metric": "def fetch_metric(metric_id: str) -> list"},
    )

    valid, errors = ASTContractValidator.validate_code(code, contract)
    assert valid is False
    assert any("missing expected argument 'metric_id'" in e for e in errors)
