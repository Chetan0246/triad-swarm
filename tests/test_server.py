"""Tests for FastAPI production server endpoints, metrics, and job manager."""

from fastapi.testclient import TestClient

from triad import __version__
from triad.server.app import app
from triad.server.metrics import metrics_registry
from triad.server.state import JobStatus

client = TestClient(app)


def test_healthz_liveness_probe():
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "triad-swarm"
    assert data["version"] == __version__
    assert "uptime_seconds" in data


def test_readyz_readiness_probe():
    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "active_jobs" in data


def test_metrics_prometheus_exposition():
    # Record sample metrics
    metrics_registry.record_job_completed(duration_seconds=1.23)
    metrics_registry.record_tokens("architect", 450)
    metrics_registry.record_tokens("worker", 650)
    metrics_registry.record_verification(passed=True)
    metrics_registry.record_cache_hit()

    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    text = response.text

    assert "triad_jobs_total" in text
    assert "triad_tokens_total" in text
    assert "triad_verification_events_total" in text
    assert "triad_cache_hits_total" in text
    assert "triad_job_duration_seconds" in text


def test_submit_and_query_job_synchronous():
    spec_dict = {
        "name": "test-sync-job",
        "description": "Integration test job for server",
        "slices": [
            {
                "slice_id": "slice-1",
                "target_files": ["server_test_module.py"],
                "dependencies": [],
                "contract": {
                    "module_path": "server_test_module.py",
                    "expected_classes": ["ServerService"],
                    "expected_functions": ["handle_request"],
                    "signatures": {},
                    "docstring_requirements": [],
                },
                "instructions": "Create a dummy ServerService class",
            }
        ],
    }

    # Submit synchronous job
    submit_res = client.post(
        "/api/v1/jobs",
        json={
            "workload_spec": spec_dict,
            "provider_name": "mock",
            "async_mode": False,
            "concurrency": 2,
        },
    )
    assert submit_res.status_code == 202
    job_data = submit_res.json()
    assert "job_id" in job_data
    assert job_data["status"] == JobStatus.COMPLETED.value
    assert job_data["name"] == "test-sync-job"
    assert job_data["metrics"] is not None

    # Query job details
    get_res = client.get(f"/api/v1/jobs/{job_data['job_id']}")
    assert get_res.status_code == 200
    assert get_res.json()["job_id"] == job_data["job_id"]


def test_list_jobs():
    response = client.get("/api/v1/jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert isinstance(jobs, list)
    assert len(jobs) >= 1


def test_cancel_non_existent_job():
    response = client.post("/api/v1/jobs/job-non-existent/cancel")
    assert response.status_code == 404


def test_stream_job_events_not_found():
    response = client.get("/api/v1/jobs/job-fake-id/stream")
    assert response.status_code == 404
