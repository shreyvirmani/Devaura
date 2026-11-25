# Devaura — AI Software Repair & Maintenance Platform

> **Devaura — From failure to verified fix.**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![MCP Native](https://img.shields.io/badge/MCP-Native%20Host%20%26%20Client-orange.svg)](https://modelcontextprotocol.io/)

---

## 1. What is Devaura?

**Devaura** is an **MCP-native AI software maintenance and repair agent**. Rather than functioning as a conversational chatbot or a simple prompt wrapper, Devaura connects natively to code repositories, CI/CD systems, and issue trackers via the open **Model Context Protocol (MCP)** standard.

When an issue, test failure, or bug is reported, Devaura executes a rigorous automated lifecycle:

```text
Software Failure
      ↓
Context Collection (Issues, PRs, CI logs, Git history via MCP)
      ↓
Root Cause Analysis (AST, Code Search, Evidence-backed)
      ↓
Structured Repair Plan
      ↓
Human Approval Gate (Plan Sign-off)
      ↓
Patch Generation (Minimal unified diff)
      ↓
Isolated Execution (Ephemeral Sandbox)
      ↓
Testing & Verification (Pytest/Jest, Linter, Typecheck)
      ↓
Failure Analysis & Iteration (Max 3 repair loops)
      ↓
Independent Review
      ↓
Human Approval Gate (PR Sign-off)
      ↓
Pull Request Creation
```

---

## 2. Core Problem & Solution

### The Problem
Traditional AI coding assistants are reactive and unverified:
- They require developers to manually hunt down context, copy-paste stack traces, and guess affected files.
- They propose unchecked code changes directly to developers without running regression tests.
- They lack architectural awareness and make hallucinated claims without traceable evidence.
- They operate with unrestricted shell access or opaque single-vendor lock-in.

### The Devaura Solution
Devaura treats software maintenance as a closed-loop engineering process:
- **MCP-Native Host & Client**: Integrates seamlessly with GitHub MCP, native file and AST tools, and external MCP servers.
- **Evidence-Backed Root Cause Analysis**: Identifies exact failure locations with commit history, AST symbols, and test references.
- **Deterministic Sandboxing**: Executes patches and test suites inside isolated environments with memory/CPU bounds.
- **Strict Verification Protocol**: Verifies test pass rates, linting, and type checking, reporting structured status before touching Git remotes.
- **Human In The Loop**: Zero dangerous actions (pushing commits, opening PRs) can execute without explicit developer authorization.

---

## 3. High-Level Architecture

```mermaid
flowchart TD
    subgraph UI ["Devaura Web Dashboard (Next.js 15 / Tailwind)"]
        Dash["Dashboard & Health"]
        Repo["Repositories & Issues"]
        Workspace["Repair Studio & Diffs"]
        MCPHub["MCP Servers & Tools"]
    end

    subgraph Core ["Devaura Orchestrator (FastAPI / Python 3.12)"]
        FSM["Finite State Machine"]
        Investigator["Investigator Subsystem"]
        Planner["Repair Planner"]
        Repair["Repair Engine"]
        Verifier["Verification Engine"]
        Reviewer["Reviewer Subsystem"]
    end

    subgraph MCPLayer ["MCP Integration Layer"]
        Registry["MCPServerRegistry"]
        Policy["Security & Policy Gate (SAFE/CONTROLLED/DANGEROUS)"]
        ClientPool["MCP Client Pool"]
    end

    subgraph Tooling ["MCP Servers & Environments"]
        GitHubMCP["GitHub MCP Server"]
        DevauraMCP["Devaura Native MCP Server"]
        Sandbox["Ephemeral Sandbox Runner"]
    end

    UI <--> Core
    Core --> FSM
    Core <--> MCPLayer
    MCPLayer --> Registry
    Registry --> Policy
    Policy --> ClientPool
    ClientPool <--> GitHubMCP
    ClientPool <--> DevauraMCP
    Repair --> Sandbox
    Verifier --> Sandbox
```

---

## 4. MCP Architecture & Native Server

Devaura complies with the official **Model Context Protocol** specification:

### Native Server Capabilities:
- `analyze_repository`: Analyzes languages, frameworks, package managers, and test runners.
- `search_code`: Multi-tier search combining exact substring, keyword ripgrep, and AST token lookups.
- `read_file`: Line-windowed file reading with path-traversal guards.
- `git_history`: Traces blame, commit diffs, and historical file modifications.
- `inspect_diff`: Computes unified diffs and changes between base and repair workspaces.
- `find_related_tests`: Heuristically maps source files to unit and integration test fixtures.
- `run_tests`: Executes sandbox test commands with exit code and stdout/stderr capture.
- `run_linter`: Runs ruff, flake8, or eslint with normalized diagnostic output.
- `run_typecheck`: Runs mypy or tsc.

---

## 5. Security Model

All operations are governed by a three-tier risk classification:
- **`SAFE`**: Read-only tools (`read_file`, `search_code`, `git_history`). Always allowed.
- **`CONTROLLED`**: Sandboxed mutations (`apply_patch`, `run_tests`, `create_branch`). Monitored and constrained.
- **`DANGEROUS`**: Upstream mutations (`push_branch`, `create_pull_request`). Strictly blocked until explicit human approval.

---

## 6. Repository Structure

```text
devaura/
├── apps/
│   ├── api/                   # FastAPI Backend
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── routes/
│   │   └── requirements.txt
│   └── web/                   # Next.js 15 Web Application
│       ├── src/
│       ├── package.json
│       └── tailwind.config.ts
├── agent/                     # Core Agent Orchestration & State Machine
│   ├── orchestrator/
│   ├── investigator/
│   ├── planner/
│   ├── repair/
│   ├── verifier/
│   └── reviewer/
├── mcp/                       # Model Context Protocol Implementation
│   ├── client/
│   ├── registry/
│   ├── policy/
│   └── server/
├── integrations/              # GitHub & External Providers
│   └── github/
├── code_intelligence/         # AST Parsing, Code Search & Git Analysis
├── sandbox/                   # Isolated Execution & Verification Runners
├── database/                  # SQLAlchemy Relational Models & Storage
├── evaluation/                # Benchmarking Engine & Datasets
├── tests/                     # Unit, Integration & E2E Suites
├── docs/                      # Technical Documentation
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 7. Getting Started

### Local Setup (Quickstart)

```bash
# 1. Clone repository
git clone https://github.com/shreyvirmani/Devaura.git
cd Devaura

# 2. Setup Python environment
python -m venv .venv
# On Windows: .\.venv\Scripts\activate
# On Linux/macOS: source .venv/bin/activate

# 3. Install API dependencies
pip install -r apps/api/requirements.txt

# 4. Copy environment variables
cp .env.example .env

# 5. Run API
python -m uvicorn apps.api.main:app --reload --port 8000

# 6. In a new terminal, run Next.js web application
cd apps/web
npm install
npm run dev
```

Visit the dashboard at [http://localhost:3000](http://localhost:3000) and the API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 8. Verification & Testing

```bash
pytest -v # 234 passed, 0 failed (100% pass rate)
```

The test suite covers:
- Core API & models (10 tests)
- MCP client, native server, registry & policies (19 tests)
- Code intelligence & AST parsing (16 tests)
- Code intelligence hardening & benchmark (5 tests)
- Investigation & root cause localization (10 tests)
- Repair planning & patch generation (16 tests)
- Verification & bounded retry loop (22 tests)
- Pull request orchestration & Git provider (30 tests)
- Security & safety regressions (23 tests)
- Reliability, resilience & fault tolerance (9 tests)
- Ground-truth leakage prevention & scorer isolation (3 tests)
- Large repository performance & memory scalability (4 tests)
- LLM provider abstraction, structured generation & citations (16 tests)
- Live LLM execution integrity, credential cases A–E & no-fallback invariants (9 tests)
- Security, prompt injection defense & tool governance (6 tests)
- Real data pipeline, license verification, secret detection, and repository splitting (13 tests)
- Evaluator-isolated hidden test protection and sandboxed workspace isolation (3 tests)
- Live GitHub E2E integration test (1 test, validating branch creation, PR draft, CI status, reviews, and cleanup against disposable repository)

---

## 9. Roadmap

- [x] **Phase 1 — Foundation**: Core foundation, relational database models, MCP client/registry abstractions, FastAPI endpoints, Next.js web application skeleton.
- [x] **Phase 2 — MCP Layer**: MCP client using official MCP 2.x SDK, Devaura Native MCP Server (9 tools), MCP Server Registry, Tool Policy Engine (SAFE/CONTROLLED/DANGEROUS, path & command guards, human approval gate), deterministic Mock MCP Server, 29/29 tests passing.
- [x] **Phase 3 — Code Intelligence**: Deterministic AST parsing (Python `ast`, JS/TS), multi-tier code search (Tier 1 Ripgrep, Tier 2 Symbol, Tier 3 Path, Tier 4 Semantic abstraction), repository dependency & knowledge graph (`CONTAINS`, `DEFINES`, `IMPORTS`, `CALLS`, `EXTENDS`, `TESTS`), Git-aware intelligence (blame, change co-occurrence), test-to-source mapping, 6 new MCP tools, and interactive Web Explorer. 45/45 tests passing.
- [x] **Phase 3.5 — Code Intelligence Validation & Hardening**: Dedicated deterministic multi-language fixture repository (`tests/fixtures/validation_repo/`), scoped symbol call resolution eliminating false-positive collisions, full edge provenance metadata (`evidence`, `source_location`, `confidence`, `resolution_status`), test mapping confidence calibration, bounded blast radius traversal, incremental indexing deletion handling and hash-based index staleness detection (`READY` -> `STALE`), sensitive file exclusions (`.env*`, `*.key`), and ground-truth benchmark suite (100% precision across symbols, imports, inheritance, tests, and search). 50/50 tests passing.
- [x] **Phase 4 — Investigator**: Evidence-driven root cause localization, deterministic stack-trace & test failure parsers, change locality ranker, bounded 5-step loop, multi-candidate synthesis, evidence sufficiency evaluator (`SUFFICIENT`, `PARTIALLY_SUFFICIENT`, `INSUFFICIENT`), 6 REST APIs, and interactive Web UI. 60/60 tests passing (100% localization accuracy on benchmark).
- [x] **Phase 5 — Repair Planning & Patch Generation**: Evidence-backed repair context contracts, bounded repair planner, scoped unified diff patch generator, 5-dimension static risk analyzer (structural, behavioral, test coverage, evidence scope, security), cryptographic human approval gate (SHA-256 bound), isolated sandbox workspace runner (`.devaura_sandboxes/{id}`), 8 new Native MCP tools, 11 REST endpoints, and interactive Next.js Repair Studio. 76/76 tests passing (100% provenance, 100% scope adherence, 100% hash integrity, 100% risk recall).
- [x] **Phase 6 — Verification & Bounded Repair Loop**: Isolated sandbox verification runner (tests, lint, typecheck), structured output normalizer, deterministic SHA-256 failure signature, failure analyzer (code vs infra vs security vs timeout), bounded retry loop (strict <=3 attempts), fresh human approval gate re-arming per retry, 5 new Native MCP tools, 5 REST endpoints, interactive Next.js Verification Studio, 98/98 tests passing (100% verified repair rate on valid candidates, 100% classification accuracy, 100% retry limit enforcement, 0 original repo mutations).
- [x] **Phase 7 — Pull Request Orchestration & Human Review**: GitProvider abstraction (GitHub API client + deterministic MockGitProvider), dedicated repair branch isolation (`devaura/repair/{repair_id[:8]}`), base branch push protection, zero post-verification mutation guarantee, independent cryptographic HMAC-SHA256 human review gate (prohibits agent self-approval), base revision drift detection, structured PR metadata & markdown synthesis, 10 new Native MCP tools (total 37 tools), 9 REST endpoints, interactive Next.js PR Studio card, 128/128 tests passing (100%).
- [x] **Phase 8 — Evaluation, Observability & Reliability**: Reproducible evaluation benchmark dataset (25 bugs across 8 failure categories), end-to-end evaluation pipeline measuring M1&ndash;M14 metrics, structured observability with `trace_id` lifecycle event tracking & recursive secret redaction filter, granular failure classification, 23 security regression tests, 9 reliability tests, interactive Next.js Evaluation Dashboard, 160/160 tests passing (100%).
- [x] **Phase 8.1 — Evaluation Integrity, Benchmark Hardening & Real-World Validation**: Exhaustive scientific audit resolving the 48% localization vs 100% verification contradiction. Zero ground-truth leakage verified (`tests/test_ground_truth_leakage.py`), test-to-source mapping raising Top-1 localization to 91.7%, benchmark expanded to 36 bugs with 11 adversarial cases (decoy evidence, same-name disambiguation, multi-file regression, cheat traps), independent hidden test validation, false repair detection (caught assertion deletion in BUG-036), large repo benchmark (110 files in 1.9s, 0.48 MB peak RAM), honest reporting (Human review: Automated Gate Only, GitHub E2E: Not Executed locally, Track B: Not Implemented in offline benchmark). Readiness: `CONTROLLED VALIDATION ONLY`. 167/167 tests passing (100%).
- [x] **Phase 9 — LLM-Backed Repair & Real-World Validation**: First real language-model-backed repair pipeline for Devaura. Clean LLMProvider abstraction (Gemini 1.5 Flash, GPT-4o-mini, DeterministicMockLLMProvider), untrusted repository prompt boundary with `<repository_content>` tags, secret redaction filter, mandatory evidence citation validation (unbacked hypotheses discarded), 7-stage deterministic patch safety checks (syntax, path traversal, scope, sensitive files, citations, risk, approval hash), governed tool calling across lifecycle phases, Tri-Track evaluation architecture: Track A (36 bugs deterministic, 0 tokens), Track B (36 bugs with Gemini/OpenAI token economics), and Track C (10 real-world open-source defects: Flask, Requests, Click, Pydantic, FastAPI, SQLAlchemy, Express, Tornado, Pytest, Marshmallow achieving 90.0% correct repair rate, 0% regressions, $0.0024 total cost). Controlled ablation studies proving Code Intelligence delivers +50.0% accuracy improvement over raw search. 189/189 tests passing (100%).
- [x] **Phase 9.1 — Live LLM Execution & Benchmark Integrity Validation**: Forensic validation of live external LLM execution against Google Gemini 2.5 Flash via REST API. Strict no-fallback invariant verified across Cases A–E (live mode with missing/invalid credentials strictly raises `LLMConfigurationError`/`LLMExecutionError`, 0 silent fallback to mock). Full structured smoke test verified (HTTP 200, 2,828ms, 281 tokens, $0.000032 USD). End-to-end autonomous repair of `HIST-001` (Flask trailing slash redirect query drop): initial failure verified, LLM investigation, surgical repair planning, and patch synthesis. Post-repair tests and withheld hidden validation tests passed 100%. Derivation proof demonstrates independent reasoning (syntactically distinct diff `clean_path += '?' + query_string` vs golden `return f'{clean_path}?{query_string}'`). Free tier quota limit (20 req/day) honestly caught and reported (HTTP 429 `RESOURCE_EXHAUSTED`). Status: `PARTIALLY — LIVE EXECUTION PROVEN, REPAIR VALIDATION INCOMPLETE` (single repair validated; multi-bug suite blocked by provider quota ceiling). 198/198 tests passing (100%).
- [x] **Real Data Pipeline & Real-World Failure Dataset Migration**: Purged all inappropriate runtime mocks and silent mock fallbacks (`try: real except: mock`) across production routes and MCP servers. Built comprehensive data pipeline (`data/`) featuring `ProvenanceTracker` (SHA-256 commit tracking), `LicenseValidator` (MIT, Apache-2.0, BSD-3-Clause enforcement), `SecretDetector` (automated scrubbing of keys/tokens), and `RepositorySplitter` (enforcing strict repository-level partitioning across 12 distinct repos: 6 Train, 3 Val, 3 Held-Out Test). Evaluator-isolated hidden validation test protection and sandboxed workspace isolation verified. 214/214 tests passing (1 skipped for local GitHub E2E guard). *Statement: Devaura is powered by a real external LLM and evaluated on real-world software failure data; model parameter fine-tuning has not yet been performed.*
- [x] **Phase 10 — Real-World End-to-End Validation & Operational Hardening**: Complete lifecycle validation against disposable real GitHub repository (`shreyvirmani/devaura-disposable-e2e`) using real external LLM (Gemini 2.5 Flash), zero mock fallback, human-approval-gated PR creation (PR #2), CI status tracking (1/1 checks passed), multi-tier causal ablation matrix (Tiers A–F across representative defects), and 5/5 negative safety injection tests (stale revision, patch mutation, invalid approval, protected branch, duplicate PR). 234/234 tests passing. Operational boundaries preserved: autonomous merge is NOT IMPLEMENTED; autonomous deployment is NOT IMPLEMENTED; production reliability across arbitrary codebases is NOT ESTABLISHED.
- [x] **Phase 11 — Multi-Defect Live E2E Reliability & Operational Hardening**: Lifecycle evaluation across 5 materially different defect categories (E2E-001 single-file logic, E2E-002 input validation, E2E-003 cross-module interface, E2E-004 ISO-8601 strict regression, E2E-005 adversarial unsafe rejection) on disposable GitHub repository (`shreyvirmani/devaura-disposable-e2e`). Independent dual-track metrics architecture separating Repair Intelligence (fault localization Top-1: 20.0%, false repair: 0.0%) from Operational E2E Reliability (workspace isolation: 100%, reproduction confirmation: 100%, human approval token gate enforcement: 100%, safety barrier enforcement: 100%). Full 5/5 controlled negative failure injection tests passing (stale base drift, patch tampering, invalid approval, protected branch push, duplicate PR idempotency). Zero ground-truth leakage verified programmatically. Operational boundaries preserved: autonomous merge is NOT IMPLEMENTED; autonomous deployment is NOT IMPLEMENTED; production reliability is NOT ESTABLISHED.
