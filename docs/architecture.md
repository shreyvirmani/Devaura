# Devaura System Architecture

## 1. Overview & Vision

Devaura is an **MCP-native AI software maintenance and repair platform**. Its objective is to transform detected failures (CI/CD test errors, GitHub issues, runtime exceptions, linter violations) into verified, reproducible code fixes that undergo automated testing, linting, typechecking, and an independent review pass before requesting human approval to open a pull request.

The core operational paradigm is:
```
Detect -> Understand -> Plan -> Repair -> Verify -> Review -> Explain
```

## 2. High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph UI ["User Interface (Next.js 15)"]
        Dashboard["Dashboard & Metrics"]
        RepoView["Repository Explorer"]
        InvestigationView["Issue & CI Failure Workspace"]
        RepairWorkspace["Repair Diff & Verification Studio"]
        MCPServerView["MCP Server & Tool Hub"]
    end

    subgraph API ["Devaura API (FastAPI / Python 3.12)"]
        Router["REST & WebSocket Endpoints"]
        Auth["Auth & Security Context"]
        Orchestrator["Agent Orchestrator"]
        StateEngine["Finite State Machine"]
    end

    subgraph CoreAgent ["Agent Subsystems"]
        Investigator["Investigator Subsystem"]
        Planner["Repair Planner"]
        RepairEngine["Repair Engine & Patch Validator"]
        Verifier["Verification Engine"]
        Reviewer["Independent Reviewer"]
    end

    subgraph MCPLayer ["MCP Client & Registry Layer"]
        Registry["MCPServerRegistry"]
        ClientPool["MCP Client Pool (STDIO / SSE / HTTP)"]
        Policy["Tool Policy & Permission Gate (SAFE/CONTROLLED/DANGEROUS)"]
    end

    subgraph MCPServers ["Connected MCP Servers"]
        GitHubMCP["GitHub MCP Server (Issues, PRs, CI Runs)"]
        DevauraMCP["Devaura Native MCP Server (AST, Git, Search, Sandbox)"]
        ExtMCP["External Ecosystem MCP Servers"]
    end

    subgraph Sandbox ["Execution Sandbox"]
        DockerEnv["Isolated Execution Environment"]
        TestRunner["Pytest / Jest / Lint / Typecheck Runner"]
    end

    subgraph Storage ["Persistence"]
        Postgres[(PostgreSQL / SQLite Storage)]
        KnowledgeGraph[(Repository Symbol & Dependency Graph)]
    end

    UI <--> Router
    Router <--> Orchestrator
    Orchestrator --> StateEngine
    Orchestrator --> Investigator
    Orchestrator --> Planner
    Orchestrator --> RepairEngine
    Orchestrator --> Verifier
    Orchestrator --> Reviewer

    CoreAgent <--> Registry
    Registry <--> Policy
    Policy <--> ClientPool
    ClientPool <--> GitHubMCP
    ClientPool <--> DevauraMCP
    ClientPool <--> ExtMCP

    RepairEngine --> Sandbox
    Verifier --> Sandbox
    Orchestrator <--> Postgres
    DevauraMCP <--> KnowledgeGraph
```

## 3. Finite State Machine (Agent Lifecycle)

The agent does not operate in an unconstrained loop. State transitions are strictly enforced:

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> INVESTIGATING : Start Investigation
    INVESTIGATING --> DIAGNOSED : Root Cause Identified
    DIAGNOSED --> PLAN_READY : Structured Plan Formed
    PLAN_READY --> WAITING_FOR_APPROVAL : Awaiting Human Approval
    WAITING_FOR_APPROVAL --> REPAIRING : Approved
    WAITING_FOR_APPROVAL --> IDLE : Rejected / Cancelled
    REPAIRING --> VERIFYING : Patch Applied
    VERIFYING --> REVIEWING : Tests & Checks Passed
    VERIFYING --> REPAIRING : Verification Failed (Attempt < 3)
    VERIFYING --> REPAIR_FAILED : Max Attempts (3) Reached
    REVIEWING --> WAITING_FOR_PR_APPROVAL : Independent Review Approved
    REVIEWING --> REPAIR_FAILED : Review Rejected Findings
    WAITING_FOR_PR_APPROVAL --> PR_CREATED : Human Approved PR
    WAITING_FOR_PR_APPROVAL --> COMPLETED : Branch Staged Only
    PR_CREATED --> COMPLETED
    REPAIR_FAILED --> COMPLETED
    COMPLETED --> [*]
```

## 4. Subsystem Responsibilities

### 4.1 Orchestrator
- Coordinates state transitions across the life cycle.
- Maintains the execution context, tokens consumed, tool execution traces, and audit logs.
- Dispatches execution tasks to specialized subsystems.

### 4.2 Investigator
- Ingests issue descriptions, stack traces, comments, commit history, and CI logs via MCP.
- Performs multi-tier code searches (ripgrep, exact AST token matching, symbol lookups).
- Produces an evidence-backed diagnosis detailing `root_cause`, `confidence`, `affected_files`, `affected_symbols`, and `risk`.

### 4.3 Repair Planner
- Formulates a minimal, non-destructive repair specification.
- Details atomic changes per file, rationale, and preventative regression tests.
- Halts execution at the Human Approval Gate before touching code.

### 4.4 Repair Engine & Patch Application
- Generates targeted unified diffs.
- Syntactically parses and validates patches before application.
- Executes modifications exclusively within an isolated sandbox.

### 4.5 Verifier
- Executes unit tests, integration tests, linter checks, and typechecks.
- Normalizes disparate test tool outputs into standard structured reports (`passed`, `failed`, `skipped`, `duration`).
- Feeds failures back into the Repair Engine for up to 3 iterative attempts.

### 4.6 Reviewer
- An independent validation pass ensuring that patches address the root cause without regressions, security flaws, or style violations.
