import json
import tempfile
from pathlib import Path
from triad.core.telemetry import SwarmTracer


def test_swarm_tracer_span_lifecycle():
    tracer = SwarmTracer(trace_name="test_trace")
    span = tracer.start_span("Decompose", phase="architect", agent_id="architect_01")
    assert span.status == "running"
    span.finish(status="success", metadata={"slices": 3})

    assert span.status == "success"
    assert span.duration_seconds >= 0.0
    assert span.metadata["slices"] == 3

    spans = tracer.get_spans()
    assert len(spans) == 1


def test_chrome_trace_and_mermaid_gantt_export():
    tracer = SwarmTracer(trace_name="benchmark_trace")
    s1 = tracer.start_span("Slice 1", phase="worker", agent_id="worker_1")
    s1.finish(status="success")
    s2 = tracer.start_span("Verification", phase="verifier", agent_id="verifier_1")
    s2.finish(status="success")

    # Mermaid Gantt
    gantt = tracer.generate_mermaid_gantt()
    assert "gantt" in gantt
    assert "Slice 1" in gantt
    assert "Verification" in gantt

    # Chrome Trace Event JSON
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "trace.json"
        tracer.export_chrome_trace(str(out_path))

        assert out_path.exists()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert "traceEvents" in data
        assert len(data["traceEvents"]) == 2
        assert data["traceEvents"][0]["name"] == "Slice 1"
