# Devaura — Investigation & Root Cause Localization (Phase 4)

> **Tagline:** From failure to verified fix.  
> **Layer:** Deterministic Evidence Collection, Change Locality Scoring, Bounded Investigation Loop, and Root Cause Synthesis.

---

## 1. Overview

The **Investigator Subsystem** is responsible for answering:
> *Why did this failure occur, which files and symbols are responsible, and what concrete evidence proves this conclusion?*

Devaura strictly rejects ungrounded, hallucinated claims. The Investigator operates as a **strictly read-only** closed-loop engine that translates unstructured failures into structured, ranked evidence and calibrated root-cause hypotheses.

```text
Software Failure (Trace, Test, Log, Issue)
                  ↓
         Investigation Request
                  ↓
          Evidence Collector
 (Code Intelligence + Git + Stack Parser + Test Engine)
                  ↓
          Evidence Ranker
 (Change Locality Scoring + Priority Tier Sorting)
                  ↓
       Evidence Sufficiency Gate
 (SUFFICIENT / PARTIALLY_SUFFICIENT / INSUFFICIENT)
                  ↓
         Investigator Engine
   (Bounded 5-Step Loop & Multi-Candidate Synthesis)
                  ↓
         Investigation Report
```

---

## 2. Invariants & Safety Constraints

1. **Strictly Read-Only**: The Investigator has zero write permissions. It cannot modify files, apply patches, commit to git, create branches, or open pull requests.
2. **Bounded Execution Loop**: The engine executes at most **5 iterations** and halts early once evidence sufficiency is established.
3. **No Entity Fabrication**: If a stack frame, dynamic dispatch (`getattr`), or call target cannot be statically bound in the Code Intelligence graph, it is explicitly classified as `UNRESOLVED` with low confidence.
4. **Transparent Uncertainty**: When an error is generic or ungrounded (e.g. "Something went wrong"), the system states:
   > *"Insufficient evidence to determine root cause."*
5. **No Forced Certainty**: On ambiguous caller-callee failures, multiple ranked candidates are returned with supporting evidence citations rather than pretending a single cause is guaranteed.

---

## 3. Investigation State Machine

The investigation lifecycle is governed by an explicit finite state machine:

```text
       CREATED / INVESTIGATING
                  │
                  ▼
         COLLECTING_EVIDENCE
                  │
                  ▼
            EVIDENCE_READY
                  │
                  ▼
              ANALYZING
                  │
                  ▼
         CANDIDATES_GENERATED
                  │
                  ▼
              COMPLETED

(From ANY active state ──► FAILED on unhandled error)
```

Illegal state jumps raise `InvalidStateTransitionError`.

---

## 4. Change Locality & Evidence Ranking

### 4.1 Change Locality Scoring Formula
$$\text{LocalityScore}(e) = w_{sym} \cdot S_{sym} + w_{file} \cdot S_{file} + w_{rec} \cdot S_{recency} + w_{dep} \cdot S_{dep} + w_{test} \cdot S_{test}$$

- $w_{sym} = 0.35$: Evidence touches the suspected failing symbol.
- $w_{file} = 0.25$: Evidence touches the failing source file.
- $w_{rec} = 0.20$: Commit recency decay factor $\frac{1}{1 + \text{commit\_distance}}$.
- $w_{dep} = 0.10$: Target is on the direct dependency or caller/callee path.
- $w_{test} = 0.10$: Target exercises or is exercised by the failing test suite.

### 4.2 Priority Tiers
1. `DIRECT_STACK_FRAME` (1.00)
2. `DIRECT_FAILED_TEST` (0.90)
3. `RESOLVED_CALL_RELATIONSHIP` (0.80)
4. `RECENT_DIRECT_CODE_CHANGE` (0.75)
5. `IMPORT_RELATIONSHIP` (0.65)
6. `HEURISTIC_TEST_MATCH` (0.50)
7. `GIT_CO_CHANGE` (0.35)
8. `UNRESOLVED_CALL_RELATIONSHIP` (0.25)
9. `GENERIC_LOG` (0.15)

$$\text{Relevance} = \text{PriorityBase} \times (0.6 \cdot \text{Confidence} + 0.4 \cdot \text{LocalityScore})$$

---

## 5. REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/investigations` | Initiates an investigation request with failure details. |
| `GET` | `/api/v1/investigations` | Lists all investigations. |
| `GET` | `/api/v1/investigations/{id}` | Retrieves investigation details, evidence items, and candidates. |
| `POST` | `/api/v1/investigations/{id}/run` | Executes the 5-step Investigator engine. |
| `GET` | `/api/v1/investigations/{id}/evidence` | Returns ranked evidence items ordered by relevance. |
| `GET` | `/api/v1/investigations/{id}/candidates` | Returns synthesized root-cause hypotheses. |
| `GET` | `/api/v1/investigations/{id}/timeline` | Returns the step-by-step execution audit trail. |
| `POST` | `/api/v1/investigations/{id}/approve` | Human Approval Gate for repair plan. |
| `POST` | `/api/v1/investigations/{id}/reject` | Human Approval Gate to reject or close. |

---

## 6. Evaluation Benchmark Results

Evaluated using `InvestigationEvaluator` on the deterministic fixture repository (`tests/fixtures/validation_repo/`):

- **Issue Localization Accuracy**: **100.0%**
- **Root Cause Candidate Accuracy**: **100.0%**
- **Top-1 Candidate Accuracy**: **100.0%**
- **Top-3 Candidate Accuracy**: **100.0%**
- **Evidence Retrieval Precision**: **60.0%**
- **Evidence Sufficiency Accuracy**: **100.0%**
- **False Confidence Rate**: **0.0%**
- **Unsupported Claim Rate**: **0.0%**
- **Tool Selection Accuracy**: **100.0%**
- **Average Iterations**: **5.0 / 5**
- **Average Latency**: **14.20 ms**
