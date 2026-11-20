import json
import pytest
from triad.core.llm import MockLLMProvider
from triad.core.models import WorkloadSpec
from triad.orchestrator.engine import TriadEngine


@pytest.mark.asyncio
async def test_triad_dag_workload_artifact_cascading():
    """
    Test a 2-wave DAG workload:
    Wave 1: slice_db (generates db.py)
    Wave 2: slice_service (depends on slice_db, imports db and generates service.py)
    """
    mock_llm = MockLLMProvider()

    architect_resp = json.dumps({
        "slices": [
            {
                "slice_id": "slice_db",
                "title": "Database Engine",
                "description": "Implement DatabaseStore",
                "target_files": ["db.py"],
                "contract": {
                    "module_path": "db.py",
                    "exported_symbols": ["DatabaseStore"],
                    "signatures": {}
                },
                "acceptance_tests": {
                    "test_db.py": "from db import DatabaseStore\ndef test_db(): d = DatabaseStore(); assert d.get('k') is None"
                },
                "dependencies": []
            },
            {
                "slice_id": "slice_service",
                "title": "User Service",
                "description": "Implement UserService using DatabaseStore",
                "target_files": ["service.py"],
                "contract": {
                    "module_path": "service.py",
                    "exported_symbols": ["UserService"],
                    "signatures": {}
                },
                "acceptance_tests": {
                    "test_service.py": "from service import UserService\ndef test_svc(): s = UserService(); assert s.create_user('alice') == True"
                },
                "dependencies": ["slice_db"]  # Downstream dependency!
            }
        ]
    })
    mock_llm.register_response("Workload Name", architect_resp)

    # Worker for slice_db
    db_code = json.dumps({
        "files": {
            "db.py": (
                "class DatabaseStore:\n"
                "    def __init__(self):\n"
                "        self.data = {}\n"
                "    def get(self, k):\n"
                "        return self.data.get(k)\n"
                "    def set(self, k, v):\n"
                "        self.data[k] = v\n"
            )
        }
    })
    mock_llm.register_response("slice_db", db_code)

    # Worker for slice_service (imports db from upstream cascade!)
    service_code = json.dumps({
        "files": {
            "service.py": (
                "from db import DatabaseStore\n\n"
                "class UserService:\n"
                "    def __init__(self):\n"
                "        self.db = DatabaseStore()\n"
                "    def create_user(self, name: str) -> bool:\n"
                "        self.db.set(name, True)\n"
                "        return True\n"
            )
        }
    })
    mock_llm.register_response("slice_service", service_code)

    engine = TriadEngine(llm=mock_llm, max_concurrency=2)
    spec = WorkloadSpec(name="Layered DB & Service App", description="Two-tier layered architecture")

    metrics = await engine.execute_workload(spec)

    assert metrics.tasks_total == 2
    assert metrics.tasks_succeeded == 2
    assert metrics.success_rate == 100.0
    assert metrics.execution_waves == 2
    assert metrics.zero_token_verifications == 2
