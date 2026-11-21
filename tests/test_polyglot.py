"""Tests for Polyglot Verification Gates (TypeScript/JavaScript)."""

from triad.agents.polyglot import PolyglotTracebackPruner
from triad.agents.verifier import DeterministicVerifier
from triad.core.models import InterfaceContract, TaskSlice
from triad.core.sandbox import IsolatedSandbox
from triad.core.token_tracker import TokenTracker


def test_polyglot_traceback_pruning():
    raw_vitest_output = """
    FAIL  tests/calculator.test.ts
    ✕ adds two numbers (5 ms)

      AssertionError: expected 5 to be 6 // Object.is equality

      - Expected:
      6
      + Received:
      5

        at tests/calculator.test.ts:4:18
        at process.processTicksAndRejections (node:internal/process/task_queues:95:5)
        at runTest (/Users/node_modules/vitest/dist/entry.js:120:25)
    """
    pruned = PolyglotTracebackPruner.prune(raw_vitest_output)
    assert "AssertionError: expected 5 to be 6" in pruned
    assert "Expected:" in pruned
    assert "Received:" in pruned
    assert "node_modules/vitest" not in pruned


def test_polyglot_verifier_static_contract():
    tracker = TokenTracker()
    verifier = DeterministicVerifier(tracker=tracker)

    contract = InterfaceContract(
        module_path="src/service.ts",
        exported_symbols=["UserService", "createUser"],
        language="typescript",
    )
    slice_item = TaskSlice(
        slice_id="slice_ts_01",
        title="User Service in TS",
        description="Implement UserService and createUser",
        target_files=["src/service.ts"],
        contract=contract,
    )

    # Valid TypeScript code
    sandbox = IsolatedSandbox()
    sandbox.write_file(
        "src/service.ts",
        "export class UserService {}\nexport function createUser() {}\n",
    )

    res = verifier.verify(slice_item, sandbox)
    assert res.passed is True
    assert res.tokens_used == 0

    # Missing symbol
    sandbox_fail = IsolatedSandbox()
    sandbox_fail.write_file("src/service.ts", "export class UserService {}\n")
    res_fail = verifier.verify(slice_item, sandbox_fail)
    assert res_fail.passed is False
    assert "Missing required TypeScript export: 'createUser'" in res_fail.ast_errors[0]
