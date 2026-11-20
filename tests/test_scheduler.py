import pytest
from triad.core.models import InterfaceContract, TaskSlice
from triad.orchestrator.scheduler import CircularDependencyError, DAGScheduler, MissingDependencyError


def make_slice(slice_id: str, dependencies=None) -> TaskSlice:
    return TaskSlice(
        slice_id=slice_id,
        title=f"Title {slice_id}",
        description="desc",
        contract=InterfaceContract(module_path=f"{slice_id}.py"),
        dependencies=dependencies or [],
    )


def test_independent_slices_single_wave():
    s1 = make_slice("s1")
    s2 = make_slice("s2")
    s3 = make_slice("s3")

    scheduler = DAGScheduler([s1, s2, s3])
    assert len(scheduler.waves) == 1
    assert len(scheduler.waves[0]) == 3


def test_multi_wave_dependencies():
    # s1 -> s2 -> s3
    s1 = make_slice("s1")
    s2 = make_slice("s2", dependencies=["s1"])
    s3 = make_slice("s3", dependencies=["s2"])
    s4 = make_slice("s4", dependencies=["s1"])

    scheduler = DAGScheduler([s1, s2, s3, s4])
    # Wave 0: s1
    # Wave 1: s2, s4
    # Wave 2: s3
    assert len(scheduler.waves) == 3
    assert [s.slice_id for s in scheduler.waves[0]] == ["s1"]
    assert set(s.slice_id for s in scheduler.waves[1]) == {"s2", "s4"}
    assert [s.slice_id for s in scheduler.waves[2]] == ["s3"]


def test_circular_dependency_detected():
    s1 = make_slice("s1", dependencies=["s2"])
    s2 = make_slice("s2", dependencies=["s1"])

    with pytest.raises(CircularDependencyError) as exc_info:
        DAGScheduler([s1, s2])
    assert "Circular dependency detected" in str(exc_info.value)


def test_missing_dependency_detected():
    s1 = make_slice("s1", dependencies=["non_existent_slice"])

    with pytest.raises(MissingDependencyError) as exc_info:
        DAGScheduler([s1])
    assert "non_existent_slice" in str(exc_info.value)


def test_mermaid_and_ascii_rendering():
    s1 = make_slice("s1")
    s2 = make_slice("s2", dependencies=["s1"])

    scheduler = DAGScheduler([s1, s2])
    mermaid = scheduler.to_mermaid()
    ascii_out = scheduler.to_ascii()

    assert "flowchart TD" in mermaid
    assert "s1 --> s2" in mermaid
    assert "Wave 1" in ascii_out
    assert "Wave 2" in ascii_out
