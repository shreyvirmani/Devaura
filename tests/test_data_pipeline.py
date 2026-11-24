"""Devaura Real-World Data Ingestion & Pipeline Unit Tests.

Validates:
1. LicenseValidator for permissive vs proprietary licensing
2. SecretDetector for automated token & credential catching
3. GroundTruthValidator for prompt leakage detection
4. RepositorySplitter for strict repository-level isolation (zero leakage)
5. DatasetBuilder for dataset versioning, hashing, and schema validation
6. GitHubIngestionService error handling and provenance preservation
"""

import json
from pathlib import Path
import pytest

from data.datasets.builder import DatasetBuilder
from data.ingestion.github_ingest import GitHubIngestionError, GitHubIngestionService
from data.normalization.normalizer import BugFixRecord, DataNormalizer
from data.provenance.provenance_tracker import ProvenanceRecord, ProvenanceTracker
from data.splits.repository_splitter import RepositoryLeakageError, RepositorySplitter
from data.validation.ground_truth_validator import GroundTruthLeakageError, GroundTruthValidator
from data.validation.license_validator import LicenseValidationError, LicenseValidator
from data.validation.secret_detector import SecretDetectedError, SecretDetector


class TestLicenseValidation:
    """Verifies that only approved permissive open-source licenses are admitted."""

    def test_approved_permissive_licenses(self):
        assert LicenseValidator.is_permissive("MIT")
        assert LicenseValidator.is_permissive("Apache-2.0")
        assert LicenseValidator.is_permissive("BSD-3-Clause")
        assert LicenseValidator.is_permissive("BSD-2-Clause")
        assert LicenseValidator.is_permissive("ISC")
        assert LicenseValidator.is_permissive("Python-2.0")

    def test_forbidden_proprietary_licenses(self):
        assert not LicenseValidator.is_permissive("Proprietary")
        assert not LicenseValidator.is_permissive("All Rights Reserved")
        assert not LicenseValidator.is_permissive("UNKNOWN")
        assert not LicenseValidator.is_permissive("")

        with pytest.raises(LicenseValidationError):
            LicenseValidator.validate_license("internal/secret-repo", "Proprietary")


class TestSecretDetection:
    """Verifies scanning and redaction of credentials in ingested data."""

    def test_detect_github_token(self):
        text = "Repo setup: token = ghp_1234567890abcdefghijklmnopqrstuvwxyzAB"
        findings = SecretDetector.find_secrets(text)
        assert len(findings) > 0
        assert findings[0][0] == "GITHUB_TOKEN"

        with pytest.raises(SecretDetectedError):
            SecretDetector.assert_clean("commit message", text)

    def test_detect_google_api_key(self):
        text = "key: AIzaSyD9876543210ZYXWVUTSRQPONMLKJIHGF"
        findings = SecretDetector.find_secrets(text)
        assert len(findings) > 0
        assert findings[0][0] == "GOOGLE_API_KEY"

    def test_detect_openai_key(self):
        text = "openai: sk-proj-1234567890abcdefghijklmnopqrstuvwxyz"
        findings = SecretDetector.find_secrets(text)
        assert len(findings) > 0

    def test_sanitize_scrubs_all_secrets(self):
        text = "Keys: ghp_1234567890abcdefghijklmnopqrstuvwxyzAB and AIzaSyD9876543210ZYXWVUTSRQPONMLKJIHGF"
        cleaned = SecretDetector.sanitize(text)
        assert "ghp_" not in cleaned
        assert "AIzaSy" not in cleaned
        assert "[REDACTED_SECRET]" in cleaned


class TestGroundTruthValidator:
    """Verifies prompt leakage detection for golden diffs and hidden tests."""

    def test_golden_fix_leakage_detected(self):
        golden_diff = (
            "--- a/service.py\n"
            "+++ b/service.py\n"
            "@@ -1,2 +1,3 @@\n"
            "+    if not user_id:\n"
            "+        raise ValueError('Invalid user id provided')\n"
        )
        prompt = "Investigation details. Suggested fix: raise ValueError('Invalid user id provided')"

        with pytest.raises(GroundTruthLeakageError, match="Golden fix line"):
            GroundTruthValidator.assert_no_leakage(prompt, golden_patch=golden_diff)

    def test_hidden_test_leakage_detected(self):
        hidden_tests = {
            "tests/test_hidden.py": "def test_hidden_security_boundary():\n    assert check_admin_bypass() is False\n"
        }
        prompt = "Failing test: assert check_admin_bypass() is False"

        with pytest.raises(GroundTruthLeakageError, match="Hidden test leakage"):
            GroundTruthValidator.assert_no_leakage(prompt, hidden_tests=hidden_tests)


class TestRepositorySplitter:
    """Verifies strict repository-level partitioning (zero repository leakage)."""

    def test_repository_level_split_disjoint(self):
        records = [
            BugFixRecord(
                id="BUG-1", repository="pallets/flask", language="python",
                buggy_commit="c1", fix_commit="c2", issue="1", failure_type="err", license="MIT", source_url="url"
            ),
            BugFixRecord(
                id="BUG-2", repository="pallets/flask", language="python",
                buggy_commit="c3", fix_commit="c4", issue="2", failure_type="err", license="MIT", source_url="url"
            ),
            BugFixRecord(
                id="BUG-3", repository="tiangolo/fastapi", language="python",
                buggy_commit="c5", fix_commit="c6", issue="3", failure_type="err", license="MIT", source_url="url"
            ),
            BugFixRecord(
                id="BUG-4", repository="pydantic/pydantic", language="python",
                buggy_commit="c7", fix_commit="c8", issue="4", failure_type="err", license="MIT", source_url="url"
            ),
        ]
        splits = RepositorySplitter.assign_splits(records)
        assert len(splits["train"]) == 2  # Both Flask bugs in train
        assert len(splits["validation"]) == 1  # FastAPI in validation
        assert len(splits["test"]) == 1  # Pydantic in test

        # Verify no overlap
        RepositorySplitter.verify_no_repo_overlap(splits)

    def test_repository_leakage_raises_error(self):
        # Force conflicting assignment
        records = [
            BugFixRecord(
                id="BUG-1", repository="pallets/flask", language="python",
                buggy_commit="c1", fix_commit="c2", issue="1", failure_type="err", license="MIT", source_url="url"
            ),
        ]
        # Intentionally overlapping repository sets
        invalid_splits = {
            "train": [records[0]],
            "validation": [records[0]],
            "test": [],
        }
        with pytest.raises(RepositoryLeakageError, match="Overlap"):
            RepositorySplitter.verify_no_repo_overlap(invalid_splits)


class TestDatasetBuilder:
    """Verifies the complete dataset builder and persistence pipeline."""

    def test_dataset_build_manifest(self, tmp_path):
        builder = DatasetBuilder(data_root=tmp_path)
        manifest = builder.build_dataset(version="v1.0.0-test")

        assert manifest["total_records"] == 22
        assert manifest["split_counts"]["train"] == 6
        assert manifest["split_counts"]["validation"] == 3
        assert manifest["split_counts"]["test"] == 13
        assert len(manifest["all_repositories"]) == 22
        assert len(manifest["dataset_hash"]) == 64

        # Check persisted files
        assert (tmp_path / "datasets" / "real_bugs_manifest.json").exists()
        assert (tmp_path / "datasets" / "train.json").exists()
        assert (tmp_path / "datasets" / "validation.json").exists()
        assert (tmp_path / "datasets" / "test.json").exists()


class TestGitHubIngestionService:
    """Verifies real GitHub ingestion service and error handling."""

    def test_github_ingestion_auth_error_on_invalid_token(self):
        service = GitHubIngestionService(token="invalid_gh_token_test")
        with pytest.raises(GitHubIngestionError, match="GitHub authentication error"):
            service.get_repository_info("shreyvirmani", "Devaura")

    def test_github_ingestion_not_found(self):
        # Querying nonexistent repo
        service = GitHubIngestionService(token=None)
        with pytest.raises(GitHubIngestionError):
            service.get_repository_info("shreyvirmani", "nonexistent_repo_xyz_9999")
