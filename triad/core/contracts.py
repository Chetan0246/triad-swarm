"""Deterministic AST-based contract verification, security linting, polyglot checks, and traceback pruning (Zero Token Cost)."""

from __future__ import annotations

import ast
import json
import re
from typing import Dict, List, Tuple

from triad.core.models import InterfaceContract


class ContractViolation(Exception):
    """Raised when an implementation fails to fulfill the Interface Contract."""
    pass


class ASTContractValidator:
    """
    Validates source code against an InterfaceContract using local CPU static analysis.
    Supports Python AST, type annotations, security import rules, and TypeScript/JS contracts.
    Consumes exactly 0 LLM tokens.
    """

    @classmethod
    def validate_code(cls, code_str: str, contract: InterfaceContract) -> Tuple[bool, List[str]]:
        """Validate code based on the contract's target language."""
        if contract.language in ("typescript", "javascript"):
            return cls._validate_typescript(code_str, contract)
        elif contract.language == "json_schema":
            return cls._validate_json_schema(code_str, contract)
        else:
            return cls._validate_python(code_str, contract)

    @classmethod
    def _validate_python(cls, code_str: str, contract: InterfaceContract) -> Tuple[bool, List[str]]:
        """Deep Python AST validation: symbols, signatures, type hints, classes, and forbidden imports."""
        errors: List[str] = []

        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            return False, [f"Syntax error at line {e.lineno}: {e.msg}"]

        found_symbols: Dict[str, ast.AST] = {}
        imported_modules: List[str] = []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found_symbols[node.name] = node
            elif isinstance(node, ast.ClassDef):
                found_symbols[node.name] = node
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        found_symbols[target.id] = node
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.append(node.module)

        # 1. Security Check: Forbidden Imports
        for forbidden in contract.forbidden_imports:
            for imp in imported_modules:
                if imp == forbidden or imp.startswith(f"{forbidden}."):
                    errors.append(f"Security violation: Forbidden module imported: '{imp}'")

        # 2. Check exported symbols
        for symbol in contract.exported_symbols:
            if symbol not in found_symbols:
                errors.append(f"Missing required exported symbol: '{symbol}'")

        # 3. Check signatures if specified
        for symbol, expected_sig in contract.signatures.items():
            if symbol in found_symbols:
                node = found_symbols[symbol]
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    actual_args = [arg.arg for arg in node.args.args if arg.arg != "self"]
                    # If expected_sig has a parenthesized arg list, verify each expected arg is present
                    open_idx = expected_sig.find("(")
                    close_idx = expected_sig.find(")", open_idx + 1) if open_idx != -1 else -1
                    if open_idx != -1 and close_idx != -1:
                        arg_part = expected_sig[open_idx + 1 : close_idx]
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

        # 4. Check Type Hints if explicitly specified in contract
        for symbol, type_map in contract.type_hints.items():
            if symbol in found_symbols:
                node = found_symbols[symbol]
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    actual_arg_annotations = {
                        arg.arg: ast.unparse(arg.annotation) if arg.annotation else None
                        for arg in node.args.args
                        if arg.arg != "self"
                    }
                    for arg_name, expected_type in type_map.items():
                        if arg_name == "return":
                            actual_ret = ast.unparse(node.returns) if node.returns else None
                            if actual_ret and expected_type not in actual_ret:
                                errors.append(
                                    f"Symbol '{symbol}' return type mismatch. Expected '{expected_type}', found '{actual_ret}'"
                                )
                        elif arg_name in actual_arg_annotations:
                            actual_t = actual_arg_annotations[arg_name]
                            if actual_t and expected_type not in actual_t:
                                errors.append(
                                    f"Argument '{arg_name}' of '{symbol}' type hint mismatch. Expected '{expected_type}', found '{actual_t}'"
                                )

        # 5. Check Required Classes and their methods
        for class_name, required_methods in contract.required_classes.items():
            class_node = found_symbols.get(class_name)
            if class_node is None:
                errors.append(f"Required class '{class_name}' not found.")
            elif isinstance(class_node, ast.ClassDef):
                class_methods = {
                    item.name
                    for item in class_node.body
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                for method in required_methods:
                    if method not in class_methods:
                        errors.append(
                            f"Class '{class_name}' is missing required method '{method}'"
                        )
            else:
                errors.append(f"Symbol '{class_name}' was expected to be a class.")

        return len(errors) == 0, errors

    @classmethod
    def _validate_typescript(cls, code_str: str, contract: InterfaceContract) -> Tuple[bool, List[str]]:
        """Static zero-token validation for TypeScript / JavaScript exports and security."""
        errors: List[str] = []

        # 1. Security check: Forbidden imports for JS/TS
        for forbidden in contract.forbidden_imports:
            # Matches import ... from 'mod' or require('mod')
            pattern = rf"(?:from\s+[\"']{re.escape(forbidden)}(?:/[\w.-]+)?[\"']|require\s*\(\s*[\"']{re.escape(forbidden)}(?:/[\w.-]+)?[\"']\s*\))"
            if re.search(pattern, code_str):
                errors.append(f"Security violation: Forbidden module imported: '{forbidden}'")

        # 2. Find exported functions, classes, interfaces, types, consts, vars
        exported_functions = set(re.findall(r"export\s+(?:async\s+)?function\s+([a-zA-Z0-9_$]+)", code_str))
        exported_classes = set(re.findall(r"export\s+class\s+([a-zA-Z0-9_$]+)", code_str))
        exported_interfaces = set(re.findall(r"export\s+interface\s+([a-zA-Z0-9_$]+)", code_str))
        exported_types = set(re.findall(r"export\s+type\s+([a-zA-Z0-9_$]+)", code_str))
        exported_consts = set(re.findall(r"export\s+(?:const|let|var)\s+([a-zA-Z0-9_$]+)", code_str))
        all_exports = (
            exported_functions
            | exported_classes
            | exported_interfaces
            | exported_types
            | exported_consts
        )

        # Also support export { a, b, c }
        for match in re.findall(r"export\s*\{([^}]+)\}", code_str):
            for item in match.split(","):
                clean_item = item.strip().split(" as ")[-1].strip()
                if clean_item:
                    all_exports.add(clean_item)

        for symbol in contract.exported_symbols:
            if symbol not in all_exports:
                errors.append(f"Missing required TypeScript export: '{symbol}'")

        return len(errors) == 0, errors

    @classmethod
    def _validate_json_schema(cls, code_str: str, contract: InterfaceContract) -> Tuple[bool, List[str]]:
        """Validate JSON data string against required schema keys."""
        errors: List[str] = []
        try:
            data = json.loads(code_str)
        except Exception as e:
            return False, [f"Invalid JSON content: {str(e)}"]

        if contract.contract_schema and isinstance(data, dict):
            required = contract.contract_schema.get("required", [])
            for key in required:
                if key not in data:
                    errors.append(f"Missing required JSON property: '{key}'")

        return len(errors) == 0, errors


class TracebackPruner:
    """
    Intelligent test failure pruning.
    Compresses hundreds of lines of raw pytest / python traceback into high-signal
    essence: failing test, assertion error diff, and target line.
    Saves 60%-80% tokens on self-healing retry prompts.
    """

    @staticmethod
    def prune(raw_trace: str, max_lines: int = 15) -> str:
        """Extract only actionable error context from raw execution output."""
        if not raw_trace:
            return "Unknown verification error."

        lines = raw_trace.strip().splitlines()
        pruned: List[str] = []
        capture = False

        for line in lines:
            # Capture failure lines, errors, assertions, and summary
            if any(marker in line for marker in ["FAILED", "FAILURES", "AssertionError", "SyntaxError", "TypeError", "AttributeError", "E   "]):
                pruned.append(line)
                capture = True
            elif capture and (line.startswith(" ") or line.startswith(">")):
                pruned.append(line)
                if len(pruned) >= max_lines:
                    break

        if not pruned:
            # If standard markers not found, take the last few lines
            pruned = lines[-min(len(lines), max_lines):]

        return "\n".join(pruned[:max_lines])
