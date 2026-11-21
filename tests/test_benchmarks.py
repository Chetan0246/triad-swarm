import pytest

from examples.benchmark_comparison import run_rigorous_benchmark
from examples.demo_workload import main as run_demo_main


@pytest.mark.asyncio
async def test_benchmark_script_execution():
    # Verify that the benchmark script runs without exceptions
    await run_rigorous_benchmark()


@pytest.mark.asyncio
async def test_demo_script_execution():
    # Verify that the demo script runs without exceptions
    await run_demo_main()
