# ⚡ Triad Swarm

> **A minimal-agent, maximum-throughput, token-optimal multi-agent swarm framework for software engineering.**

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
          ┌────────────────────────┼────────────────────────┐
          │ Parallel Fan-Out       │ Concurrency Semaphore  │
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

| Dimension | Traditional Chat Swarm | Triad Swarm | Improvement |
| :--- | :--- | :--- | :--- |
| **Agent Roles** | 8–12 conversational personas | **2 core types** (1 Architect + $k$ homogeneous Workers) | **60–80% fewer roles** |
| **Execution Time** | Serial turn-taking ($T = \sum T_i$) | **Async parallel fan-out** ($T \approx \max T_i$) | **Up to $k\times$ parallel speedup** |
| **Token Cost** | $O(N^2)$ quadratic chat accumulation | **$O(1)$ isolated context** (~500–800 tokens/task) | **64.5% fewer total tokens** |
| **Verification Gate** | LLM Critic (2,000+ tokens/check) | **Deterministic AST + PyTest (0 tokens)** | **100% LLM verification cost eliminated** |
| **Success Ratio** | Heuristic, prone to drift | **Contract-First TDD verification** | **100% verified test compliance** |

---

## 🏛️ The Triad Architecture

The framework is structured into three pillars:

### 1. The Architect Agent (1 Instance)
- Takes a high-level `WorkloadSpec`.
- Decomposes the workload into $N$ **disjoint, decoupled `TaskSlice` objects**.
- Declares a formal `InterfaceContract` for each slice (module paths, exported symbols, type signatures, logical invariants).
- Generates deterministic **acceptance tests** for each slice.
- Because slices are decoupled, workers implement them concurrently with zero cross-worker chatter.

### 2. The Worker Pool ($k$ Parallel Homogeneous Workers)
- Minimalist, Pi-style workers running in **isolated sandboxes**.
- Each worker only sees its specific slice, interface contract, and target files.
- Operates on a lean 4-tool primitive set: `read_file`, `write_file`, `edit_file`, `exec_command`.
- Ultra-low context footprint (~400–800 tokens max).

### 3. The Deterministic Verifier Gate (0 Tokens on Pass)
- Executes entirely on the local CPU; **zero LLM tokens consumed**.
- **Phase 1: AST Contract Validation:** Parses source code into Python AST to mathematically verify that all exported symbols and signatures exist.
- **Phase 2: PyTest Test Runner:** Executes the acceptance tests in the isolated sandbox.
- **Self-Healing Loop:** If and only if a deterministic test fails, the verifier extracts a concise failure traceback and prompts the worker for a targeted fix (max 2 attempts).

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
│ Total Tokens Consumed   │ 8,711 tokens    │ 3,094 tokens    │ 64.5% saved    │
│ Verification Token Cost │ 3,656 tokens    │ 0 tokens        │ 100% saved     │
│ Zero-Token Passes       │ 0               │ 4 passes        │ 100% pass      │
│ Success Ratio           │ 100.0%          │ 100.0%          │ TDD Guarantees │
│ Estimated Cost (USD)    │ $0.00295        │ $0.00101        │ $0.00194 saved │
└─────────────────────────┴─────────────────┴─────────────────┴────────────────┘
```

---

## 🚀 Installation & Quickstart

### Prerequisites
- Python 3.10+ (tested on Python 3.13 / 3.14)
- [`uv`](https://github.com/astral-sh/uv) (recommended) or standard `pip`

### Setup
```bash
git clone https://github.com/your-username/triad-swarm.git
cd triad-swarm

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate
uv pip install -e .
```

### Configure API Keys (Optional)
Triad supports Gemini, OpenAI, or an offline deterministic Mock provider:
```bash
# For Google Gemini (Flash / Pro):
export GEMINI_API_KEY="your-gemini-key"

# For OpenAI (GPT-4o / GPT-4o-mini):
export OPENAI_API_KEY="your-openai-key"

# Or run fully offline without any API keys:
export TRIAD_LLM_PROVIDER="mock"
```

---

## 💻 CLI Usage

### 1. Run the Head-to-Head Benchmark
```bash
triad benchmark --slices 4
```

### 2. Execute a Custom Workload
```bash
triad run examples/demo_workload.json --concurrency 4 --out dist/my_service
```

### 3. Check Framework Version
```bash
triad version
```

---

## 🛠️ Python SDK Usage

```python
import asyncio
from triad import TriadEngine, WorkloadSpec, get_llm_provider

async def main():
    # 1. Define Workload
    spec = WorkloadSpec(
        name="Crypto Payment Gateway",
        description="Modular payment processor with signature validation and ledger sync.",
        acceptance_criteria=[
            "Module `crypto/signer.py` with verify_signature",
            "Module `crypto/ledger.py` with record_transaction",
        ]
    )

    # 2. Initialize Engine
    llm = get_llm_provider("gemini")
    engine = TriadEngine(llm=llm, max_concurrency=4, output_dir="dist/payment_service")

    # 3. Execute Swarm
    metrics = await engine.execute_workload(spec)
    print(f"Completed in {metrics.wall_clock_seconds}s with {metrics.total_tokens} tokens!")
    print(f"Zero-token passes: {metrics.zero_token_verifications}")

asyncio.run(main())
```

---

## 📁 Repository Structure

```text
triad-swarm/
├── pyproject.toml               # Package metadata and dependencies
├── README.md                    # Architecture and documentation
├── triad/
│   ├── __init__.py              # Library exports
│   ├── cli.py                   # Rich-powered terminal interface
│   ├── core/
│   │   ├── models.py            # Pydantic schemas (TaskSlice, Contract, Metrics)
│   │   ├── token_tracker.py     # Thread-safe token & cost accountant
│   │   ├── llm.py               # Gemini, OpenAI & Mock LLM providers
│   │   ├── sandbox.py           # Isolated workspace sandbox & path security
│   │   └── contracts.py         # AST-based 0-token interface validator
│   ├── agents/
│   │   ├── base.py              # Base agent harness
│   │   ├── architect.py         # Contract-first decomposition agent
│   │   ├── worker.py            # Context-isolated implementation agent
│   │   └── verifier.py          # Deterministic 0-token PyTest gate
│   └── orchestrator/
│       ├── engine.py            # Async parallel semaphore orchestrator
│       └── naive_engine.py      # Monolithic chat baseline for A/B testing
├── examples/
│   ├── demo_workload.json       # Telemetry microservice specification
│   ├── demo_workload.py         # Executable demonstration script
│   └── benchmark_comparison.py  # Standalone A/B benchmark runner
└── tests/                       # 22 automated unit and integration tests
```

---

## 🧪 Running Tests

The test suite covers models, token tracking, AST validation, sandboxing security, parallel orchestration, and regression benchmarks:

```bash
uv run pytest -v
```

---

## 📜 License

MIT License. Designed for high-reliability, production-grade agent swarms.
