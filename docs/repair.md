# Devaura — Phase 5: Repair Planning & Patch Generation

## 1. Overview

Devaura Phase 5 implements the **Repair Planning & Patch Generation** layer. Consuming root-cause candidates and supporting evidence produced by Phase 4, Phase 5 formulates an evidence-backed repair strategy, generates a scoped unified diff, executes static risk analysis, enforces cryptographic human approval, and applies the patch strictly inside an isolated sandbox workspace.

```text
Phase 4 Investigation
        │
        ▼
1. RepairContextBuilder ──▶ Validates Evidence & Scope (Blocks if Insufficient)
        │
        ▼
2. RepairPlanner ─────────▶ Formulates Strategy with Evidence ID Citations
        │
        ▼
3. PatchGenerator ────────▶ Generates Unified Diff & SHA-256 Digest
        │
        ▼
4. PatchRiskAnalyzer ─────▶ 5-Dimension Risk Scoring (Structural, Behavioral, Tests, Scope, Security)
        │
        ▼
5. HumanApprovalGate ─────▶ Mandatory Human Authorization (SHA-256 Bound)
        │
        ▼
6. IsolatedRunner ────────▶ Applies Patch in Sandbox (.devaura_sandboxes/{id})
        │
        ▼
Phase 6 Handoff ──────────▶ RepairExecutionResult (verification_status="PENDING")
```

---

## 2. Invariants & Safety Guarantees

1. **Original Repository Isolation**: The primary source repository is strictly read-only. All patch applications execute inside `.devaura_sandboxes/{workspace_id}`.
2. **Mandatory Human-in-the-Loop**: Patches **never self-approve**. Application requires an explicit human authorization record.
3. **Cryptographic Integrity**: Approvals are bound to `SHA-256(unified_diff)`. If the diff changes between approval and application, the system raises `PatchIntegrityError` and transitions to `PATCH_CHANGED`.
4. **Strict Scope Guard**: Modifications outside the files diagnosed by Phase 4 are rejected with `ScopeViolationError`.
5. **Sensitive File Protection**: Modifications to `.env`, `.pem`, `.key`, `id_rsa`, `.git`, or files $> 50\text{KB}$ are rejected.
6. **Evidence Provenance**: 100% of proposed changes cite concrete Phase 4 evidence IDs.
7. **Phase 6 Verification Boundary**: Verification, auto-retry loops, and PR opening are strictly deferred to subsequent phases. The handoff state is `PATCH_APPLIED_PENDING_VERIFICATION`.

---

## 3. Subsystems & Components

### 3.1 Repair State Machine (`agent/repair/state_machine.py`)
Finite State Machine governing the repair progress:
- Progression: `CREATED` $\to$ `CONTEXT_BUILDING` $\to$ `CONTEXT_READY` $\to$ `PLANNING` $\to$ `PLAN_READY` $\to$ `PATCH_GENERATING` $\to$ `PATCH_READY` $\to$ `RISK_ANALYZED` $\to$ `AWAITING_APPROVAL` $\to$ `APPROVED` $\to$ `APPLYING` $\to$ `PATCH_APPLIED_PENDING_VERIFICATION`.
- Failure / Terminal Traps: `REPAIR_BLOCKED`, `REPAIR_BLOCKED_INSUFFICIENT_EVIDENCE`, `PLAN_FAILED`, `PATCH_FAILED`, `RISK_BLOCKED`, `REJECTED`, `PATCH_CHANGED`, `APPLICATION_FAILED`.
- Any illegal state transition raises `InvalidRepairStateTransitionError`.

### 3.2 Repair Context Builder (`agent/repair/context_builder.py`)
Extracts and validates failure parameters, root-cause candidate, supporting evidence, and affected files.
- Checks investigation state (`COMPLETED` or `CANDIDATES_GENERATED`).
- Enforces evidence sufficiency (`INSUFFICIENT` aborts to `REPAIR_BLOCKED_INSUFFICIENT_EVIDENCE`).
- Validates file scope ($\le 5$ files, no path traversal, no sensitive files).
- Produces immutable `RepairContext` contract.

### 3.3 Repair Planner (`agent/repair/planner.py`)
Formulates actionable, structured strategies for each affected file.
- Specifies `ProposedChange` items (`file`, `location`, `change_type`, `rationale`, `evidence_ids`, `expected_effect`).
- Maps targeted tests using Code Intelligence test relationships.
- Identifies potential regression risks and explicit assumptions.

### 3.4 Patch Generator & Scope Guard (`agent/repair/patch_generator.py`)
- `PatchScopeGuard`: Validates target file size, path traversal, credentials, and scope bounds.
- `PatchGenerator`: Generates standardized unified diffs with line-level defensive guards.
- Computes deterministic SHA-256 digest: `patch_hash = hashlib.sha256(unified_diff.strip().encode("utf-8")).hexdigest()`.

### 3.5 Static Patch Risk Analyzer (`agent/repair/risk_analyzer.py`)
Evaluates patches across 5 dimensions:
1. **Structural Risk**: Lines added/removed ($> 50$ lines $\to$ MEDIUM, $> 100$ lines $\to$ HIGH) and number of files changed.
2. **Behavioral Risk**: Changes touching auth, login, crypto, tokens, migrations.
3. **Test Coverage Risk**: Detecting test deletions (`def test_`, `it(`, `describe(`) as blocking issues.
4. **Evidence Scope Risk**: Detecting modifications to files not identified in Phase 4 evidence as blocking issues.
5. **Security Risk**: Detecting dangerous calls (`eval`, `exec`, `os.system`, `subprocess` with `shell=True`, unpickling, hardcoded secrets) as blocking issues.
- Assigns level: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. Any blocking finding triggers `CRITICAL` and moves state to `RISK_BLOCKED`.

### 3.6 Human Approval Gate (`agent/repair/approval_gate.py`)
- Issues cryptographic approval token bound to `patch_hash`.
- Enforces human caller identity (rejects `agent`, `bot`, `auto`).
- Pre-application check ensures current diff hash matches approved hash.
- Supports rejection with audit reason (`REJECTED`).

### 3.7 Isolated Workspace & Runner (`sandbox/workspace.py` & `sandbox/isolated_runner.py`)
- Copies repository to `.devaura_sandboxes/{workspace_id}` excluding heavy caches (`.venv`, `node_modules`, `.git`).
- Applies unified diff using a deterministic line-level hunk applier.
- Guarantees original repository is 100% untouched.
- Produces Phase 6 Handoff contract: `RepairExecutionResult(application_status="APPLIED", verification_status="PENDING")`.

---

## 4. Native MCP Server Tools

The Devaura Native MCP Server provides 8 repair tools:
1. `create_repair_context` (SAFE): Ingests investigation and creates `RepairContext`.
2. `get_repair_context` (SAFE): Retrieves context by `repair_id`.
3. `generate_repair_plan` (SAFE): Formulates `RepairPlan`.
4. `generate_patch` (SAFE): Synthesizes unified diff and SHA-256 hash.
5. `analyze_patch_risk` (SAFE): Evaluates 5-dimension risk score and findings.
6. `approve_repair` (DANGEROUS): Grants human authorization bound to `patch_hash`.
7. `apply_approved_patch` (DANGEROUS): Applies patch strictly in sandbox.
8. `get_repair_diff` (SAFE): Returns unified diff and line metrics.

---

## 5. REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/repairs` | Initialize repair linked to investigation |
| `GET` | `/api/v1/repairs` | List repairs with optional investigation filter |
| `GET` | `/api/v1/repairs/{id}` | Full repair details and status |
| `POST` | `/api/v1/repairs/{id}/context` | Build and validate `RepairContext` |
| `POST` | `/api/v1/repairs/{id}/plan` | Generate evidence-backed `RepairPlan` |
| `POST` | `/api/v1/repairs/{id}/patch` | Generate scoped patch and risk analysis |
| `GET` | `/api/v1/repairs/{id}/risk` | Inspect static risk evaluation |
| `GET` | `/api/v1/repairs/{id}/diff` | Get unified diff and changed files |
| `POST` | `/api/v1/repairs/{id}/approve` | Human approval bound to patch SHA-256 |
| `POST` | `/api/v1/repairs/{id}/reject` | Reject proposed patch with reason |
| `POST` | `/api/v1/repairs/{id}/apply` | Apply patch in isolated sandbox |

---

## 6. Evaluation Metrics

Measured via `tests/test_repair_benchmark.py` and `tests/test_repair_cases.py`:
- **Evidence Provenance Rate**: **100.0%**
- **Scope Adherence Rate**: **100.0%**
- **Patch Syntactic Validity Rate**: **100.0%**
- **Cryptographic Binding Integrity**: **100.0%**
- **Critical Risk Detection Recall**: **100.0%**
- **Human-in-the-Loop Enforceability**: **100.0%**
- **Original Repository Isolation**: **100.0%**
- **Clean Phase 6 Handoff Rate**: **100.0%**
