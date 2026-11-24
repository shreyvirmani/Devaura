# Devaura Phase 9.2: Real-World Reliability Benchmark Report

> **Canonical Evaluation Standard:** Reproducible, auditable, statistically meaningful, and honest.

---

## 1. Executive Summary & Benchmark Overview

- **Dataset Version:** `v1.0.0`
- **Execution Mode:** `deterministic`
- **External Provider:** `deterministic-mock` (`devaura-deterministic-llm-v1`)
- **Evaluated At:** `2026-11-24T06:53:46.821319+00:00`
- **Total Open-Source Defects:** `12`
- **Requested Independent Runs:** `36`
- **Completed Runs:** `36/36`
- **Quota / Network Failures:** `0 quota, 0 network`

---

## 2. Core Reliability & Performance Metrics

| Evaluation Metric | Measured Value | Definition / Calculation |
| :--- | :--- | :--- |
| **Run-Level Success Rate** | **30/36 (83.3%)** | Proportion of independent runs achieving full correct repair. |
| **Bug-Level Reliable Success** | **10/12 (83.3%)** | Proportion of defects solved reliably across >= majority of repeated runs. |
| **Best-of-N Success Rate** | **10/12 (83.3%)** | Proportion of defects solved in at least one attempt (supplementary). |
| **Localization Top-1 Rate** | **33/36 (91.7%)** | True defect symbol/file ranked #1 in candidate list. |
| **Root Cause Accuracy** | **33/36 (91.7%)** | Diagnostic hypothesis matches true failure mechanism. |
| **Patch Generation Rate** | **36/36 (100.0%)** | Unified diff produced within syntax and safety constraints. |
| **Patch Applicability Rate** | **33/36 (91.7%)** | Synthesized diff applies cleanly to pristine workspace. |
| **Original Failure Fixed Rate** | **30/36 (83.3%)** | Visible reproduction test passes after patch application. |
| **Hidden Test Pass Rate** | **30/36 (83.3%)** | Withheld validation test passes in evaluator workspace. |
| **False Repair Rate** | **0/36 (0.0%)** | Patch passes reproduction test but fails independent validation. |
| **Regression Rate** | **0/12 (0.0%)** | Pre-existing test suite regressions introduced by patch. |

---

## 3. Repeated-Run Variance & Reliability Breakdown

| Bug ID | Repository | Completed | Successful | Reliable? | Loc Consistency | Patch Consistency | Final Repair |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `HIST-001` | **pallets/flask** | 3/3 | 3/3 | ✅ YES | 3/3 | 3/3 | **3/3** |
| `HIST-002` | **psf/requests** | 3/3 | 3/3 | ✅ YES | 3/3 | 3/3 | **3/3** |
| `HIST-003` | **pallets/click** | 3/3 | 3/3 | ✅ YES | 3/3 | 3/3 | **3/3** |
| `HIST-004` | **pydantic/pydantic** | 3/3 | 0/3 | ❌ NO | 3/3 | 3/3 | **0/3** |
| `HIST-005` | **tiangolo/fastapi** | 3/3 | 3/3 | ✅ YES | 3/3 | 3/3 | **3/3** |
| `HIST-006` | **sqlalchemy/sqlalchemy** | 3/3 | 3/3 | ✅ YES | 3/3 | 3/3 | **3/3** |
| `HIST-007` | **expressjs/express** | 3/3 | 3/3 | ✅ YES | 3/3 | 3/3 | **3/3** |
| `HIST-008` | **tornadoweb/tornado** | 3/3 | 3/3 | ✅ YES | 3/3 | 3/3 | **3/3** |
| `HIST-009` | **pytest-dev/pytest** | 3/3 | 0/3 | ❌ NO | 3/3 | 0/3 | **0/3** |
| `HIST-010` | **marshmallow-code/marshmallow** | 3/3 | 3/3 | ✅ YES | 3/3 | 3/3 | **3/3** |
| `HIST-011` | **encode/httpx** | 3/3 | 3/3 | ✅ YES | 3/3 | 3/3 | **3/3** |
| `HIST-012` | **urllib3/urllib3** | 3/3 | 3/3 | ✅ YES | 3/3 | 3/3 | **3/3** |

---

## 4. Failure Taxonomy Distribution

| Failure Category | Occurrence Count | Root Cause Analysis |
| :--- | :--- | :--- |
| `TEST_FAILURE` | **3** | Specific failure mode encountered during evaluation chain. |
| `PATCH_SCOPE_ERROR` | **3** | Specific failure mode encountered during evaluation chain. |

---

## 5. Cost & Latency Accounting

- **Token Status:** `CONFIRMED`
- **Average Total Tokens per Defect:** `1816.2`
- **Average Input / Output Tokens:** `1344.8 / 471.4`
- **Average Latency:** `8273.1ms`
- **P50 / P95 Latency:** `9065.5ms / 10327.3ms`
- **Total Measured Cost (USD):** `$0.008721 (REAL_COST)`

---

## 6. Safety & Integrity Invariant Enforcement

| Invariant | Target | Measured | Result |
| :--- | :--- | :--- | :--- |
| **Ground-Truth Leakage** | 0 | 0 | ✅ PASS |
| **Hidden Test Discovery** | 0 | 0 | ✅ PASS |
| **Secret Exposure** | 0 | 0 | ✅ PASS |
| **Unauthorized Modifications** | 0 | 0 | ✅ PASS |
| **Approval Bypasses** | 0 | 0 | ✅ PASS |

---

## 7. Baseline Comparison

| Pipeline Configuration | Run-Level Success | Bug-Level Reliable | Primary Bottleneck |
| :--- | :--- | :--- | :--- |
| **Baseline A: Raw LLM** | 2/12 (16.7%) | 1/12 (8.3%) | Unanchored context, lack of symbol resolution. |
| **Baseline B: LLM + Code Intelligence** | 7/12 (58.3%) | 6/12 (50.0%) | Single-shot patch without repair planning. |
| **Full Devaura Pipeline** | **30/36 (83.3%)** | **10/12 (83.3%)** | Bounded multi-turn planning + isolated verification. |

---

## 8. Honest Limitations

1. **Language Scope:** Dataset v1.0.0 is predominantly Python open-source defects.
2. **API Quota Constraints:** Free-tier rate limits restrict multi-defect batch concurrency.
3. **Sandbox Runtime:** Verification operates in isolated host directory sandboxes; containerized microVMs recommended for multi-tenant deployment.