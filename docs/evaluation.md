# Devaura Evaluation Framework & Benchmarking

## 1. Evaluation Methodology

Devaura is designed with rigorous quantitative evaluation metrics. An AI maintenance system cannot rely on subjective self-reporting.

### Core Metrics

1. **Issue Localization Accuracy**:
   - Percentage of investigations where the true faulty file and function are present in `affected_files` and `affected_symbols`.
2. **Root Cause Diagnosis Accuracy**:
   - Semantic alignment score between Devaura's diagnosis and ground-truth issue resolution.
3. **First-Pass Patch Success Rate**:
   - Percentage of issues resolved on attempt 1 with 100% test pass rate.
4. **Iterative Repair Success Rate**:
   - Percentage of issues resolved within the maximum allowed 3 attempts.
5. **Regression Rate**:
   - Percentage of patches that pass new tests but cause regressions in existing pre-fix test suites. Target: < 1%.
6. **Tool Selection Precision & Efficiency**:
   - Ratio of relevant MCP tool invocations to extraneous calls.
7. **Token Budget & Cost Efficiency**:
   - Total prompt, completion, and tool tokens consumed per verified repair.
8. **End-to-End Latency**:
   - Mean wall-clock time from failure ingestion to ready pull request.

---

## 2. Benchmark Dataset Structure

The benchmark suite (`evaluation/benchmarks/`) contains reproducible failure scenarios covering Python, TypeScript, and JavaScript:

```
evaluation/benchmarks/
├── dataset.json
└── fixtures/
    ├── bug_001_auth_token_parsing/
    ├── bug_002_off_by_one_pagination/
    ├── bug_003_unhandled_null_pointer/
    ├── bug_004_async_race_condition/
    └── ...
```

Each benchmark scenario schema:
```json
{
  "id": "bug_001",
  "repository": "mock-org/auth-service",
  "base_commit": "7f9a12c",
  "issue": {
    "title": "Malformed JWT header raises unhandled 500",
    "body": "..."
  },
  "expected_affected_files": ["src/auth/jwt.py"],
  "expected_root_cause_keywords": ["jwt", "split", "bearer", "header", "indexerror"],
  "validation_command": "pytest tests/test_jwt.py",
  "regression_command": "pytest"
}
```

---

## 3. Automated Benchmark Runner

The benchmark runner executes Devaura against each scenario in a completely isolated container, recording metrics into an immutable eval run ledger.
