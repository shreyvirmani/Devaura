# Devaura Agent Subsystem Specifications

## 1. Modular Architecture Overview

Rather than deploying a diffuse swarm of opaque agents, Devaura operates through a unified orchestrator governing five strictly defined functional phases:

```
                  ┌──────────────────────┐
                  │  DevauraOrchestrator │
                  └──────────┬───────────┘
                             │
     ┌───────────────┬───────┴───────┬───────────────┐
     ▼               ▼               ▼               ▼
Investigator      Planner       RepairEngine      Verifier
     │                               │               │
     └───────────────┬───────────────┴───────────────┘
                     ▼
                 Reviewer
```

---

## 2. Investigator Subsystem

### Inputs
- Source Issue / PR / CI failure identifier.
- Repository identifier, default branch, clone URL.

### Responsibilities
1. Queries GitHub MCP Server to fetch issue body, comments, pull request context, commit hash, and workflow logs.
2. Interrogates Code Intelligence layer:
   - Identifies candidate files and symbols using ripgrep keyword search and AST parser.
   - Extracts recent git history and blame for suspect files.
   - Discovers existing test files linked to targeted symbols.
3. Formulates structured diagnostic evidence.

### Structured Output Contract
```json
{
  "investigation_id": "inv_01hx...",
  "root_cause": "Detailed, evidence-backed explanation of the underlying software defect",
  "confidence": 0.92,
  "affected_files": ["src/auth/middleware.py", "src/auth/jwt.py"],
  "affected_symbols": ["decode_auth_token", "authenticate_request"],
  "evidence": [
    {
      "source": "ci_log",
      "detail": "ValueError: Invalid payload structure raised at middleware.py:48"
    },
    {
      "source": "git_blame",
      "detail": "Commit a1b2c3d changed decode signature without updating caller"
    }
  ],
  "related_tests": ["tests/test_auth.py"],
  "risk": "medium"
}
```

---

## 3. Repair Planner

### Inputs
- Diagnostic output from the Investigator.
- Source code contents of affected files and related test files.

### Responsibilities
1. Designs a minimal, surgical repair strategy targeting root cause.
2. Identifies exact files to modify and new regression test specifications.
3. Computes estimated risk level (`low`, `medium`, `high`).
4. Emits plan and halts execution until human operator issues an approval.

### Structured Output Contract
```json
{
  "plan_id": "plan_01hx...",
  "objective": "Safely validate incoming token header format prior to decode call",
  "changes": [
    {
      "file": "src/auth/middleware.py",
      "action": "modify",
      "reason": "Ensure Authorization header matches Bearer format and contains 3 token segments"
    },
    {
      "file": "tests/test_auth.py",
      "action": "add_test",
      "reason": "Assert malformed bearer tokens return HTTP 401 without throwing 500"
    }
  ],
  "risk": "medium",
  "confidence": 0.89
}
```

---

## 4. Repair Engine & Patch Application

### Inputs
- Approved Repair Plan.
- Repository codebase in isolated sandbox.

### Responsibilities
1. Generates unified diff patch files.
2. Validates patch grammar and integrity.
3. Applies patch in temporary sandbox workspace.
4. If patch rejects, attempts clean fuzzy line application or regenerates diff.

---

## 5. Verification Engine

### Inputs
- Patched sandbox workspace.
- Test and linter commands identified during repository analysis.

### Responsibilities
1. Runs test suite (e.g., `pytest -v`, `npm test`).
2. Runs linter (e.g., `ruff check`, `eslint`).
3. Runs type checker (e.g., `mypy`, `tsc`).
4. Formats execution outcome into normalized JSON.
5. If verification fails, extracts failure trace and triggers Repair Loop iteration (max 3 attempts).

### Normalized Verification Report
```json
{
  "attempt_number": 1,
  "status": "passed",
  "tests": {
    "status": "passed",
    "passed": 48,
    "failed": 0,
    "duration_s": 3.42
  },
  "lint": {
    "status": "passed",
    "warnings": 0
  },
  "typecheck": {
    "status": "passed",
    "errors": 0
  }
}
```

---

## 6. Reviewer Subsystem

An independent review pass that evaluates the verified patch against repository conventions:
- Checks whether unrelated files or comments were modified.
- Checks if patch introduces security risks or regressions.
- Approves patch for final human sign-off before PR creation.
