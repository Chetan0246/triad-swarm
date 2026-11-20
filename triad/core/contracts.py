"""Deterministic AST-based contract verification (Zero Token Cost)."""

from __future__ import annotations

import ast
from typing import Dict, List, Optional, Tuple
from triad.core.models import InterfaceContract


class ContractViolation(Exception):
    """Raised when an implementation fails to fulfill the Interface Contract."""
    pass


class ASTContractValidator:
    """Validates Python source code against an InterfaceContract using the Python AST."""

    @staticmethod
    def validate_code(code_str: str, contract: InterfaceContract) -> Tuple[bool, List[str]]:
        """
        Verify that the code exports all expected symbols and conforms to signatures.
        Returns (is_valid, list_of_errors). Zero tokens consumed.
        """
        errors: List[str] = []

        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            return False, [f"Syntax error at line {e.lineno}: {e.msg}"]

        found_symbols: Dict[str, ast.AST] = {}

        for node in tree.body:
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                found_symbols[node.name] = node
            elif isinstance(node, ast.ClassDef):
                found_symbols[node.name] = node
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        found_symbols[target.id] = node

        # 1. Check exported symbols
        for symbol in contract.exported_symbols:
            if symbol not in found_symbols:
                errors.append(f"Missing required exported symbol: '{symbol}'")

        # 2. Check signatures if specified
        for symbol, expected_sig in contract.signatures.items():
            if symbol in found_symbols:
                node = found_symbols[symbol]
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    actual_args = [arg.arg for arg in node.args.args if arg.arg != "self"]
                    # If expected_sig has comma-separated args, verify presence
                    if "(" in expected_sig and ")" in expected_sig:
                        arg_part = expected_sig[expected_sig.find("(") + 1 : expected_sig.find(")")]
                        expected_args = [
                            a.strip().split(":")[0].strip()
                            for a in arg_part.split(",")
                            if a.strip() and a.strip() != "self"
                        ]
                        for exp_arg in expected_args:
                            if exp_arg not in actual_args and exp_arg != "...":
                                errors.append(
                                    f"Symbol '{symbol}' is missing expected argument '{exp_arg}'. Found: {actual_args}"
                                )

        return len(errors) == 0, errors
