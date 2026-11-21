# 🚀 Triad Swarm: Product Hunt Launch Operations Guide & Kit

Everything you need to launch **Triad Swarm** on [Product Hunt](https://www.producthunt.com/posts/new) and achieve a top placement.

---

## 📋 1. Product Hunt Submission Form Details

### Basic Info
- **Product Name:** `Triad Swarm`
- **Tagline (56 chars - Max 60):**  
  `Minimal-agent, token-optimal multi-agent coding swarm`  
  *(Alternative Tagline: `Build software with AI swarms at 64% fewer tokens`)*
- **Topics/Tags:** `Developer Tools`, `Artificial Intelligence`, `Open Source`, `GitHub`, `Productivity`
- **Pricing:** `Free / Open Source (MIT License)`
- **Links:**
  - **Website / Live Demo:** `https://chetan0246.github.io/triad-swarm/`
  - **GitHub Repository:** `https://github.com/Chetan0246/triad-swarm`
  - **Releases:** `https://github.com/Chetan0246/triad-swarm/releases/tag/v0.4.0`

### Short Description (Max 260 characters)
> *A minimal-agent framework that cuts multi-agent token waste by 64.5%. Replaces conversational chat bloat and hallucinated LLM reviews with a 2-agent reactive DAG hierarchy and 0-token deterministic compiler verification gates.*

### Detailed Description (for the PH Post Body)
```markdown
Most multi-agent coding swarms (CrewAI, AutoGen, ChatDev) suffer from four crippling bottlenecks:
1. 💸 **The Token Explosion:** 8–12 agent personas chatting back and forth inflate context exponentially ($O(N^2)$), burning thousands of tokens on pleasantries before writing code.
2. 🤥 **Hallucinated LLM Critics:** Asking another LLM prompt "does this code look good?" wastes 2,000+ tokens and still misses syntax and runtime errors.
3. 🐌 **Serial Slowness:** Turn-based chat loops serialize tasks that should run in parallel.
4. 🏗️ **Brownfield Blindness:** Pasting entire codebases blows up token limits and causes hallucinated imports.

**Triad Swarm changes the paradigm from conversational chat to deterministic compiler-verified orchestration:**

⚡ **Core Breakthroughs:**
- **Minimal 2-Agent Hierarchy:** 1 Architect Agent (contract design) + $k$ homogeneous Workers (isolated sandboxes). No redundant personas.
- **0-Token Verifier Gate:** Replaces LLM critics with CPU-native AST parsing and isolated pytest/vitest runners. Successful verifications consume **exactly 0 LLM tokens**.
- **Reactive Topological DAG Waves:** Parallel async fan-out with artifact cascading across dependencies (delivering up to 4.1x parallel speedup).
- **Asymmetric Model Arbitrage:** Route frontier reasoning models (Claude 3.7 Sonnet / DeepSeek R1 / Gemini Pro) to the Architect, and fast local models (Ollama Qwen 2.5 Coder / DeepSeek Flash) to Workers for a 60%+ cost cut.
- **Brownfield AST Repo-Mapping:** Ingests existing codebases in under 1,000 tokens.
- **Enterprise-Ready:** Includes a production FastAPI REST/SSE daemon, Kubernetes manifests with HPA, and Docker Compose with Prometheus & Grafana.

100% Free & Open Source under the MIT License.
```

---

## 💬 2. First Maker Comment (Post Immediately Upon Going Live)

Post this as the very first comment on your launch page:

```markdown
Hey Product Hunt! 👋 I'm Chetan, creator of Triad Swarm.

Over the past year, multi-agent frameworks exploded in popularity. Everyone was building swarms with 8 to 12 personas—a "Product Manager agent", "Coder agent", "Reviewer agent", "QA agent", and "SRE agent".

When I tried using them for real engineering, I hit the same frustrating reality:
1. **They burn tokens like crazy.** A 4-step task easily burns 10,000+ tokens just passing global chat transcripts back and forth ($O(N^2)$ context inflation).
2. **LLM critics hallucinate.** Asking an LLM to review code costs 2,000–5,000 tokens per evaluation while missing obvious syntax errors or type mismatches.
3. **Everything is serialized.** Agents wait in turn-taking conversational loops instead of parallelizing work.

I decided to take a step back and build **Triad Swarm** from first principles:

⚡ **What makes Triad Swarm fundamentally different?**
- **We collapsed 8 personas into 2 agent classes:** 1 Architect + $k$ parallel Workers.
- **0-Token Deterministic Verification:** We killed the "LLM Critic". Code is verified on the local CPU via AST syntax checks, schema contracts, and sandboxed test execution. It costs $0 and 0 tokens.
- **Reactive DAG Waves:** Tasks are resolved into a dependency graph using Kahn’s algorithm. Non-dependent tasks execute concurrently in parallel waves (delivering 4.1x speedup).
- **Model Arbitrage:** Pair a smart frontier model (Claude 3.7 / Gemini Pro) for architecture with 100% free local models (Ollama Qwen 2.5 Coder / vLLM) for workers.
- **Zero-JSON Prompt-to-Code:** Run `triad new "Add async rate limiter with token bucket"` and the swarm autonomously designs the contract, parallelizes the build, and verifies it.

You can try the interactive dark-mode dashboard right now in your browser without installing anything:
👉 **Live Visualizer:** https://chetan0246.github.io/triad-swarm/

Or install via pip/uv:
```bash
pip install triad-swarm
triad new "Build an async priority task queue in Python" --run
```

The project is 100% open source (MIT), tested with 80 automated unit & integration tests, and includes production Kubernetes & Docker Compose stacks.

I'd love to hear your feedback, thoughts on the architecture, and what features you’d like to see next! 🚀
```

---

## 🙋 3. Maker Q&A Playbook (Anticipated Community Questions)

Prepare these exact responses to engage with Hunters in the comments:

### Q1: "How is this different from Devin, Cursor, or Claude Code?"
> **Response:**  
> *"Great question! Devin and Claude Code are single-agent or monolithic chat agents that interact iteratively with a terminal. While great for linear workflows, they don't parallelize across multi-file dependencies and carry huge accumulating context histories.  
> Triad Swarm is an open-source multi-agent orchestration framework: it decomposes complex features into a Directed Acyclic Graph (DAG) and executes modular task slices concurrently in isolated sandboxes. It also introduces 0-token deterministic verification gates, eliminating hallucinated code reviews."*

### Q2: "Can I use local models with Ollama / vLLM?"
> **Response:**  
> *"Yes, 100%! Local model support is a first-class feature. You can run:  
> `triad new "Build user CRUD API" --worker-model ollama/qwen2.5-coder:7b --run`  
> We recommend Asymmetric Model Routing: use a cloud frontier model (Claude or Gemini) for the single Architect step, and your local Ollama instance for the Workers. This gives you high architectural reasoning at $0 cost for the actual code generation."*

### Q3: "What programming languages does Triad Swarm support?"
> **Response:**  
> *"Triad Swarm supports Python, TypeScript, JavaScript, HTML5/CSS3 (Tailwind), JSON schemas, and POSIX shell scripts out-of-the-box. Our polyglot verification engine checks AST contracts, balanced DOM tags, and runs either pytest, vitest, or Node native test runners depending on the target language."*

### Q4: "How does 0-token verification work? What if the code has runtime bugs?"
> **Response:**  
> *"Traditional swarms send code back to an LLM prompt: 'Does this code fulfill the requirements?'. That burns thousands of tokens and often hallucinates approvals.  
> In Triad Swarm, the Architect generates an explicit InterfaceContract (required symbols, signatures, and acceptance tests). Verification runs on the local CPU inside an isolated sandbox using AST parsers and test runners (pytest/vitest). If the tests pass and symbols match, it passes with 0 tokens. If tests fail, our traceback pruner extracts only the failing assertion, saving 70% of tokens on self-healing retries."*

---

## 🎨 4. Product Hunt Gallery Slides

We have generated pixel-perfect 16:9 dark-mode visual slides for the gallery in [`docs/product_hunt/gallery.html`](file:///home/chetan/triad-swarm/docs/product_hunt/gallery.html).

### Recommended Slide Order:
1. **Slide 1 (Hero Thumbnail):** Triad Swarm headline, key badges (64.5% token savings, 0-token verifier, 4.1x speedup).
2. **Slide 2 (The Architecture):** Comparison diagram contrasting traditional 10-agent chat bloat vs Triad Swarm's 2-agent DAG waves.
3. **Slide 3 (Empirical Benchmarks):** Verified benchmark scorecard showing token reduction, latency speedup, and deterministic reliability.
4. **Slide 4 (Enterprise Production Stack):** Architecture diagram showing `triad serve`, FastAPI REST & SSE daemon, Prometheus metrics, and Grafana dashboard.
5. **Slide 5 (Polyglot & Full-Stack):** Showcase of multi-tier app generation (FastAPI backend + SQLite + Tailwind UI dashboard).
6. **Slide 6 (Zero-JSON CLI):** Terminal walkthrough of `triad new "<feature>" --run`.

> [!TIP]
> Open [`docs/product_hunt/gallery.html`](file:///home/chetan/triad-swarm/docs/product_hunt/gallery.html) in your browser to view all 6 slides and capture high-resolution screenshots for the Product Hunt image uploader.

---

## 🗓️ 5. Launch Day Hour-by-Hour Execution Checklist

| Time (PST) | Action Item |
| :--- | :--- |
| **11:45 PM (Eve)** | Ensure GitHub repo is public, latest release is live, and GitHub Pages is responding. |
| **12:01 AM** | **Hit Publish on Product Hunt!** Immediately post your First Maker Comment. |
| **12:05 AM** | Post the **X / Twitter Thread** linking to the Product Hunt launch. |
| **12:15 AM** | Post the **LinkedIn Engineering Announcement**. |
| **12:30 AM** | Post **Show HN: Triad Swarm** on Hacker News. |
| **01:00 AM – 06:00 AM** | European & Asian morning traffic peaks. Reply to every PH comment within 10 minutes. |
| **06:00 AM** | US East Coast wakes up. Post technical breakdowns to `r/LocalLLaMA`, `r/Python`, and `r/MachineLearning`. |
| **09:00 AM** | US West Coast wakes up (peak tech activity). Share milestone update on X / Twitter (e.g. *"We just hit Top 5 on Product Hunt!"*). |
| **12:00 PM – 08:00 PM** | Maintain active engagement in the comments section. Highlight community suggestions. |
| **11:59 PM** | Voting closes. Post a thank-you note on Twitter/LinkedIn sharing the final rank and stats. |
