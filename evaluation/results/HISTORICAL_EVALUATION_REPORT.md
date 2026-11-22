# Devaura Track C: Historical Real-World Open-Source Evaluation Report

**Execution Mode:** `deterministic`  
**Generated:** `2026-11-22T15:44:26.247262+00:00`  
**Total Real-World Bugs:** 2  

## 1. Summary Performance Metrics

| Metric | Value |
|---|---|
| **Localization Top-1 Accuracy** | **100.0%** |
| **Patch Generation Success** | **100.0%** |
| **Original Failure Fixed Rate** | **100.0%** |
| **Hidden Validation Test Pass Rate** | **100.0%** |
| **False Repair Rate** | **0.0%** |
| **Correct Repair Rate** | **100.0%** |
| **Regression Rate** | **0.0%** |
| **Total Tokens Consumed** | **3,619** |
| **Total Financial Cost (USD)** | **$0.0005** |

## 2. Per-Bug Breakdown

| Bug ID | Project | Category | Issue / CVE | Localized | Orig Fixed | Hidden Pass | Outcome |
|---|---|---|---|---|---|---|---|
| `HIST-001` | **flask** | Routing / URL Parsing | `Issue #2766 / CVE-2018-1000656` | ✅ | ✅ | ✅ | **CORRECT_REPAIR** |
| `HIST-002` | **requests** | Security / HTTP Redirect | `CVE-2018-18074` | ✅ | ✅ | ✅ | **CORRECT_REPAIR** |