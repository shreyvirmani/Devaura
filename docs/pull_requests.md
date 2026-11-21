# Devaura — Phase 7: Pull Request Orchestration & Human Review

> **Devaura Tagline:** From failure to verified fix.
>
> **Core Pipeline Milestone:** Verified Repair $\to$ Git State Validation $\to$ Branch Preparation $\to$ Commit Preparation $\to$ PR Metadata Synthesis $\to$ Cryptographic Human Review Gate $\to$ Remote Pull Request Creation $\to$ PR Monitoring.

---

## 1. Architectural Overview

Phase 7 delivers the final transition in Devaura's automated maintenance pipeline: translating an isolated, sandbox-verified code repair (`VerifiedRepairResult`) into an auditable, peer-reviewable Pull Request on a remote Git provider (such as GitHub) without sacrificing human control, repository safety, or patch integrity.

```text
Phase 6: VERIFIED REPAIR
         ↓
Phase 7: PR Context Builder
         ↓
Git Working Tree Validation (0 Unverified Mutations)
         ↓
Dedicated Branch Creation (devaura/repair/{repair_id[:8]})
         ↓
Scoped Repair Commit
         ↓
PR Metadata Synthesis (Summary, Root Cause, Verification Evidence)
         ↓
HUMAN APPROVAL GATE (Cryptographic HMAC-SHA256 Token)
  ├─ Agent Self-Approval: STRICTLY PROHIBITED (403 Forbidden)
  └─ Token Expiration & Nonce Binding (1-hour window)
         ↓
Remote Git Provider (GitHub REST API / In-Memory Mock)
         ↓
Pull Request Created (Open / Draft)
         ↓
CI & Peer-Review Status Monitoring
```

---

## 2. Core Architectural Invariants

### 1. Isolated Dedicated Repair Branches
- All PRs are created exclusively on dedicated feature branches named according to the strict specification:
  $$\text{branch\_name} = \texttt{"devaura/repair/"} + \text{repair\_id}[:8]$$
- No modifications, direct commits, or direct pushes are ever permitted against the base branch (`main`, `master`, `release/*`, `develop`). Any attempt immediately raises `SecurityBlockError`.

### 2. Zero Post-Verification Mutation Guarantee
- The patch hash applied to the branch must exactly match `VerifiedRepairResult.final_patch_hash`.
- No post-verification code edits, formatting changes, or re-linting are allowed between sandbox verification and PR creation.
- If the working tree contains unverified or uncommitted dirty files, staging and commit creation are aborted.

### 3. Independent Cryptographic Human Authorization Gate
- Prior Phase 5/6 repair approvals **never** carry over to PR creation.
- A human operator must explicitly authorize the PR via `POST /api/v1/repairs/{id}/pr/approve`.
- The human authorization gate computes an HMAC-SHA256 signature binding:
  $$\text{HMAC-SHA256}(\text{repair\_id} + \text{patch\_hash} + \text{base\_revision} + \text{repair\_branch} + \text{repository} + \text{operation})$$
- The token is formatted as `pr-auth-{token_bytes}` with a strict 1-hour expiration.
- Autonomous agent self-approval (`devaura-agent`, `autonomous-loop`, `system-bot`) is strictly rejected with `403 Forbidden` (`PRApprovalRequiredError`).

### 4. Base Revision Drift Detection
- Before pushing the branch or creating the pull request, the Git provider queries the remote default branch.
- If the remote base SHA has diverged from `VerifiedRepairResult.base_revision`, the operation halts with `BaseRevisionChangedError` (HTTP 409 Conflict), requiring re-verification before PR creation.

### 5. Sensitive File Exclusion & Scope Guard
- PR context generation scans all changed files against dangerous patterns:
  - `.env*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa`, `id_ed25519`, `credentials.*`, `secrets.*`
  - Path traversal indicators (`../`, `..\\`)
- Any detection triggers `SecurityBlockError` and halts PR preparation.

### 6. Idempotency & Conflict Safety
- If a pull request for the branch already exists on the Git provider, `PullRequestAlreadyExistsError` is raised (HTTP 409 Conflict), returning the existing PR number and URL rather than duplicating work.
- Autonomous merging, force pushing, and production deployment are strictly out of scope.

---

## 3. Subsystem Architecture

### 3.1 Git Provider Abstraction (`integrations/github/`)
- **`GitProvider` ABC (`provider.py`)**: Abstract provider defining the interface:
  - `get_default_branch(owner, repo) -> BranchInfo`
  - `create_branch(owner, repo, branch_name, from_sha) -> BranchInfo`
  - `push_branch(owner, repo, branch_name, commit_sha, force) -> BranchInfo`
  - `create_pull_request(payload) -> PullRequestResult`
  - `get_pull_request(owner, repo, pr_number) -> PullRequestResult`
  - `get_ci_status(owner, repo, commit_sha) -> CIStatusInfo`
  - `get_review_status(owner, repo, pr_number) -> ReviewInfo`
  - `close_pull_request(owner, repo, pr_number) -> PullRequestResult`
- **`GitHubClient` (`client.py`)**: Production asynchronous GitHub REST API implementation using `httpx.AsyncClient` with secure token headers and authorization header redaction in logging.
- **`MockGitProvider` (`mock_provider.py`)**: Deterministic in-memory provider supporting failure simulation (auth error, rate limit, network timeout, merge conflict, base revision divergence) and idempotency checks.

### 3.2 PR State Machine (`agent/pr/state_machine.py`)
Governs the lifecycle through immutable state transitions:
```text
PR_NOT_PREPARED
  ↓ prepare_pull_request()
PR_PREPARING
  ↓ context built
AWAITING_PR_APPROVAL
  ├─ reject_pull_request() ───────────────→ PR_REJECTED (terminal)
  └─ authorize_pull_request()
       ↓
     PR_APPROVED
       ├─ git dirty / security error ────→ PR_BLOCKED_GIT_STATE (terminal)
       ├─ base revision changed ─────────→ PR_BLOCKED_BASE_CHANGED (terminal)
       └─ execute_pull_request_creation()
            ↓
          PR_CREATING
            ├─ creation failed ───────────→ PR_CREATION_FAILED (terminal)
            └─ created successfully
                 ↓
               PR_CREATED
                 ├─ CI/reviews active ────→ PR_MONITORING
                 ├─ human closes ─────────→ PR_CLOSED
                 └─ human merges (remote) → PR_MERGED
```

### 3.3 PR Context Builder (`agent/pr/context_builder.py`)
Ingests `VerifiedRepairResult` and `RepairRecord`:
- Validates verification status is `VERIFIED` and all checks passed.
- Enforces strict patch hash match.
- Checks file scope and path safety.
- Formulates conventional commit message: `fix({scope}): repair verified issue {repair_id[:8]}`.
- Synthesizes professional Markdown PR description detailing:
  - **Summary**: Concise description of the fix.
  - **Diagnosed Root Cause**: Provenance from Phase 4 investigation.
  - **Verification Evidence**: Test results, exit codes, durations, linter, and typechecker logs from Phase 6.
  - **Human Authorization**: Approver email and timestamp.

### 3.4 Git State Manager (`agent/pr/git_manager.py`)
Executes porcelain Git CLI operations inside the workspace:
- Verifies working tree cleanliness (`git status --porcelain`).
- Creates and checks out isolated branch `devaura/repair/{repair_id[:8]}`.
- Stages only allowlisted files (`git add <file>`).
- Commits with structured commit message and committer metadata.

---

## 4. MCP Server Tools (`mcp/server/devaura_server.py`)

Phase 7 registers 10 native MCP tools, bringing the total platform tools to 37:

| Tool Name | Risk Level | Description |
|:---|:---|:---|
| `get_pr_context` | SAFE | Retrieve current PR preparation context and metadata |
| `get_pull_request` | SAFE | Retrieve details for an existing pull request |
| `get_pull_request_history` | SAFE | Retrieve PR creation and status transition event history |
| `get_pr_status` | SAFE | Query live CI checks and human review status from Git provider |
| `prepare_pull_request` | CONTROLLED | Validate verified repair and synthesize PR metadata |
| `prepare_repair_branch` | CONTROLLED | Create and checkout isolated branch `devaura/repair/{repair_id[:8]}` |
| `prepare_repair_commit` | CONTROLLED | Stage verified files and generate repair commit |
| `request_pr_approval` | CONTROLLED | Generate PR approval request and notify human reviewer |
| `push_repair_branch` | DANGEROUS | Push repair branch to remote repository (protected branches blocked) |
| `create_pull_request` | DANGEROUS | Create pull request on Git provider (requires HMAC approval token) |

---

## 5. REST API Specification

Mounted under `/api/v1`:

- `POST /api/v1/repairs/{repair_id}/pr/prepare`: Ingests verified repair, prepares context and PR metadata.
- `GET  /api/v1/repairs/{repair_id}/pr/context`: Queries current PR preparation context.
- `POST /api/v1/repairs/{repair_id}/pr/approve`: Submits human authorization and returns cryptographic HMAC token.
- `POST /api/v1/repairs/{repair_id}/pr/reject`: Records human rejection and halts PR workflow.
- `POST /api/v1/repairs/{repair_id}/pr/create`: Validates HMAC token, pushes branch, and opens PR on Git provider.
- `GET  /api/v1/repairs/{repair_id}/pr`: Fetches PR record details and provider metadata.
- `GET  /api/v1/repairs/{repair_id}/pr/status`: Queries live CI/CD and review status.
- `GET  /api/v1/repairs/{repair_id}/pr/history`: Returns audit timeline of all PR events.
- `GET  /api/v1/pull-requests`: Lists all pull requests across all repositories.

---

## 6. Verification & Evaluation Results

- **Unit & Property Test Cases (`tests/test_pr_cases.py`)**: **24 / 24 PASSING**
- **Benchmark Evaluation Suite (`tests/test_pr_benchmark.py`)**: **4 / 4 PASSING**
- **End-to-End API Integration Suite (`tests/test_pr_integration.py`)**: **2 / 2 PASSING**
- **Live GitHub E2E Test (`tests/e2e/test_github_pr.py`)**: Guarded by `RUN_GITHUB_E2E=1` (1 skipped when unset).
- **Full Devaura Test Suite**: **128 / 128 PASSING (100%)**
- **Next.js Production Build**: **0 errors**, type-safe, static generation 10/10 pages.
