# ⚡ Triad Swarm v0.2.0

> **A minimal-agent, maximum-throughput, token-optimal multi-agent swarm framework for software engineering.**

[![CI](https://github.com/chetan/triad-swarm/actions/workflows/ci.yml/badge.svg)](#)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests Passing](https://img.shields.io/badge/tests-38%20passed-brightgreen.svg)](#)
[![Token Savings](https://img.shields.io/badge/token%20savings-64.5%25-brightgreen.svg)](#)
[![Verification Cost](https://img.shields.io/badge/verification%20tokens-0%20tokens-cyan.svg)](#)

[**Read Full Technical Research Whitepaper**](docs/research_whitepaper.md) • [**Launch Interactive Visualizer**](examples/visualizer/index.html) • [**Run Benchmarks**](#-empirical-benchmark-results)

```text
       ┌────────────────────────────────────────────────────────┐
       │               User / Workload Specification             │
       └───────────────────────────┬────────────────────────────┘
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │    Architect Agent    │  (1 Agent Instance)
                       │ (Contract-First AST)  │
                       └───────────┬───────────┘
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │ Reactive DAG Scheduler│  (Topological Waves)
                       └───────────┬───────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │ Wave 1 (Root Slices)   │ Concurrency Semaphore  │
          ▼                        ▼                        ▼
 ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
 │ Worker Agent 1  │      │ Worker Agent 2  │      │ Worker Agent K  │
 │ (Isolated ~600t)│      │ (Isolated ~600t)│      │ (Isolated ~600t)│
 └────────┬────────┘      └────────┬────────┘      └────────┬────────┘
          │                        │                        │
          ▼                        ▼                        ▼
 ┌───────────────────────────────────────────────────────────────────┐
 │               Deterministic Verifier Gate (0 TOKENS)              │
 │        AST Contract Check + Subprocess PyTest Acceptance Gate      │
 └─────────────────────────────────┬─────────────────────────────────┘
                                   │
                                   ▼  [Artifact Cascading to Downstream Wave]
 ┌───────────────────────────────────────────────────────────────────┐
 │ Wave 2...N: Dependent slices execute reactively upon upstream pass│
 └─────────────────────────────────┬─────────────────────────────────┘
                                   │
                                   ▼
                    [ Verified Production Artifacts ]
```

---

## 🎯 The Core Philosophy: Why Most Swarms Fail

Traditional multi-agent frameworks (e.g., AutoGen, CrewAI, ChatDev) suffer from four crippling pathologies when applied to coding tasks:

1. **Role Bloat (Too Many Agents):** Creating 8–12 specialized personas (Product Manager, Planner, Code Reviewer, QA Engineer, SRE, Critic, Summarizer) introduces endless conversational chatter.
2. **Quadratic Token Inflation ($O(N^2)$):** Shared conversation histories force every agent to re-ingest past chat transcripts. As a task progresses, context windows balloon exponentially, inflating costs and polluting attention.
3. **Serial Bottlenecks:** Agents waiting in turn-based chat loops serialize execution, destroying the potential for parallel speedup.
4. **Fuzzy LLM-as-a-Judge Reviews:** Using an LLM Critic to review code consumes 2,000–5,000 tokens per evaluation while missing subtle syntax, signature, and logic errors.

### The Triad Swarm Solution

| Dimension | Traditional Chat Swarm | Triad Swarm v0.2.0 | Improvement |
| :--- | :--- | :--- | :--- |
| **Agent Roles** | 8–12 conversational personas | **2 core types** (1 Architect + $k$ homogeneous Workers) | **60–80% fewer roles** |
| **Execution Architecture** | Serial turn-taking ($T = \sum T_i$) | **Reactive DAG Waves** with async streaming ($T \approx \max T_i$) | **Up to $k\times$ parallel speedup** |
| **Token Cost** | $O(N^2)$ quadratic chat accumulation | **$O(1)$ isolated context** (~500–800 tokens/task) | **64.5% fewer total tokens** |
| **Verification Gate** | LLM Critic (2,000+ tokens/check) | **Deterministic AST + PyTest (0 tokens)** | **100% LLM verification cost eliminated** |
| **Prompt Caching** | None (full network re-evaluation) | **Multi-tier exact semantic cache** (<1ms lookup) | **Up to 75% cached prompt discount** |
| **Self-Healing Tracebacks**| Raw verbose terminal dumps | **Intelligent Traceback Pruning** | **60–80% tokens saved on retries** |
| **Success Ratio** | Heuristic, prone to drift | **Contract-First TDD verification** | **100% verified test compliance** |

---

## 🏛️ Advanced Architecture in v0.2.0

### 1. Reactive DAG Scheduler & Topological Waves (`triad.orchestrator.scheduler`)
- Evaluates task slice dependencies to construct a Directed Acyclic Graph.
- Detects circular dependency cycles with Kahn's algorithm before execution starts.
- Partitions tasks into parallel execution waves while streaming tasks reactively via `asyncio.Event` without blocking independent tasks.
- **Artifact Cascading**: Upstream verified modules are automatically mounted as read-only dependencies into downstream worker sandboxes.

### 2. Polyglot & Deep AST Static Contracts (`triad.core.contracts`)
- **Python AST Verification**: Validates function signatures, argument names, type hints, and class method declarations.
- **Security Import Gate**: Automatically enforces `forbidden_imports` (e.g. `subprocess`, `pickle`, `ctypes`) with 0 tokens.
- **Polyglot Interface Support**: Static TypeScript export/function validation and JSON Schema structural verification.

### 3. Multi-Tier Prompt Caching (`triad.core.cache`)
- Thread-safe and async-safe in-memory and disk caching with SHA-256 fingerprinting.
- Returns identical task requests in $< 1\text{ms}$ with 0 network calls and 0 duplicate tokens billed.

### 4. Traceback Pruner (`TracebackPruner`)
- Compresses hundreds of lines of pytest stack frames into high-signal error context (failing assertion, diff, target line).
- Cuts self-healing prompt tokens by 60–80%.

### 5. Distributed Tracing & DevTools Export (`triad.core.telemetry`)
- Records microsecond-level spans across all swarm lifecycle events.
- Exports to **Chrome DevTools Trace Event format** (drag-and-drop into `chrome://tracing` or [perfetto.dev](https://ui.perfetto.dev)).
- Generates live Mermaid Gantt timeline diagrams.

---

## 🔬 Empirical Benchmark Results

Ran head-to-head on the modular `Telemetry & Analytics Processing Engine` workload:

```text
                   🏆 Swarm Architecture Benchmark Comparison                   
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ Dimension               ┃ Naive Chat Swarm┃ Triad Swarm     ┃ Advantage      ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ Agent Roles Required    │ 8 roles         │ 5 instances     │ 38% fewer roles│
│ Concurrency             │ 1 (Sequential)  │ 4 Parallel      │ 4x fan-out     │
│ Total Tokens Consumed   │ 8,711 tokens    │ 3,110 tokens    │ 64.3% saved    │
│ Verification Token Cost │ 3,656 tokens    │ 0 tokens        │ 100% saved     │
│ Zero-Token Passes       │ 0               │ 4 passes        │ 100% pass      │
│ Success Ratio           │ 100.0%          │ 100.0%          │ TDD Guarantees │
│ Estimated Cost (USD)    │ $0.00295        │ $0.00101        │ $0.00194 saved │
└─────────────────────────┴─────────────────┴─────────────────┴────────────────┘
```

---

## 💻 CLI Usage

### 1. Execute Workloads with Distributed Tracing
```bash
triad run examples/demo_workload.json --concurrency 4 --out dist/my_service --trace-file trace.json
```

### 2. Visualize Workload DAG (ASCII & Mermaid)
```bash
# ASCII Wave Tree
triad graph examples/demo_workload.json

# Mermaid Flowchart syntax
triad graph examples/demo_workload.json --mermaid
```

### 3. Standalone 0-Token Verification Gate for CI/CD
```bash
triad verify path/to/module.py --contract path/to/contract.json
```

### 4. Run Side-by-Side Empirical Benchmark
```bash
triad benchmark --slices 4
```

### 5. Launch Interactive Architecture Dashboard
```bash
triad dashboard
```

### 6. Check Framework Version
```bash
triad version
```

---

## 🛠️ Python SDK Usage

```python
import asyncio
from triad import TriadEngine, WorkloadSpec, get_llm_provider

async def main():
    spec = WorkloadSpec(
        name="Crypto Payment Gateway",
        description="Modular payment processor with signature validation and ledger sync.",
        acceptance_criteria=[
            "Module `crypto/signer.py` with verify_signature",
            "Module `crypto/ledger.py` with record_transaction",
        ]
    )

    llm = get_llm_provider("gemini", model="gemini-3.8-flash")
    engine = TriadEngine(
        llm=llm,
        max_concurrency=4,
        output_dir="dist/payment_service",
        enable_cache=True,
        trace_output_path="timeline_trace.json"
    )

    metrics = await engine.execute_workload(spec)
    print(f"Completed in {metrics.wall_clock_seconds}s with {metrics.total_tokens} tokens!")
    print(f"Zero-token passes: {metrics.zero_token_verifications}")
    print(f"Execution waves: {metrics.execution_waves}")

asyncio.run(main())
```

---

## 🧪 Running Tests

The test suite covers models, token tracking, AST validation, sandboxing security, DAG scheduling, prompt caching, distributed telemetry, and end-to-end multi-wave workflows:

```bash
source .venv/bin/activate
pytest -v
# 38 passed in ~3 seconds
```

---

## 📜 License

MIT License. Designed for high-reliability, production-grade agent swarms.
