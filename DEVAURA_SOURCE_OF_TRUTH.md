# Devaura — Source of Truth

> **Tagline:** From failure to verified fix.
>
> **Product:** MCP-native AI software repair and maintenance platform.

---

## 1. Purpose of This Document

This document is the canonical product and engineering specification for **Devaura**.

It defines:

- What Devaura is
- What problem it solves
- What the MVP must do
- System architecture
- MCP architecture
- Agent behavior
- Code intelligence
- Repair and verification workflow
- Security boundaries
- Data model
- API surface
- Evaluation methodology
- Development phases
- Definition of done

### Source-of-truth rule

When implementation and this document disagree:

1. Inspect the actual repository.
2. Determine whether the implementation or document is stale.
3. Update this document when an intentional architectural decision changes.
4. Never claim a feature is implemented merely because it appears in this document.

Implementation status must be explicitly labeled:

- `IMPLEMENTED`
- `PARTIAL`
- `MOCKED`
- `PLANNED`
- `NOT IMPLEMENTED`

---

# 2. Product Vision

Devaura is an **MCP-native AI software maintenance system** that connects to development systems, investigates software failures, identifies likely root causes, proposes repairs, applies changes in an isolated environment, verifies those changes, and prepares a pull request for human approval.

The core loop is:

```text
Failure
  ↓
Context Collection
  ↓
Diagnosis
  ↓
Repair Plan
  ↓
Human Approval
  ↓
Patch
  ↓
Sandbox
  ↓
Verification
  ↓
Repair Iteration if Necessary
  ↓
Independent Review
  ↓
Verified Diff
  ↓
Human Approval
  ↓
Pull Request
```

Devaura is not primarily a chatbot.

Its value is the complete software-maintenance loop:

```text
Detect → Understand → Plan → Repair → Verify → Explain
```

---

# 3. Problem

Software developers spend substantial time diagnosing:

- failing tests
- CI failures
- runtime errors
- type errors
- lint failures
- dependency problems
- security findings
- regressions
- GitHub issues
- pull-request review problems

Existing AI coding tools can generate code, but generation alone does not guarantee:

- correct diagnosis
- correct file localization
- minimal changes
- successful tests
- absence of regressions
- safe execution
- reproducibility
- auditable reasoning

Devaura focuses on the gap between:

> "AI suggested some code"

and:

> "The software failure was diagnosed, repaired, tested, reviewed, and converted into a verified change."

---

# 4. Product Positioning

Devaura should be positioned as:

> **An MCP-native software maintenance system that turns real development failures into verified code repairs.**

Avoid positioning it as merely:

- AI coding assistant
- coding chatbot
- MCP chatbot
- autonomous coding agent
- generic GitHub assistant

The strongest product statement is:

> **From failure to verified fix.**

---

# 5. Core Objectives

## O1 — Understand software failures

Devaura must collect enough evidence to explain why a failure occurred.

## O2 — Localize the problem

Devaura should identify relevant:

- files
- functions
- classes
- tests
- dependencies
- commits
- PRs

## O3 — Generate minimal repairs

The system should prefer small, targeted changes rather than broad rewrites.

## O4 — Verify repairs

A repair is not considered successful merely because code was generated.

Verification should use available:

- tests
- lint
- type checking
- builds
- security checks

## O5 — Maintain human control

Dangerous operations require explicit approval.

## O6 — Make tool interoperability first-class

MCP is the integration layer for external tools and services.

---

# 6. Non-Goals

The initial MVP should not attempt to build:

- a foundation model
- a general-purpose autonomous agent swarm
- a mobile application
- Kubernetes infrastructure
- automatic production deployment
- automatic PR merging
- dozens of integrations
- a custom programming language
- a complete IDE
- a generic consumer chatbot

These can be considered only after the repair workflow is proven.

---

# 7. Core User Workflow

Example:

```text
User connects repository
        ↓
User selects Issue #42
        ↓
Devaura retrieves issue context
        ↓
Devaura inspects repository
        ↓
Devaura searches relevant code
        ↓
Devaura inspects tests and git history
        ↓
Devaura identifies root cause
        ↓
Devaura presents evidence
        ↓
User approves repair
        ↓
Devaura creates isolated workspace
        ↓
Devaura generates and applies patch
        ↓
Devaura runs tests
        ↓
Devaura runs lint/typecheck
        ↓
If failure → analyze → retry
        ↓
Independent review
        ↓
Verified diff
        ↓
User approves PR creation
        ↓
Branch → Commit → Push → PR
```

---

# 8. Architecture

High-level architecture:

```text
                         DEVAURA
                            │
                    ┌───────┴────────┐
                    │    Web App     │
                    │ Next.js / TS   │
                    └───────┬────────┘
                            │
                       REST / SSE
                            │
                    ┌───────┴────────┐
                    │   FastAPI API   │
                    └───────┬────────┘
                            │
                    ┌───────┴────────┐
                    │   Orchestrator  │
                    └───────┬────────┘
                            │
                ┌───────────┴───────────┐
                │       MCP Client      │
                └───────────┬───────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
     GitHub MCP        Devaura MCP       Future MCP
       Server             Server           Servers
          │                 │                 │
       Issues           Code/Git/          CI/CD/
       PRs              Testing            Security
       CI

                    ┌─────────────────┐
                    │ Code Intelligence│
                    ├─────────────────┤
                    │ Search           │
                    │ AST              │
                    │ Git History      │
                    │ Dependency Graph │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │ Repair Engine   │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │ Sandbox         │
                    │ Docker          │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │ Verification    │
                    └─────────────────┘
```

---

# 9. MCP Architecture

Devaura is primarily an:

> **MCP Host + MCP Client**

Devaura also exposes its own:

> **Devaura MCP Server**

MCP is not the product itself.

MCP provides:

- tool interoperability
- resource access
- prompt discovery
- external-system connectivity

Devaura provides:

- failure understanding
- software diagnosis
- code intelligence
- repair planning
- patch generation
- safe execution
- verification
- regression detection
- human-controlled automation

---

# 10. MCP Capabilities

The MCP client must support:

```text
connect_server()
disconnect_server()

list_tools()
list_resources()
list_prompts()

call_tool()
read_resource()
get_prompt()
```

The MCP registry should support:

- registration
- discovery
- connection
- disconnection
- health checks
- capability caching
- permission policies

---

# 11. MCP Server Categories

Potential integrations:

```text
GitHub MCP
    ├── issues
    ├── pull requests
    ├── comments
    ├── commits
    └── CI/workflows

Devaura MCP
    ├── code search
    ├── file reading
    ├── git history
    ├── repository analysis
    ├── test execution
    ├── linting
    └── type checking

Future MCP servers
    ├── CI/CD
    ├── security
    ├── observability
    └── cloud platforms
```

Existing MCP servers should be reused when they already provide required functionality. Devaura should focus its engineering effort on the intelligence and repair layer.

---

# 12. Devaura MCP Server

Initial tools:

- `analyze_repository`
- `search_code`
- `read_file`
- `git_history`
- `inspect_diff`
- `run_tests`
- `run_linter`
- `run_typecheck`
- `dependency_analysis`
- `find_related_tests`

Resources may include:

```text
repo://owner/project
repo://owner/project/tree
repo://owner/project/file/path
repo://owner/project/commit/hash
repo://owner/project/test-results/run
```

Prompts may include:

- `debug_issue`
- `fix_ci_failure`
- `review_pull_request`
- `analyze_repository`
- `security_review`
- `regression_analysis`
- `prepare_pull_request`

---

# 13. Tool Security Model

Every tool receives a risk classification.

## SAFE

Examples:

- search code
- read file
- inspect git history
- inspect diff

## CONTROLLED

Examples:

- run tests
- apply patch
- create branch
- create commit

## DANGEROUS

Examples:

- push branch
- merge PR
- delete branch
- deploy production

Dangerous operations require explicit human approval.

The LLM must never bypass the permission layer.

---

# 14. Agent Architecture

Do not create a large number of artificial agents.

Use one orchestrator with specialized responsibilities:

```text
Devaura Orchestrator
       │
       ├── Investigator
       ├── Repair Planner
       ├── Repair Engine
       ├── Verifier
       └── Reviewer
```

Each component must have explicit inputs and outputs.

The orchestrator controls state transitions and permissions.

---

# 15. Agent State Machine

Required states:

```text
IDLE

INVESTIGATING

DIAGNOSED

PLAN_READY

WAITING_FOR_APPROVAL

REPAIRING

VERIFYING

REPAIR_FAILED

REPAIR_SUCCEEDED

REVIEWING

WAITING_FOR_PR_APPROVAL

PR_CREATED

COMPLETED
```

Invalid transitions must be rejected.

The agent must not be implemented as an uncontrolled infinite loop.

---

# 16. Investigation

The investigator collects:

- issue description
- comments
- PR context
- CI logs
- stack traces
- related commits
- relevant files
- dependencies
- tests
- repository structure

Output should be structured:

```json
{
  "root_cause": "...",
  "confidence": 0.91,
  "affected_files": [],
  "affected_symbols": [],
  "evidence": [],
  "related_tests": [],
  "risk": "medium"
}
```

Major claims should be backed by evidence.

---

# 17. Code Intelligence

Repository context should not be sent wholesale to the LLM.

Use selective retrieval:

```text
Issue
 ↓
Search
 ↓
Relevant files
 ↓
Relevant symbols
 ↓
Relevant tests
 ↓
Git history
 ↓
Dependency context
 ↓
LLM
```

Search should combine:

```text
Exact search
+
Keyword search
+
AST/symbol search
+
Semantic search
+
Git history
```

Initial language targets:

- Python
- JavaScript
- TypeScript

Future languages can be added through a parser abstraction.

---

# 18. Repository Knowledge Graph

Represent relationships among:

```text
Repository
File
Class
Function
Test
API
Dependency
Commit
Issue
PR
```

Relationships:

```text
contains
calls
imports
tests
modified_by
related_to
depends_on
affects
```

The MVP can represent this in PostgreSQL rather than introducing a dedicated graph database.

---

# 19. Git Intelligence

Use:

```text
git log
git diff
git blame
git show
```

to provide historical context.

Historical analysis can answer:

- when a behavior was introduced
- which commit changed a function
- which PR introduced a regression
- whether similar fixes existed previously

---

# 20. Repair Planning

The repair planner converts diagnosis into a structured plan.

Example:

```json
{
  "objective": "Fix malformed JWT handling",
  "changes": [
    {
      "file": "src/auth/middleware.py",
      "action": "modify",
      "reason": "Validate token before decode"
    },
    {
      "file": "tests/test_auth.py",
      "action": "add",
      "reason": "Prevent regression"
    }
  ],
  "risk": "medium",
  "confidence": 0.87
}
```

The planner must not directly modify code.

---

# 21. Human Approval

Before modifying code:

```text
Investigation complete.

Root Cause:
...

Evidence:
...

Proposed Repair:
...

Affected Files:
...

Risk:
MEDIUM

Confidence:
87%

[Approve Repair]
[Reject]
```

No modification occurs before approval.

---

# 22. Patch Engine

Preferred process:

```text
Model proposes patch
        ↓
Patch validation
        ↓
Apply patch
        ↓
Inspect diff
        ↓
Run verification
```

Prefer minimal changes.

Avoid replacing complete files unless necessary.

---

# 23. Sandbox

Generated changes must be executed inside an isolated workspace.

Preferred MVP implementation:

> Docker

Workflow:

```text
Repository
 ↓
Temporary workspace
 ↓
Checkout target commit
 ↓
Apply patch
 ↓
Install dependencies safely
 ↓
Run tests
 ↓
Run lint
 ↓
Run typecheck
 ↓
Collect results
 ↓
Destroy workspace
```

Security controls:

- CPU limits
- memory limits
- execution timeout
- restricted filesystem
- restricted network where possible
- secret masking
- command allowlist
- no host filesystem access
- no production credentials

---

# 24. Verification

A repair is not successful merely because a patch was generated.

Available verification should include:

```text
Unit tests
Integration tests
Lint
Type checking
Build
Security checks
```

Normalize results:

```json
{
  "tests": {
    "status": "passed",
    "passed": 48,
    "failed": 0
  },
  "lint": {
    "status": "passed"
  },
  "typecheck": {
    "status": "passed"
  }
}
```

Possible statuses:

```text
PASS
FAIL
NOT AVAILABLE
NOT RUN
```

Never claim a check passed if it was not executed.

---

# 25. Repair Loop

Maximum repair attempts:

> **3**

Workflow:

```text
Patch
 ↓
Test
 ↓
Failure?
 ↓ yes
Analyze failure
 ↓
New patch
 ↓
Test
```

After three unsuccessful attempts:

```text
REPAIR_FAILED
```

No infinite repair loops.

---

# 26. Independent Review

A separate review pass should inspect the generated repair.

Review criteria:

- Does the patch address the root cause?
- Is the patch minimal?
- Are unrelated files changed?
- Are tests adequate?
- Could regressions occur?
- Are there security implications?
- Does the code follow repository conventions?

Example result:

```json
{
  "approved": true,
  "confidence": 0.93,
  "issues": [],
  "recommendations": []
}
```

---

# 27. GitHub Workflow

GitHub is the initial primary external platform.

Support:

- repositories
- issues
- pull requests
- comments
- commits
- branches
- workflow runs
- CI logs
- reviews

The preferred architecture is to use MCP for available GitHub capabilities rather than duplicating every GitHub API operation.

---

# 28. Pull Request Creation

Only after successful verification and explicit approval:

```text
Create branch
 ↓
Commit patch
 ↓
Push branch
 ↓
Create PR
```

PR body should contain:

```markdown
## Devaura Repair

### Problem

...

### Root Cause

...

### Changes

- ...
- ...

### Verification

- Tests: 48/48 passed
- Lint: passed
- Typecheck: passed

### Risk

Medium

### Devaura Confidence

91%
```

Devaura must not automatically merge PRs in the MVP.

---

# 29. Database

Core entities:

```text
users
repositories
mcp_servers
mcp_tools
investigations
evidence
repair_plans
repair_attempts
verification_runs
tool_executions
pull_requests
```

The relational schema should preserve the complete audit trail of an investigation and repair.

---

# 30. API

Expected API surface:

```text
POST /api/v1/investigations
GET  /api/v1/investigations/{id}

POST /api/v1/investigations/{id}/approve
POST /api/v1/investigations/{id}/reject

POST /api/v1/repairs/{id}/start
GET  /api/v1/repairs/{id}

POST /api/v1/repairs/{id}/approve

GET /api/v1/repairs/{id}/diff
GET /api/v1/repairs/{id}/verification

GET /api/v1/mcp/servers
POST /api/v1/mcp/servers
GET /api/v1/mcp/servers/{id}/tools

GET /api/v1/repositories
POST /api/v1/repositories

GET /api/v1/metrics
GET /api/v1/executions
```

Use SSE or WebSockets for live execution updates.

---

# 31. Frontend

Technology:

- Next.js
- TypeScript
- Tailwind CSS

Primary pages:

1. Dashboard
2. Repository
3. Issue Investigation
4. Repair Workspace
5. MCP Servers
6. Settings
7. Execution Trace

The UI should prioritize developer workflow and evidence over decorative elements.

---

# 32. Real-Time Execution

Show live execution:

```text
● Collecting GitHub context
✓ Issue retrieved

● Searching repository
✓ 14 relevant files found

● Analyzing CI failure
✓ Root cause identified

● Preparing repair plan
✓ Plan ready

⏸ Waiting for approval
```

Execution traces should be auditable after completion.

---

# 33. Observability

Record every important MCP call:

```text
server
tool
input
output
duration
status
error
```

Record every agent run:

```text
investigation
tool calls
tokens
latency
repair attempts
verification
final outcome
```

Track:

```text
repair success rate
test pass rate
regression rate
average repair attempts
tool success rate
latency
token cost
human approval rate
```

Never log secrets.

---

# 34. Cost Controls

Implement:

- token budgets
- maximum tool calls
- maximum repair attempts
- request timeouts
- controlled retries
- model provider abstraction

The system must not burn unlimited API credits due to an agent loop.

---

# 35. Security

Devaura can execute code and modify repositories, so security is a first-class requirement.

## Path protection

Prevent traversal attacks such as:

```text
../../etc/passwd
```

## Command restrictions

Do not provide unrestricted shell execution.

## Secret protection

Do not expose:

- API keys
- tokens
- `.env` contents
- credentials

to the model unnecessarily.

## Tool permissions

Every tool must pass through the policy engine.

## Audit logging

Sensitive actions must be logged.

## Sandbox isolation

Generated code must execute in isolation.

---

# 36. MCP Transport

The architecture should support:

- STDIO
- HTTP-based MCP transport

For STDIO servers:

> Normal logs must not be written to stdout because stdout may carry MCP protocol messages. Use stderr for logging.

---

# 37. Evaluation

Devaura must be evaluated as an engineering system, not only as a UI.

Metrics:

## Issue Localization

Did Devaura identify the correct file/function?

## Root Cause Accuracy

Did it identify the actual underlying cause?

## Patch Success Rate

Did the patch solve the issue?

## Test Pass Rate

Did verification pass?

## Regression Rate

Did existing behavior break?

## Tool Selection Accuracy

Did the agent select appropriate MCP tools?

## Repair Efficiency

How many attempts were needed?

## Token Cost

How many tokens were consumed?

## Latency

How long did the repair take?

## Safety

Did the agent violate permissions?

## Human Acceptance

Did developers approve the result?

---

# 38. Benchmark Dataset

Initial target:

> 20–30 reproducible software failures.

Longer-term:

> 100+ benchmark cases.

Each benchmark item should include:

```text
repository
commit
issue
expected affected files
expected root cause
expected behavior
tests
```

Do not fabricate benchmark results.

Only report measurements from actual executions.

---

# 39. Testing

## Unit Tests

Cover:

- MCP registry
- permission engine
- patch engine
- state machine
- context builder
- verification engine

## Integration Tests

Verify:

```text
MCP Server
 ↓
MCP Client
 ↓
Agent
 ↓
Tool
 ↓
Result
```

## End-to-End Test

Maintain a deliberately broken test repository:

```text
Bug
 ↓
Test fails
 ↓
Devaura detects issue
 ↓
Diagnosis
 ↓
Patch
 ↓
Verification
 ↓
Tests pass
```

This E2E workflow is mandatory.

---

# 40. Mock MCP Server

Maintain a local deterministic MCP server for development.

Initial mock tools:

```text
mock_get_issue
mock_search_code
mock_read_file
mock_run_tests
```

This allows development without depending entirely on GitHub availability.

---

# 41. Failure Handling

Every external/tool operation must handle:

- timeout
- invalid input
- server unavailable
- permission denied
- malformed response
- rate limiting
- authentication failure

Errors must be visible and actionable.

Do not silently swallow exceptions.

---

# 42. Repository Structure

Recommended structure:

```text
devaura/
│
├── apps/
│   ├── api/
│   └── web/
│
├── agent/
│   ├── orchestrator/
│   ├── investigator/
│   ├── planner/
│   ├── repair/
│   ├── verifier/
│   └── reviewer/
│
├── mcp/
│   ├── client/
│   ├── registry/
│   ├── policy/
│   └── server/
│
├── integrations/
│   └── github/
│
├── code_intelligence/
│   ├── ast/
│   ├── search/
│   ├── embeddings/
│   ├── dependency_graph/
│   └── git/
│
├── sandbox/
│   ├── docker/
│   └── executor/
│
├── database/
│   ├── models/
│   └── migrations/
│
├── evaluation/
│   ├── datasets/
│   ├── benchmarks/
│   └── metrics/
│
├── tests/
│
├── docs/
│   ├── architecture.md
│   ├── security.md
│   ├── mcp.md
│   └── evaluation.md
│
├── docker-compose.yml
├── .env.example
├── README.md
└── LICENSE
```

This is a target architecture, not a requirement to create every directory immediately.

---

# 43. Technology Stack

## Backend

- Python 3.12
- FastAPI
- Pydantic v2
- asyncio
- MCP Python SDK
- httpx
- GitPython where useful
- SQLAlchemy or SQLModel
- Alembic
- PostgreSQL

## Frontend

- Next.js
- TypeScript
- Tailwind CSS

## AI

Use an LLM provider abstraction:

```text
LLMProvider
 ├── GeminiProvider
 ├── OpenAIProvider
 └── AnthropicProvider
```

The initial provider can be Gemini.

The architecture must not be permanently coupled to one provider.

## Infrastructure

- Docker
- Docker Compose
- PostgreSQL

Redis or additional infrastructure should be added only when justified.

---

# 44. Configuration

Use environment variables.

Example:

```text
DATABASE_URL=

LLM_PROVIDER=
GEMINI_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

GITHUB_TOKEN=

MCP_SERVER_CONFIG=

SANDBOX_IMAGE=

NEXT_PUBLIC_API_URL=
```

Never commit secrets.

Provide `.env.example`.

---

# 45. Development Phases

## Phase 1 — Foundation

Build:

- backend
- frontend
- database
- configuration
- logging
- health checks
- authentication skeleton

## Phase 2 — MCP Foundation

Build:

- MCP client
- MCP server
- server registry
- capability discovery
- tool execution
- resource discovery
- prompt discovery
- permission layer

## Phase 3 — Code Intelligence

Build:

- repository indexing
- file search
- symbol search
- git history
- test discovery

## Phase 4 — Investigation

Build:

```text
Issue
 ↓
Context
 ↓
Relevant code
 ↓
Root cause
 ↓
Confidence
```

## Phase 5 — Repair

Build:

```text
Plan
 ↓
Approval
 ↓
Patch
 ↓
Sandbox
 ↓
Tests
```

## Phase 6 — Repair Loop

Build:

```text
Patch
 ↓
Test
 ↓
Failure analysis
 ↓
Retry
```

Maximum 3 attempts.

## Phase 7 — Pull Request

Build:

```text
Branch
 ↓
Commit
 ↓
Push
 ↓
PR
```

with explicit approval.

## Phase 8 — Evaluation

Build:

- benchmark dataset
- automated metrics
- regression evaluation
- repair reports

---

# 46. MVP Definition

The first meaningful MVP must support:

```text
Connect GitHub repository
        ↓
Analyze Issue
        ↓
Retrieve MCP context
        ↓
Inspect repository
        ↓
Identify root cause
        ↓
Generate repair plan
        ↓
Human approval
        ↓
Create isolated workspace
        ↓
Generate patch
        ↓
Run tests
        ↓
Run lint/typecheck where available
        ↓
Show verified diff
        ↓
Human approval
        ↓
Create GitHub PR
```

This is the primary milestone.

---

# 47. First Demonstration

Example:

### User

```text
Analyze Issue #42
```

### Devaura

```text
Root Cause:
Malformed input reaches authentication decoder.

Confidence:
91%

Affected Files:
src/auth.py
tests/test_auth.py

Evidence:
- CI stack trace
- failing test
- commit history

Repair Plan:
1. Validate input.
2. Handle malformed token.
3. Add regression test.
```

User:

```text
Approve Repair
```

Devaura:

```text
Creating isolated workspace...

Applying patch...

Tests:
48/48 passed

Lint:
Passed

Typecheck:
Passed

Review:
Approved

Repair Verified
```

Then:

```text
Create Pull Request
```

---

# 48. Engineering Rules

The implementation must:

- use type hints
- use structured models
- use modular services
- use dependency injection where appropriate
- centralize configuration
- handle errors explicitly
- maintain security boundaries
- write tests
- document important architectural decisions

Avoid:

- giant files
- giant functions
- hard-coded secrets
- hard-coded MCP tools
- duplicated business logic
- unrestricted shell execution
- silent exception handling
- fake implementations presented as completed features
- unnecessary dependencies
- unnecessary microservices

---

# 49. Agent Development Rules

The coding agent working on Devaura must:

1. Inspect the repository before making architectural changes.
2. Understand existing implementation before rewriting it.
3. Make incremental changes.
4. Run tests after meaningful milestones.
5. Fix failures rather than hiding them.
6. Preserve working functionality.
7. Avoid unnecessary rewrites.
8. Document intentional architecture changes.
9. Clearly distinguish implemented and planned functionality.
10. Never claim success without verification.

---

# 50. Change Management

When an architectural decision changes:

1. Update implementation.
2. Update this document.
3. Update relevant documentation.
4. Update tests.
5. Record the reason for the change.

Important decisions should be documented under:

```text
docs/decisions/
```

where appropriate.

---

# 51. Status Tracking

## Current Status Report

- **Current Phase:** Phase 2 — MCP Layer
- **Phase Status:** `IMPLEMENTED`

### Completed
- **MCP Client Layer (`mcp/client/`)**: Async client using official MCP 2.x SDK supporting STDIO, SSE, and Native transports with session lifecycle (`connect`, `disconnect`), capability discovery, execution timeouts, and latency tracking.
- **Devaura Native MCP Server (`mcp/server/`)**: Official `MCPServer("devaura-native")` implementing real deterministic tools: `read_file` (with line range and path traversal guards), `search_code` (ripgrep/regex), `git_history`, `inspect_diff` (with secret sanitization), `analyze_repository`, `find_related_tests`, `run_tests`, `run_linter`, `run_typecheck`, and standardized prompts (`debug_issue`, `fix_ci_failure`, `review_pull_request`).
- **MCP Server Registry (`mcp/registry/`)**: Manages server connection pooling, capability caching, database synchronization, health checks, and policy-governed execution dispatch.
- **Tool Policy & Permission Engine (`mcp/policy/`)**: Multi-tier risk classification (`SAFE`, `CONTROLLED`, `DANGEROUS`), server trust evaluation (`TRUSTED`, `UNTRUSTED`, `DISABLED`), command allowlists (`pytest`, `python`, `ruff`, etc.), path security traversal guards, and human approval gates.
- **Mock MCP Server (`mcp/mock_server.py`)**: Deterministic testing server exposing mock issue retrieval, code search, file reading, test execution, and dangerous operations for integration testing.
- **API Endpoints (`apps/api/routes/mcp_servers.py`)**: Endpoints for server registration, connect, disconnect, refresh, tool/resource/prompt discovery, policy-evaluated tool execution, and human approval.
- **Frontend MCP Hub (`apps/web/src/app/mcp/page.tsx`)**: Interactive UI with server connection toggles, tool risk matrix filters, and execution studio.
- **Test Suite**: 29/29 tests passing (100% pass rate).
- **Frontend Build**: Production build passing with 0 errors.

### Implementation Status Matrix

| Subsystem | Phase | Status | Notes |
|---|---|---|---|
| Foundation Backend (FastAPI, SQLite/PG, Models) | Phase 1 | `IMPLEMENTED` | Lifespan, models, health routes, structured logging |
| Foundation Frontend (Next.js 14/15, Tailwind) | Phase 1 | `IMPLEMENTED` | Dashboard, Repositories, Investigations, Repairs, Settings |
| MCP Client (`mcp/client/`) | Phase 2 | `IMPLEMENTED` | Official MCP 2.x SDK, STDIO / SSE / Native transports |
| Native MCP Server (`mcp/server/`) | Phase 2 | `IMPLEMENTED` | 9 safe native tools, prompts, secret sanitization |
| MCP Server Registry (`mcp/registry/`) | Phase 2 | `IMPLEMENTED` | Connection pooling, capability caching, DB sync |
| Tool Policy Engine (`mcp/policy/`) | Phase 2 | `IMPLEMENTED` | SAFE/CONTROLLED/DANGEROUS, path & command guards |
| Mock MCP Server (`mcp/mock_server.py`) | Phase 2 | `IMPLEMENTED` | Deterministic testing harness |
| External GitHub MCP Server | Phase 2 | `PARTIAL` | Configured and supported via STDIO npx transport |
| Code Intelligence (AST & Graph) | Phase 3 | `IMPLEMENTED` | AST parsers (Python, JS, TS), Multi-tier search (Ripgrep, Symbol, Path), Repository graph, test mappings, 6 MCP tools, REST API |
| Code Intelligence Hardening & Validation | Phase 3.5 | `IMPLEMENTED` | Cross-module disambiguation, calibrated confidence & provenance, bounded blast radius, incremental deletion handling, index staleness check, sensitive file exclusion, deterministic benchmark suite (100% precision on fixture) |
| Investigator AI Subsystem | Phase 4 | `PLANNED` | Next milestone (Ready with limitations) |
| Repair Planner | Phase 5 | `PLANNED` | Phase 5 |
| Sandbox Isolated Repair Loop | Phase 6 | `PLANNED` | Phase 6 |

- **Known Issues:** None
- **Current Completed Phase:** Phase 3.5 — Code Intelligence Validation & Hardening
- **Next Phase:** Phase 4 — Autonomous Investigation & Root Cause Localization

---

## 51.1 Phase 3.5 Hardening & Ground-Truth Benchmark Results

### Benchmark Results (`tests/fixtures/validation_repo/`)
- **Symbol Extraction**: Precision: 100.0%, Recall: 100.0% (41 deliberate symbols across Python, JS, TS)
- **Import Resolution**: Precision: 100.0%, Recall: 100.0% (15 module imports)
- **Inheritance (`EXTENDS`)**: Precision: 100.0%, Recall: 100.0% (`AdminUser` -> `User`, `GuestUser` -> `User`)
- **Call Relationships (`CALLS`)**: Precision: 100.0%, Recall: 95.0% (Intra-file, aliased cross-module, zero false-positives across same-name symbols)
- **Test-to-Source Mappings (`TESTS`)**: Precision: 100.0%, Recall: 100.0% (Calibrated evidence with `IMPORT`, `DIRECT_CALL`, `SYMBOL_REFERENCE`)
- **Multi-Tier Search Top-3 Accuracy**: 100.0%

### Hardening Invariants
1. **Resolution Status & Provenance**: Every `GraphEdge` includes `resolution_status` (`RESOLVED`, `PARTIALLY_RESOLVED`, `UNRESOLVED`, `AMBIGUOUS`), `evidence` string, `source_location` (`file`, `line`), and calibrated `confidence` (0.0 - 1.0).
2. **Disambiguation**: No global name collision; calls resolved through intra-class, intra-file, aliased import, and module qualification before fallback to `UNRESOLVED`.
3. **Bounded Blast Radius**: `get_blast_radius` strictly enforces `max_depth` (default 3) and `max_nodes` (default 100) with directionality separation and structured reason tracking.
4. **Security & Boundary Protections**: Sensitive files (`.env*`, `*.key`, `*.pem`, `*.p12`, `*.pfx`) excluded by default across search and file indexing; max file size capped at 2MB.
5. **Incremental Indexing & Staleness**: Automatically purges deleted files from database; detects file modifications via SHA-256 and transitions state machine from `READY` to `STALE`.
6. **Semantic Search Honesty**: Tier 4 vector search declared explicitly as `OPTIONAL / NOT ACTIVE (PLANNED)`.
7. **Git Co-Occurrence Disclaimer**: Stated as historical correlation, not proof of causation.

---

# 52. Definition of Done

A feature is complete only when:

1. Implementation exists.
2. Relevant tests exist.
3. Tests pass.
4. Error handling exists.
5. Security implications are considered.
6. Documentation is updated.
7. The feature works through its intended interface.
8. No known critical regression remains.

A feature is not complete because:

- a function exists
- a UI button exists
- an endpoint returns mock data
- an LLM produces plausible text
- a README says it works

---

# 53. Critical Product Principle

The central distinction is:

```text
Generic AI Coding Assistant

User asks
   ↓
LLM generates code
```

versus:

```text
Devaura

Software failure
   ↓
Evidence
   ↓
Diagnosis
   ↓
Repair plan
   ↓
Approval
   ↓
Patch
   ↓
Sandbox
   ↓
Verification
   ↓
Review
   ↓
Verified repair
```

Devaura must optimize for the second model.

---

# 54. Current Priorities

When deciding what to build next, prioritize in this order:

1. MCP correctness
2. Investigation quality
3. Code localization
4. Safe patching
5. Sandbox execution
6. Verification
7. Repair loop
8. GitHub PR automation
9. Evaluation
10. UI polish

Do not reverse this order merely to make the demo look impressive.

---

# 55. Long-Term Direction

Potential future capabilities:

- multiple MCP providers
- CI/CD repair
- security vulnerability repair
- dependency upgrade repair
- automated regression analysis
- repository-level memory
- repair pattern learning
- benchmark leaderboard
- team workflows
- enterprise permissions
- policy-controlled autonomous maintenance
- multi-repository reasoning

These are future capabilities, not MVP requirements.

---

# 56. Final Product Definition

Devaura is complete in concept when it can reliably execute:

```text
REAL SOFTWARE FAILURE
        ↓
REAL DEVELOPMENT CONTEXT
        ↓
REAL ROOT-CAUSE ANALYSIS
        ↓
REAL CODE CHANGE
        ↓
REAL SANDBOX EXECUTION
        ↓
REAL TEST VERIFICATION
        ↓
REAL REVIEW
        ↓
REAL HUMAN APPROVAL
        ↓
REAL PULL REQUEST
```

The defining metric is not:

> "How good is Devaura at generating code?"

The defining metric is:

> **"How reliably can Devaura turn a real software failure into a verified, reviewable repair?"**

---

# 57. Source References

MCP documentation:

https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server

Use the official MCP specification and SDK documentation as the authority for protocol behavior.

When the protocol evolves, verify the current official specification before changing the MCP implementation.

---

# 58. Final Rule

**Never sacrifice correctness, security, or verifiability merely to make Devaura appear autonomous.**

The system should be autonomous where it is safe and deterministic, and human-controlled where actions can cause meaningful damage.

> **Devaura: From failure to verified fix.**
