import pytest
import concurrent.futures
from triad.core.token_tracker import TokenTracker


def test_token_tracker_basic():
    tracker = TokenTracker(
        prompt_price_per_m=0.15,
        completion_price_per_m=0.60,
        cached_price_per_m=0.0375,
    )

    rec = tracker.record_usage(
        agent_id="worker_01",
        phase="worker",
        prompt_tokens=1000,
        completion_tokens=200,
        cached_tokens=0,
    )

    assert tracker.total_prompt_tokens == 1000
    assert tracker.total_completion_tokens == 200
    assert tracker.total_tokens == 1200
    assert tracker.total_cost_usd > 0.0


def test_zero_token_events():
    tracker = TokenTracker()
    assert tracker.zero_token_events == 0

    tracker.record_zero_token_event("deterministic_verifier", "ast_check_pass")
    tracker.record_zero_token_event("deterministic_verifier", "pytest_pass")

    assert tracker.zero_token_events == 2
    assert tracker.total_tokens == 0
    assert tracker.total_cost_usd == 0.0


def test_thread_safety():
    tracker = TokenTracker()

    def worker_log(idx: int):
        tracker.record_usage(
            agent_id=f"worker_{idx}",
            phase="worker",
            prompt_tokens=100,
            completion_tokens=50,
        )
        tracker.record_zero_token_event("verifier")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker_log, i) for i in range(50)]
        concurrent.futures.wait(futures)

    assert tracker.total_tokens == 50 * 150
    assert tracker.zero_token_events == 50


def test_markdown_report_generation():
    tracker = TokenTracker()
    tracker.record_usage("architect_01", "architect", 800, 400)
    tracker.record_usage("worker_01", "worker", 500, 250)
    tracker.record_zero_token_event("verifier")

    report = tracker.generate_markdown_report()
    assert "Triad Swarm Token Economics Report" in report
    assert "deterministic_verifier" in report
    assert "architect" in report
