from triad.core.models import (
    InterfaceContract,
    SwarmMetrics,
    TaskSlice,
)


def test_interface_contract_creation():
    contract = InterfaceContract(
        module_path="core/storage.py",
        exported_symbols=["StorageClient", "save_record"],
        signatures={"save_record": "def save_record(key: str, data: dict) -> bool"},
        invariants=["key must not be empty"],
    )
    assert contract.module_path == "core/storage.py"
    assert "StorageClient" in contract.exported_symbols
    assert contract.invariants[0] == "key must not be empty"


def test_task_slice_model():
    contract = InterfaceContract(
        module_path="math_utils.py",
        exported_symbols=["compute_stats"],
    )
    task = TaskSlice(
        slice_id="slice_math",
        title="Math Utilities",
        description="Implement compute_stats function",
        target_files=["math_utils.py"],
        contract=contract,
        acceptance_tests={"tests/test_math.py": "def test_math(): assert True"},
    )
    assert task.slice_id == "slice_math"
    assert len(task.target_files) == 1
    assert "tests/test_math.py" in task.acceptance_tests


def test_swarm_metrics_model():
    metrics = SwarmMetrics(
        workload_name="Test Workload",
        total_agents_invoked=3,
        active_worker_concurrency=2,
        wall_clock_seconds=1.5,
        cumulative_worker_seconds=3.0,
        parallel_speedup=2.0,
        total_tokens=1500,
        prompt_tokens=1000,
        completion_tokens=500,
        cached_tokens=200,
        zero_token_verifications=2,
        llm_verifications=0,
        tasks_total=2,
        tasks_succeeded=2,
        success_rate=100.0,
        estimated_cost_usd=0.00045,
    )
    assert metrics.parallel_speedup == 2.0
    assert metrics.zero_token_verifications == 2
    assert metrics.success_rate == 100.0
