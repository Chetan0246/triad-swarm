import json

import pytest

from triad.agents.architect import ArchitectAgent
from triad.agents.verifier import DeterministicVerifier
from triad.agents.worker import WorkerAgent
from triad.core.llm import MockLLMProvider
from triad.core.models import InterfaceContract, TaskSlice, WorkloadSpec
from triad.core.sandbox import IsolatedSandbox
from triad.core.token_tracker import TokenTracker


@pytest.mark.asyncio
async def test_architect_agent_decomposition():
    tracker = TokenTracker()
    mock_llm = MockLLMProvider()

    # Predefine Architect JSON response
    mock_architect_response = json.dumps(
        {
            "slices": [
                {
                    "slice_id": "slice_math",
                    "title": "Math Utilities",
                    "description": "Provide math helper functions",
                    "target_files": ["math_utils.py"],
                    "contract": {
                        "module_path": "math_utils.py",
                        "exported_symbols": ["add_numbers"],
                        "signatures": {"add_numbers": "def add_numbers(a: int, b: int) -> int"},
                        "invariants": ["a + b must equal return value"],
                    },
                    "acceptance_tests": {
                        "test_math.py": "from math_utils import add_numbers\ndef test_add(): assert add_numbers(2, 3) == 5"
                    },
                    "dependencies": [],
                }
            ]
        }
    )
    mock_llm.register_response("Workload Name", mock_architect_response)

    architect = ArchitectAgent(llm=mock_llm, tracker=tracker)
    spec = WorkloadSpec(name="Demo Project", description="Testing decomposition")

    slices = await architect.decompose_workload(spec)
    assert len(slices) == 1
    assert slices[0].slice_id == "slice_math"
    assert "add_numbers" in slices[0].contract.exported_symbols
    assert tracker.total_prompt_tokens > 0


@pytest.mark.asyncio
async def test_worker_agent_execution_and_verifier():
    tracker = TokenTracker()
    mock_llm = MockLLMProvider()

    worker_code_response = json.dumps(
        {
            "files": {"math_utils.py": "def add_numbers(a: int, b: int) -> int:\n    return a + b\n"},
            "summary": "Implemented add_numbers",
        }
    )
    mock_llm.register_response("Task Slice: slice_math", worker_code_response)

    contract = InterfaceContract(
        module_path="math_utils.py",
        exported_symbols=["add_numbers"],
        signatures={"add_numbers": "def add_numbers(a: int, b: int) -> int"},
    )
    task_slice = TaskSlice(
        slice_id="slice_math",
        title="Math Utilities",
        description="Implement add_numbers",
        target_files=["math_utils.py"],
        contract=contract,
        acceptance_tests={
            "test_math.py": "from math_utils import add_numbers\ndef test_add():\n    assert add_numbers(10, 5) == 15\n"
        },
    )

    worker = WorkerAgent(worker_id="worker_math", llm=mock_llm, tracker=tracker)
    verifier = DeterministicVerifier(tracker=tracker)

    with IsolatedSandbox(cleanup=True) as sb:
        # Worker execution
        exec_res = await worker.execute_slice(task_slice, sb)
        assert exec_res.status == "success"
        assert "math_utils.py" in exec_res.files_written

        # Verifier execution
        verif_res = verifier.verify(task_slice, sb)
        assert verif_res.passed is True
        assert verif_res.exit_code == 0
        assert verif_res.tokens_used == 0

        # Check that 0-token event was recorded
        assert tracker.zero_token_events == 1
