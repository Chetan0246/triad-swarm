# ⚡ Triad Swarm v0.3.0

> **A minimal-agent, maximum-throughput, token-optimal multi-agent swarm framework for software engineering.**
> Transform natural language prompts or issue descriptions into verified, tested multi-file pull requests at minimum token cost.

[![CI](https://github.com/Chetan0246/triad-swarm/actions/workflows/ci.yml/badge.svg)](https://github.com/Chetan0246/triad-swarm/actions)
[![Live Dashboard](https://img.shields.io/badge/live_dashboard-GitHub_Pages-blueviolet.svg)](https://chetan0246.github.io/triad-swarm/)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests Passing](https://img.shields.io/badge/tests-72%20passed-brightgreen.svg)](https://github.com/Chetan0246/triad-swarm/actions)
[![Token Savings](https://img.shields.io/badge/token%20savings-64.5%25-brightgreen.svg)](#-empirical-benchmark-results)
[![Verification Cost](https://img.shields.io/badge/verification%20tokens-0%20tokens-cyan.svg)](#-the-core-philosophy-why-most-swarms-fail)

[**Read Technical Research Whitepaper**](docs/research_whitepaper.md) • [**Launch Live Visualizer**](https://chetan0246.github.io/triad-swarm/) • [**Product Blueprint**](docs/product_blueprint.md)

```text
       ┌────────────────────────────────────────────────────────┐
       │   triad new "Add async Redis rate limiter with token   │
       │           bucket algorithm & sliding window fallback"  │
       └───────────────────────────┬────────────────────────────┘
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │  Spec Generator Agent │  (Prompt -> WorkloadSpec)
                       │ + AST Repo-Mapper     │  (Injects Existing Codebase AST)
                       └───────────┬───────────┘
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │    Architect Agent    │  (High-Reasoning Model Arbitrage)
                       │ (Contract-First AST)  │  (e.g., Claude 3.7 / Gemini Pro)
                       └───────────┬───────────┘
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │ Reactive DAG Scheduler│  (Topological Waves + Async Events)
                       └───────────┬───────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │ Wave 1 (Root Slices)   │ Concurrency Semaphore  │
          ▼                        ▼                        ▼
 ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
 │ Worker Agent 1  │      │ Worker Agent 2  │      │ Worker Agent K  │
 │ (Fast/Ollama LLM│      │ (Fast/Ollama LLM│      │ (Fast/Ollama LLM│
 │  ~600 tokens)   │      │  ~600 tokens)   │      │  ~600 tokens)   │
 └────────┬────────┘      └────────┬────────┘      └────────┬────────┘
          │                        │                        │
          ▼                        ▼                        ▼
 ┌───────────────────────────────────────────────────────────────────┐
 │              Deterministic Verifier Gate (0 TOKENS)               │
 │       AST Contract Check + Subprocess PyTest/Vitest Acceptance    │
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

## 🚀 What's New in v0.3.0

- ✨ **Zero-JSON Prompt-to-Code (`triad new "<feature>"`):** Pass a natural language prompt; Triad Swarm automatically synthesizes acceptance criteria, modular task slices, and interface contracts, then builds verified code autonomously.
- 🐟 **TinyFish Web Search & Fetch Tool:** Integrated web intelligence via the TinyFish API (`tinyfish.ai` / `agent.tinyfish.ai`), backed by automatic **100% free zero-key fallbacks** for offline documentation retrieval.
- 🔀 **Asymmetric Model Routing:** Economic and capability arbitrage—run a heavy reasoning model (Claude 3.7 Sonnet, Gemini Pro, GPT-4o) for the single Architect step, and lightweight models (Gemini Flash, GPT-4o-mini, or **local 100% free Ollama / vLLM**) for parallel Workers.
- 🗺️ **Brownfield AST Repo-Mapping (`triad repomap`):** Scans existing codebases and extracts class hierarchies, method signatures, and exported TypeScript types into a bounded, token-budgeted (<1,000 tokens) context block so new features seamlessly integrate.
- 🌐 **Polyglot Verification Gates:** Full support for TypeScript and JavaScript workloads with static contract verification and dynamic test runner integration (Vitest, Jest, Node test runner) with stack trace pruning.

---

## 🎯 The Core Philosophy: Why Most Swarms Fail

Traditional multi-agent frameworks (e.g., AutoGen, CrewAI, ChatDev) suffer from four crippling pathologies when applied to coding tasks:

1. **Role Bloat (Too Many Agents):** Creating 8–12 specialized personas (Product Manager, Planner, Code Reviewer, QA Engineer, SRE, Critic, Summarizer) introduces endless conversational chatter.
2. **Quadratic Token Inflation ($O(N^2)$):** Shared conversation histories force every agent to re-ingest past chat transcripts. As a task progresses, context windows balloon exponentially, inflating costs and polluting attention.
3. **Serial Bottlenecks:** Agents waiting in turn-based chat loops serialize execution, destroying the potential for parallel speedup.
4. **Fuzzy LLM-as-a-Judge Reviews:** Using an LLM Critic to review code consumes 2,000–5,000 tokens per evaluation while missing subtle syntax, signature, and logic errors.

### The Triad Swarm Solution

| Dimension | Traditional Chat Swarm | Triad Swarm v0.3.0 | Improvement |
| :--- | :--- | :--- | :--- |
| **Agent Roles** | 8–12 conversational personas | **2 core types** (1 Architect + $k$ homogeneous Workers) | **60–80% fewer roles** |
| **Execution Architecture** | Serial turn-taking ($T = \sum T_i$) | **Reactive DAG Waves** with async streaming ($T \approx \max T_i$) | **Up to $k\times$ parallel speedup** |
| **Token Cost** | $O(N^2)$ quadratic chat accumulation | **$O(1)$ isolated context** (~500–800 tokens/task) | **64.5% fewer total tokens** |
| **Verification Gate** | LLM Critic (2,000+ tokens/check) | **Deterministic AST + PyTest/Vitest (0 tokens)** | **100% LLM verification cost eliminated** |
| **Prompt-to-Code** | Manual YAML/JSON files required | **`triad new "<prompt>"` (Zero-JSON)** | **Instant natural language synthesis** |
| **Model Arbitrage** | One expensive model for all agents | **Asymmetric Model Router (Cloud + Local Ollama)** | **60%+ cost reduction via model arbitrage** |
| **Prompt Caching** | None (full network re-evaluation) | **Multi-tier exact semantic cache** (<1ms lookup) | **Up to 75% cached prompt discount** |
| **Self-Healing Tracebacks**| Raw verbose terminal dumps | **Intelligent Traceback Pruning** | **60–80% tokens saved on retries** |
| **Brownfield Codebases**| Hallucinates missing functions | **AST Repo-Mapping (<1,000 token context)** | **Imports verified real symbols** |
| **Web Research** | None / Heavy search agents | **TinyFish + Free Fallback Engine** | **Targeted doc lookups at 0 token waste** |

---

## ⚡ Quickstart

### 1. Installation

```bash
# Clone repository
git clone https://github.com/Chetan0246/triad-swarm.git
cd triad-swarm

# Install in virtualenv (using uv or pip)
pip install -e .

# Or run with Docker
docker build -t triad-swarm .
docker run --rm triad-swarm version
```

### 2. Natural Language Prompt-to-Code (`triad new`)

Build an entire multi-file tested feature from a single prompt:

```bash
# Synthesize specification and immediately run the swarm to generate code into ./out
triad new "Add an async Redis rate limiter with sliding window fallback" --run --output-dir ./out

# Or generate and inspect the formal workload JSON first
triad new "Add an async token bucket limiter" --out workload.json
```

### 3. Run with Asymmetric Model Routing (Cloud or Local Ollama)

Combine a high-reasoning Architect with fast, free local Workers:

```bash
# Cloud reasoning for Architect + Local Ollama for Workers (Zero API cost for workers!)
triad run workload.json \
  --architect-model gemini/gemini-3.8-flash \
  --worker-model ollama/qwen2.5-coder:7b \
  --concurrency 4 \
  --out ./dist
```

### 4. Brownfield Repo-Mapping (`triad repomap`)

Scan your codebase to extract AST symbols and inject them into the Architect:

```bash
# View codebase AST map and estimated token budget
triad repomap ./my_project

# Run a feature with existing codebase context injected
triad new "Add batch export endpoint to User model" --repo-map ./my_project --run
```

### 5. Web Search & Documentation Fetch (`triad search` & `triad fetch`)

Look up library documentation using TinyFish or zero-cost free search:

```bash
# Search web using TinyFish (or free fallback)
triad search "python asyncio priority queue best practices"

# Fetch clean markdown text from any web page
triad fetch "https://docs.pydantic.dev/latest/" --max-chars 3000
```

### 6. Full-Stack Web Apps & Everyday Automations

Triad Swarm is not limited to single algorithms—it synthesizes and verifies complete multi-tier applications:

- **Full-Stack Web Application ([examples/fullstack_app/](examples/fullstack_app/)):** Decomposes a full-stack request into SQLite Database Models → FastAPI REST API endpoints → Responsive Tailwind CSS UI dashboard, verified end-to-end with TestClient in 1.2s.
- **Everyday Automation & Scraping ([examples/automation_scraper/](examples/automation_scraper/)):** An automated data pipeline featuring robust HTTP fetchers, regex HTML item extraction, and dual HTML/Markdown report generation.

```bash
# Run the full-stack web application generation example
python examples/fullstack_app/run_fullstack.py

# Run the everyday web scraper & digest pipeline
python examples/automation_scraper/run_scraper.py
```

### 7. Interactive Visualizer Dashboard

```bash
triad dashboard
```
Opens the interactive dark-mode visualizer with animated DAG wave execution, token telemetry, and Gantt timeline charts.

---

## 📊 Empirical Benchmark Results

Benchmarked on an end-to-end Telemetry & Analytics Pipeline (Storage layer, Windowed percentiles, Alerting evaluator, Exporter payload):

```text
               🏆 Swarm Architecture Benchmark Comparison
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃ Dimension              ┃ Naive Chat Swarm     ┃ Triad Swarm v0.3.0 ┃ Advantage / Delta  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│ Agent Roles Required   │ 8 (Worker + Critic)  │ 2 (Architect+Work) │ 75% fewer roles    │
│ Wall-Clock Time        │ 8.42 s (Sequential)  │ 2.05 s (Parallel)  │ 75.7% faster (4.1x)│
│ Total Tokens Consumed  │ 8,460 tokens         │ 3,001 tokens       │ 64.5% tokens saved │
│ Verification Cost      │ 2,400 tokens (Critic)│ 0 tokens (CPU AST) │ 100% cost cut      │
│ Success Ratio          │ 75% (Drift prone)    │ 100% (Guaranteed)  │ Deterministic TDD  │
│ Estimated Run Cost     │ $0.00254             │ $0.00085           │ 66.5% cost saved   │
└────────────────────────┴──────────────────────┴────────────────────┴────────────────────┘
```

---

## 🛠️ CLI Reference

| Command | Description | Example |
| :--- | :--- | :--- |
| `triad new "<prompt>"` | Synthesizes WorkloadSpec and optionally builds code | `triad new "Add async cache" --run` |
| `triad run <spec.json>` | Executes workload DAG with isolated parallel workers | `triad run workload.json --concurrency 4` |
| `triad serve` | Launches production REST & SSE daemon with metrics | `triad serve --host 0.0.0.0 --port 8000` |
| `triad status <job_id>` | Queries status and metrics of a running/completed job | `triad status job-48efeadcbfe0` |
| `triad repomap [path]` | Extracts bounded AST symbols (<1,000 tokens) | `triad repomap triad/core` |
| `triad search "<query>"`| Searches web using TinyFish or free fallback | `triad search "FastAPI middleware"` |
| `triad fetch "<url>"` | Fetches and cleans web content to markdown | `triad fetch "https://example.com"` |
| `triad graph <spec.json>`| Visualizes topological dependency waves | `triad graph workload.json --mermaid` |
| `triad verify <file>` | Zero-token static CI/CD contract validation gate | `triad verify module.py -c contract.json` |
| `triad benchmark` | Runs reproducible side-by-side head-to-head benchmark| `triad benchmark` |
| `triad dashboard` | Launches interactive dark-mode architecture visualizer| `triad dashboard` |
| `triad version` | Displays framework version | `triad version` |

---

## 🏭 Production Deployment & Cloud Architecture

Triad Swarm is built for production operations, providing out-of-the-box infrastructure for Kubernetes, Docker Compose, Prometheus observability, and hardened process isolation.

### 1. Production Daemon & REST API (`triad serve`)

Launch Triad Swarm as a high-concurrency microservice daemon:
```bash
triad serve --host 0.0.0.0 --port 8000 --log-format json
```

Key endpoints:
- `POST /api/v1/jobs` - Submit asynchronous or synchronous multi-agent workloads.
- `GET /api/v1/jobs/{job_id}` - Query job execution lifecycle, token metrics, and generated artifacts.
- `GET /api/v1/jobs/{job_id}/stream` - Real-time Server-Sent Events (SSE) streaming execution events.
- `POST /api/v1/jobs/{job_id}/cancel` - Gracefully cancel active jobs.
- `GET /healthz` & `GET /readyz` - Kubernetes liveness and readiness probes.
- `GET /metrics` - Prometheus OpenMetrics exposition.

### 2. Docker Compose Production Stack

Deploy Triad Swarm alongside Prometheus and pre-configured Grafana dashboards:
```bash
docker compose -f docker-compose.prod.yml up -d
```
- **Triad Engine API:** `http://localhost:8000`
- **Prometheus Metrics:** `http://localhost:9090`
- **Grafana Dashboard:** `http://localhost:3000` (User: `admin`, Pass: `triadadmin`)

### 3. Kubernetes Deployment (`k8s/`)

Deploy to any Kubernetes cluster with security hardening, horizontal pod autoscaling, and zero-downtime rolling updates:
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml.template
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/ingress.yaml
```

**Security Context & Resource Limits:**
- Unprivileged non-root user (`UID 10001: triad`).
- All Linux capabilities dropped (`drop: [ALL]`).
- Strict POSIX process limits: Memory ceiling via `RLIMIT_AS`, CPU time limits via `RLIMIT_CPU`, and configurable outbound network gating to prevent data exfiltration.

### 4. Enterprise Observability & Structured Logging

Triad Swarm emits single-line JSON logs formatted for Datadog, Grafana Loki, AWS CloudWatch, and Vector with automated correlation IDs:
```json
{
  "timestamp": "2026-11-21T15:02:12Z",
  "level": "INFO",
  "logger": "triad.server.api",
  "message": "Job job-48efeadcbfe0 completed in 2.05s",
  "job_id": "job-48efeadcbfe0",
  "metrics": { "total_tokens": 3001, "zero_token_verifications": 4 }
}
```

---

## 🧪 Running Tests

```bash
pytest -v
# 72 unit, integration, server, and security tests passing in ~40s
```

---

## 📄 License

MIT License. Designed and engineered for maximum developer speed, reliability, and token efficiency.
