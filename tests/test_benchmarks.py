import pytest

from examples.automation_scraper.run_scraper import main as run_scraper_main
from examples.benchmark_comparison import run_rigorous_benchmark
from examples.demo_workload import main as run_demo_main
from examples.fullstack_app.run_fullstack import main as run_fullstack_main


@pytest.mark.asyncio
async def test_benchmark_script_execution():
    # Verify that the benchmark script runs without exceptions
    await run_rigorous_benchmark()


@pytest.mark.asyncio
async def test_demo_script_execution():
    # Verify that the demo script runs without exceptions
    await run_demo_main()


@pytest.mark.asyncio
async def test_fullstack_example_script_execution():
    # Verify that the fullstack app generation example runs without exceptions
    await run_fullstack_main()


@pytest.mark.asyncio
async def test_scraper_example_script_execution():
    # Verify that the scraper pipeline example runs without exceptions
    await run_scraper_main()
