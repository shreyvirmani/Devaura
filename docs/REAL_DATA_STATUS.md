# Devaura — Real Data Pipeline, Real LLM & Real-World Software Failure Status

**Document Version:** 1.1.0 (Phase 9.3 Held-Out Generalization Update)  
**Status:** ACTIVE  
**Last Updated:** November 24, 2026  
**Primary Reference:** `DEVAURA_SOURCE_OF_TRUTH.md`  
**Evaluation Report:** `docs/HELD_OUT_GENERALIZATION.md`

---

## 1. Executive Summary & Core Declaration

> **"Devaura is powered by a real external LLM and evaluated on real-world software failure data; model parameter fine-tuning has not yet been performed."**

Devaura is an MCP-native AI software maintenance and repair platform whose complete lifecycle operates as:

$$\text{Failure} \longrightarrow \text{Investigation} \longrightarrow \text{Root Cause} \longrightarrow \text{Repair Plan} \longrightarrow \text{Patch} \longrightarrow \text{Sandbox Verification} \longrightarrow \text{Human Review} \longrightarrow \text{PR}$$

All inappropriate runtime mocks, synthetic repair paths, and silent mock fallbacks (`try: real except: mock`) have been strictly removed from production and API routes. Every component in the live repair path operates against real external services and real open-source software defect data.

### Phase 9.3 Held-Out Generalization Paradigm
In Phase 9.3, Devaura established that **Held-Out Repository Generalization** (measured on unseen repositories exclusively) is the platform's primary capability KPI. The held-out test split was expanded from 3 to 13 repositories to eliminate low-sample statistical noise and evaluate true cross-repository generalization.

---

## 2. Current Implementation Status

| Component | Status | Implementation Details |
| :--- | :--- | :--- |
| **Real LLM** | **ACTIVE** | Live API integration via `GoogleGeminiProvider` (`gemini-2.5-pro` & `gemini-2.5-flash`) with dynamic provider selection, token tracking, retry exponential backoff, and full audit trail. |
| **Real GitHub** | **ACTIVE** | `GitHubClient` connected via authenticated GitHub REST & GraphQL API (`integrations/github/client.py`). Silent mock fallback strictly removed; raises `GitHubAuthRequiredError` when unauthenticated. |
| **Real Dataset** | **ACTIVE** | Curated real-world defect dataset v1.0.0 (`data/datasets/`) containing **22 reproducible defects across 22 distinct top-tier open-source repositories**. |
| **Real Training** | **INFORMATIVE** | Retrieval-enhanced reasoning and few-shot context synthesis across the training split. Parameter-level model fine-tuning has **not** been performed. |
| **Real Evaluation** | **ACTIVE** | Phase 9.3 Held-Out Benchmark (`evaluation/historical/runner.py`) running 66 repeated trials across 22 defects with air-gapped evaluator workspace and zero ground-truth leakage. |
| **Primary KPI** | **ACTIVE** | **Held-Out Generalization:** 11 / 13 (84.6%) reliable success across 13 unseen held-out test repositories (33/39 runs). |
| **Hidden Test Protection** | **ACTIVE** | Air-gapped validation tests stored exclusively in evaluator workspace (`evaluation/historical/hidden_tests/`); strictly withheld from agent repair workspaces and LLM context prompts. |
| **Real End-to-End** | **ACTIVE** | Full deterministic and live LLM pipeline executing from raw failure report through isolated sandbox verification to authenticated PR orchestration. |

---

## 3. Real-World Defect Dataset Breakdown

The dataset is generated and verified by the automated ingestion and validation pipeline (`data/`):

- **Dataset Version:** `v1.0.0`
- **Dataset Hash (SHA-256):** `f61bd74627cda2a73975c559ff73e8f6a76921e0380bed0bf6f75192254f7e58`
- **Total Real Software Defects:** 22
- **Unique Repositories:** 22
- **Verified Reproducible:** 22 / 22 (100.0%)
- **Secrets Detected:** 0 (Enforced by `SecretDetector` with automated redaction)
- **Provenance Recorded:** 100% (Enforced by `ProvenanceTracker` with immutable SHA-256 commit tracking)
- **Ground-Truth Leakage Checks:** 100% Passed (Validated by `GroundTruthValidator`)

### Repository-Level Split (Strict Zero-Overlap Invariant)

To guarantee that evaluation metrics assess generalizable repair capability rather than repository-specific memorization, all partitions are segregated strictly by **repository name**:

```
                                [22 Real-World Repositories]
                                             │
             ┌───────────────────────────────┼───────────────────────────────┐
             ▼                               ▼                               ▼
       TRAIN SPLIT (6 Repos)          VAL SPLIT (3 Repos)             HELD-OUT TEST (13 Repos)
       • pallets/flask                • tiangolo/fastapi              • pydantic/pydantic
       • psf/requests                 • sqlalchemy/sqlalchemy         • pytest-dev/pytest
       • pallets/click                • expressjs/express             • urllib3/urllib3
       • tornadoweb/tornado                                           • chalk/chalk
       • marshmallow-code/marshmallow                                 • axios/axios
       • encode/httpx                                                 • lodash/lodash
                                                                      • gin-gonic/gin
                                                                      • pallets/jinja
                                                                      • Textualize/rich
                                                                      • serde-rs/serde
                                                                      • google/guava
                                                                      • mitmproxy/mitmproxy
                                                                      • boto/botocore
```

### Multi-Ecosystem Diversity
- **Python:** 16 repositories
- **JavaScript / TypeScript:** 4 repositories (`expressjs/express`, `chalk/chalk`, `axios/axios`, `lodash/lodash`)
- **Go:** 1 repository (`gin-gonic/gin`)
- **Rust:** 1 repository (`serde-rs/serde`)
- **Java:** 1 repository (`google/guava`)

### Approved Permissive Open-Source Licenses
Every ingested defect is verified by `LicenseValidator` against an approved permissive license allowlist:
- `MIT` (14 repositories)
- `BSD-3-Clause` (5 repositories)
- `Apache-2.0` (3 repositories)

---

## 4. Phase 9.3 Evaluation Results: Held-Out Generalization

### Primary Metric (Held-Out Test Set ONLY)
- **Bug-Level Reliable Success:** **11 / 13 (84.6%)**
- **Run-Level Success:** **33 / 39 (84.6%)**
- **Localization Top-1:** **36 / 39 (92.3%)**
- **Root Cause Accuracy:** **36 / 39 (92.3%)**
- **Patch Applicability:** **36 / 39 (92.3%)**
- **False Repair Rate:** **0 / 39 (0.0%)**

### Secondary Metrics (Split Breakdown)
- **Train Split (6 Repositories):** 6 / 6 (100.0%) reliable | 18 / 18 (100.0%) runs
- **Validation Split (3 Repositories):** 3 / 3 (100.0%) reliable | 9 / 9 (100.0%) runs
- **Aggregate Suite (22 Repositories):** 20 / 22 (90.9%) reliable | 60 / 66 (90.9%) runs

### Baselines on Held-Out Test Set ONLY
- **Baseline A (Raw LLM):** 0 / 13 (0.0%) reliable
- **Baseline B (Code Intelligence):** 0 / 13 (0.0%) reliable
- **Baseline C (Full Devaura Pipeline):** **11 / 13 (84.6%)** reliable

---

## 5. Forensic Failure Analysis

1. **`HIST-004` (`pydantic/pydantic`):**
   - *Status:* `PATCH_APPLIES` $\rightarrow$ `TEST_FAILURE`.
   - *Diagnosis:* Localized to `pydantic_core/parser.py` (Rank 1). Planning succeeded. Patch generated. Patch applied cleanly. The patch prepended a comment `+# LLM defensive repair` with a leading space before the function definition, corrupting subsequent indentation and triggering a Python `IndentationError: unexpected indent`.
2. **`HIST-009` (`pytest-dev/pytest`):**
   - *Status:* `PATCH_DOES_NOT_APPLY` $\rightarrow$ `PATCH_SCOPE_ERROR`.
   - *Diagnosis:* Localization failed (Rank 3). The candidate generator hallucinated `app/service.py` as top candidate. The patch generator targeted `app/service.py` (which does not exist in pytest). Git apply failed. Disproved earlier claim of hunk context mismatch.

---

## 6. Anti-Leakage & Governance Guarantees

1. **0 Hardcoded Cheating Branches:** Exhaustive codebase audit across `agent/`, `mcp/`, and `apps/api/` confirmed 0 defect IDs or golden patch lookups.
2. **Air-Gapped Workspaces:** Agent workspace contains only buggy source files and `tests/test_reproduce.py`. `.git` history is removed. Golden fixes and hidden tests exist strictly in the evaluator workspace.
3. **Secret Redaction:** `SecretDetector` scrubs credentials prior to prompt submission. 0 secrets leaked across all runs.
4. **Tool Governance:** Autonomous PR creation, branch pushing, and patch self-approval are permanently blocked from LLM execution.
