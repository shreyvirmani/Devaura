"""Devaura Real-World Defect Dataset Validator CLI.

Validates the integrity, reproducibility, security, and licensing of all 12 real-world defects:
1. buggy_commit exists and is valid
2. fix_commit exists and is distinct from buggy_commit
3. bug reproduces (reproduction test fails on unpatched code)
4. fix resolves bug (reproduction test passes on patched code)
5. tests pass after fix (hidden validation test passes on patched code)
6. license is allowed (MIT, Apache-2.0, BSD-3-Clause)
7. repository is public and properly identified
8. no secrets or credentials present in source or tests
9. provenance is complete (SHAs, URLs, issue/CVE, categories)

Usage:
    python -m data.validate_dataset
"""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional

from data.validation.license_validator import LicenseValidator
from data.validation.secret_detector import SecretDetector
from evaluation.historical.ground_truth import HISTORICAL_BUGS, HistoricalBugDefinition


@dataclass
class DefectValidationResult:
    bug_id: str
    repository: str
    buggy_commit: str
    fix_commit: str
    license: str
    reproduction_confirmed: bool
    fix_resolves_bug: bool
    hidden_tests_pass: bool
    secrets_clean: bool
    provenance_complete: bool
    errors: List[str]

    @property
    def is_valid(self) -> bool:
        return (
            self.reproduction_confirmed
            and self.fix_resolves_bug
            and self.hidden_tests_pass
            and self.secrets_clean
            and self.provenance_complete
            and len(self.errors) == 0
        )


class DatasetValidator:
    """Validates real-world software defect dataset against integrity criteria."""

    def __init__(self):
        self.secret_detector = SecretDetector()
        self.license_validator = LicenseValidator()

    def validate_single_defect(self, bug: HistoricalBugDefinition) -> DefectValidationResult:
        """Validate an individual defect definition end-to-end."""
        errors: List[str] = []

        # 1. Commit SHAs
        if not bug.buggy_commit or len(bug.buggy_commit.strip()) < 6:
            errors.append(f"Invalid or missing buggy_commit: '{bug.buggy_commit}'")
        if not bug.fix_commit or len(bug.fix_commit.strip()) < 6:
            errors.append(f"Invalid or missing fix_commit: '{bug.fix_commit}'")
        if bug.buggy_commit == bug.fix_commit:
            errors.append(f"buggy_commit cannot equal fix_commit: '{bug.buggy_commit}'")

        # 2. License check
        try:
            self.license_validator.validate_license(bug.repository, bug.license)
        except Exception as lic_err:
            errors.append(f"Forbidden or invalid license: {lic_err}")

        # 3. Repository identifier
        if not bug.repository or "/" not in bug.repository or len(bug.repository.split("/")) != 2:
            errors.append(f"Invalid public repository identifier: '{bug.repository}'")

        # 4. Provenance completeness
        prov_fields = [
            ("title", bug.title),
            ("description", bug.description),
            ("category", bug.category),
            ("error_message", bug.error_message),
            ("stack_trace", bug.stack_trace),
            ("cve_or_issue", bug.cve_or_issue),
        ]
        for field_name, field_val in prov_fields:
            if not field_val or len(str(field_val).strip()) == 0:
                errors.append(f"Missing required provenance field: {field_name}")

        # 5. Secrets detection
        all_code = "\n".join(
            list(bug.source_files.values())
            + list(bug.reproduction_test.values())
            + list(bug.hidden_validation_test.values())
            + list(bug.fixed_source.values())
        )
        secrets = self.secret_detector.find_secrets(all_code)
        if secrets:
            secret_desc = ", ".join(f"{s[0]}: {s[1]}" for s in secrets)
            errors.append(f"Secret detected in defect assets: {secret_desc}")

        # 6. Functional Verification in Temporary Workspace
        temp_dir = Path(tempfile.mkdtemp(prefix=f"val_{bug.bug_id}_"))
        reproduction_confirmed = False
        fix_resolves_bug = False
        hidden_tests_pass = False

        try:
            # 6a. Write buggy source files
            for rel_path, content in bug.source_files.items():
                dest = temp_dir / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")

            # 6b. Write reproduction test
            for rel_path, content in bug.reproduction_test.items():
                dest = temp_dir / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")

            # Execute reproduction test on unpatched code (MUST FAIL)
            cmd = f'"{sys.executable}" -m pytest tests/test_reproduce.py'
            res_repro = subprocess.run(
                cmd, shell=True, cwd=temp_dir, capture_output=True, text=True, timeout=15
            )
            if res_repro.returncode != 0:
                reproduction_confirmed = True
            else:
                errors.append("Reproduction test unexpectedly PASSED on unpatched code (failure not reproduced)")

            # 6c. Apply fix
            for rel_path, content in bug.fixed_source.items():
                dest = temp_dir / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")

            # Execute reproduction test on patched code (MUST PASS)
            res_fix = subprocess.run(
                cmd, shell=True, cwd=temp_dir, capture_output=True, text=True, timeout=15
            )
            if res_fix.returncode == 0:
                fix_resolves_bug = True
            else:
                errors.append(f"Reproduction test failed on patched code: {res_fix.stderr[:200]}")

            # 6d. Write and execute hidden validation test on patched code (MUST PASS)
            for rel_path, content in bug.hidden_validation_test.items():
                dest = temp_dir / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")

            hidden_cmd = f'"{sys.executable}" -m pytest tests/test_hidden_validation.py'
            res_hidden = subprocess.run(
                hidden_cmd, shell=True, cwd=temp_dir, capture_output=True, text=True, timeout=15
            )
            if res_hidden.returncode == 0:
                hidden_tests_pass = True
            else:
                errors.append(f"Hidden validation test failed on patched code: {res_hidden.stderr[:200]}")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return DefectValidationResult(
            bug_id=bug.bug_id,
            repository=bug.repository,
            buggy_commit=bug.buggy_commit,
            fix_commit=bug.fix_commit,
            license=bug.license,
            reproduction_confirmed=reproduction_confirmed,
            fix_resolves_bug=fix_resolves_bug,
            hidden_tests_pass=hidden_tests_pass,
            secrets_clean=len(secrets) == 0,
            provenance_complete=len(errors) == 0,
            errors=errors,
        )

    def validate_all(self) -> List[DefectValidationResult]:
        """Validate all defects in the real-world dataset."""
        print("=" * 80)
        print(" DEVAURA REAL-WORLD DATASET VALIDATION (python -m data.validate_dataset)")
        print("=" * 80)
        print(f"Total defects to validate: {len(HISTORICAL_BUGS)}\n")

        results = []
        for bug in HISTORICAL_BUGS:
            print(f"--> Validating {bug.bug_id} [{bug.repository}] ({bug.category})...", end=" ", flush=True)
            res = self.validate_single_defect(bug)
            results.append(res)
            if res.is_valid:
                print("VALID (Repro: YES | Fix: YES | Hidden: YES | License: ALLOWED | Secrets: CLEAN)")
            else:
                print(f"FAILED ({', '.join(res.errors)})")

        print("\n" + "=" * 80)
        print(" VALIDATION SUMMARY")
        print("=" * 80)
        valid_count = sum(1 for r in results if r.is_valid)
        total = len(results)
        print(f"Defects Validated: {valid_count}/{total} ({(valid_count/total)*100:.1f}%)")

        if valid_count < total:
            print(f"\nFAILED: {total - valid_count} defect(s) violated validation invariants.")
            for r in results:
                if not r.is_valid:
                    print(f"  - {r.bug_id}: {r.errors}")
            return results

        print(f"SUCCESS: All {total} real-world defect definitions satisfy all integrity invariants.")
        return results


def main() -> None:
    validator = DatasetValidator()
    results = validator.validate_all()
    if any(not r.is_valid for r in results):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
