"""Devaura Historical Real-World Dataset Builder.

Materializes the 10 historical open-source defects on disk under evaluation/historical/dataset/
Strict zero-leakage separation:
- Repositories only contain broken source code and reproducing tests.
- Hidden validation tests and golden fixes are stored in an evaluator-only directory.
"""

import json
import os
from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.historical.ground_truth import HISTORICAL_BUGS

HISTORICAL_ROOT = Path(__file__).resolve().parent
DATASET_DIR = HISTORICAL_ROOT / "dataset"
HIDDEN_TESTS_DIR = HISTORICAL_ROOT / "hidden_tests"
GOLDEN_FIXES_DIR = HISTORICAL_ROOT / "golden_fixes"


def build_historical_dataset() -> None:
    """Build the on-disk directory structure for historical real-world defects."""
    if DATASET_DIR.exists():
        shutil.rmtree(DATASET_DIR)
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    HIDDEN_TESTS_DIR.mkdir(parents=True, exist_ok=True)
    GOLDEN_FIXES_DIR.mkdir(parents=True, exist_ok=True)

    manifest_bugs = []

    for bug in HISTORICAL_BUGS:
        bug_dir = DATASET_DIR / bug.bug_id
        bug_dir.mkdir(parents=True, exist_ok=True)

        # 1. Write broken source files
        for rel_path, content in bug.source_files.items():
            file_path = bug_dir / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

        # 2. Write reproducing test
        for rel_path, content in bug.reproduction_test.items():
            file_path = bug_dir / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

        # 3. Write hidden validation test in withheld directory
        hidden_bug_dir = HIDDEN_TESTS_DIR / bug.bug_id
        hidden_bug_dir.mkdir(parents=True, exist_ok=True)
        for rel_path, content in bug.hidden_validation_test.items():
            h_path = hidden_bug_dir / rel_path
            h_path.parent.mkdir(parents=True, exist_ok=True)
            h_path.write_text(content, encoding="utf-8")

        # 4. Write golden fix in withheld directory
        golden_bug_dir = GOLDEN_FIXES_DIR / bug.bug_id
        golden_bug_dir.mkdir(parents=True, exist_ok=True)
        for rel_path, content in bug.fixed_source.items():
            g_path = golden_bug_dir / rel_path
            g_path.parent.mkdir(parents=True, exist_ok=True)
            g_path.write_text(content, encoding="utf-8")

        # 5. Metadata manifest (NO ground truth files or answers exposed to agent)
        meta = {
            "bug_id": bug.bug_id,
            "project": bug.project,
            "ecosystem": bug.ecosystem,
            "cve_or_issue": bug.cve_or_issue,
            "category": bug.category,
            "title": bug.title,
            "description": bug.description,
            "error_message": bug.error_message,
            "stack_trace": bug.stack_trace,
            "test_command": bug.test_command,
            "context_files": [],  # Strictly empty: zero ground-truth leakage
        }
        (bug_dir / "bug_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        manifest_bugs.append(meta)

    # Master manifest
    manifest_data = {
        "version": "1.0",
        "benchmark_track": "Track C (Historical Real-World Defects)",
        "total_bugs": len(manifest_bugs),
        "bugs": manifest_bugs,
    }
    (DATASET_DIR / "manifest.json").write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    print(f"Historical dataset successfully materialized with {len(manifest_bugs)} bugs at {DATASET_DIR}")


if __name__ == "__main__":
    build_historical_dataset()
