import json
import pytest
from triad.core.llm import MockLLMProvider
from triad.core.models import WorkloadSpec
from triad.orchestrator.engine import TriadEngine
from triad.orchestrator.naive_engine import NaiveBaselineEngine


@pytest.mark.asyncio
async def test_triad_engine_end_to_end():
    mock_llm = MockLLMProvider()

    # Architect returns 2 parallel slices
    architect_resp = json.dumps({
        "slices": [
            {
                "slice_id": "slice_auth",
                "title": "Auth Module",
                "description": "Implement verify_token",
                "target_files": ["auth.py"],
                "contract": {
                    "module_path": "auth.py",
                    "exported_symbols": ["verify_token"],
                    "signatures": {"verify_token": "def verify_token(token: str) -> bool"}
                },
                "acceptance_tests": {
                    "test_auth.py": "from auth import verify_token\ndef test_token(): assert verify_token('secret')"
                },
                "dependencies": []
            },
            {
                "slice_id": "slice_cache",
                "title": "Cache Module",
                "description": "Implement InMemoryCache",
                "target_files": ["cache.py"],
                "contract": {
                    "module_path": "cache.py",
                    "exported_symbols": ["InMemoryCache"],
                    "signatures": {}
                },
                "acceptance_tests": {
                    "test_cache.py": "from cache import InMemoryCache\ndef test_cache(): c = InMemoryCache(); assert c is not None"
                },
                "dependencies": []
            }
        ]
    })
    mock_llm.register_response("Workload Name", architect_resp)

    # Worker responses
    auth_worker_code = json.dumps({
        "files": {
            "auth.py": "def verify_token(token: str) -> bool:\n    return len(token) > 0\n"
        }
    })
    mock_llm.register_response("slice_auth", auth_worker_code)

    cache_worker_code = json.dumps({
        "files": {
            "cache.py": "class InMemoryCache:\n    def __init__(self):\n        self.items = {}\n"
        }
    })
    mock_llm.register_response("slice_cache", cache_worker_code)

    engine = TriadEngine(llm=mock_llm, max_concurrency=2)
    spec = WorkloadSpec(name="Auth & Cache Service", description="Two modular micro-components")

    metrics = await engine.execute_workload(spec)

    assert metrics.tasks_total == 2
    assert metrics.tasks_succeeded == 2
    assert metrics.success_rate == 100.0
    assert metrics.zero_token_verifications == 2
    assert metrics.llm_verifications == 0
    assert metrics.total_tokens > 0
