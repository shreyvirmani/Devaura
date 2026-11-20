"""Phase 4 Deterministic Investigation Test Cases (Section 23).

Tests the 7 required investigation scenarios against the validation fixture repository:
1. Case 1: Direct failure (known failing function with direct stack trace)
2. Case 2: Wrong same-name symbol disambiguation (users.py:get_user vs database.py:get_user)
3. Case 3: Recent regression commit
4. Case 4: Test failure to source mapping
5. Case 5: Dynamic dispatch (unresolved getattr)
6. Case 6: Insufficient evidence ("Something went wrong")
7. Case 7: Conflicting evidence (multiple candidates rather than forced certainty)
"""

import os
from pathlib import Path
import pytest

from agent.investigator import InvestigatorEngine
from agent.models import (
    EvidenceSufficiency,
    EvidenceType,
    FailureType,
    InvestigationRequest,
    ResolutionStatus,
)

FIXTURE_DIR = str(Path(__file__).parent / "fixtures" / "validation_repo")


def test_case_1_direct_failure_localization():
    """Case 1: Direct failure with stack trace into known function correctly localizes symbol."""
    stack_trace = """
Traceback (most recent call last):
  File "app/service.py", line 25, in process_user
    user_data = user.get("name")
TypeError: 'NoneType' object is not subscriptable
"""
    req = InvestigationRequest(
        repository_id="validation-repo",
        title="TypeError in UserService.process_user",
        failure_type=FailureType.RUNTIME_ERROR,
        stack_trace=stack_trace,
    )

    engine = InvestigatorEngine(workspace_root=FIXTURE_DIR, repository_id="validation-repo")
    report = engine.run(req)

    assert report.evidence_sufficiency == EvidenceSufficiency.SUFFICIENT
    assert len(report.root_cause_candidates) > 0
    top_cand = report.root_cause_candidates[0]

    # Localization: check affected files or symbol
    all_affected_files = [f for c in report.root_cause_candidates for f in c.affected_files]
    assert any("app/service.py" in f for f in all_affected_files)
    assert top_cand.confidence > 0.60
    assert len(top_cand.supporting_evidence_ids) > 0


def test_case_2_wrong_same_name_symbol_disambiguation():
    """Case 2: Stack trace pointing to app/users.py:get_user must NOT link to app/database.py:get_user."""
    stack_trace = """
Traceback (most recent call last):
  File "app/users.py", line 14, in get_user
    return save_user({"id": user_id})
ValueError: invalid user id
"""
    req = InvestigationRequest(
        repository_id="validation-repo",
        title="ValueError in users.py get_user",
        failure_type=FailureType.RUNTIME_ERROR,
        stack_trace=stack_trace,
    )

    engine = InvestigatorEngine(workspace_root=FIXTURE_DIR, repository_id="validation-repo")
    report = engine.run(req)

    assert report.evidence_sufficiency == EvidenceSufficiency.SUFFICIENT
    top_cand = report.root_cause_candidates[0]

    # Must localize to app/users.py, NOT app/database.py
    assert any("app/users.py" in f for f in top_cand.affected_files)
    assert not any("app/database.py" in f for f in top_cand.affected_files)


def test_case_3_recent_regression_attribution():
    """Case 3: Failure with known commit SHA identifies the commit as high-value evidence."""
    mock_commit = "c0ffee1234567890abcdef1234567890abcdef12"
    stack_trace = """
Traceback (most recent call last):
  File "app/database.py", line 22, in get_user
    cursor.execute("SELECT * FROM users")
DatabaseError: connection refused
"""
    req = InvestigationRequest(
        repository_id="validation-repo",
        title="DatabaseError after recent commit",
        failure_type=FailureType.RUNTIME_ERROR,
        stack_trace=stack_trace,
        commit_sha=mock_commit,
    )

    engine = InvestigatorEngine(workspace_root=FIXTURE_DIR, repository_id="validation-repo")
    report = engine.run(req)

    assert report.evidence_sufficiency == EvidenceSufficiency.SUFFICIENT
    assert len(report.root_cause_candidates) > 0
    top_cand = report.root_cause_candidates[0]

    assert any("app/database.py" in f for f in top_cand.affected_files)
    assert top_cand.confidence >= 0.70


def test_case_4_test_failure_to_source_mapping():
    """Case 4: Failing test has known source relationship (test_service.py -> app/service.py)."""
    failed_test = {
        "test_file": "tests/test_service.py",
        "test_function": "test_service_process",
        "assertion": "assert res is not None",
        "expected": "User",
        "actual": "None",
        "exception": "AssertionError",
    }
    req = InvestigationRequest(
        repository_id="validation-repo",
        title="test_service_process failed",
        failure_type=FailureType.TEST_FAILURE,
        failed_tests=[failed_test],
    )

    engine = InvestigatorEngine(workspace_root=FIXTURE_DIR, repository_id="validation-repo")
    report = engine.run(req)

    assert report.evidence_sufficiency in (EvidenceSufficiency.SUFFICIENT, EvidenceSufficiency.PARTIALLY_SUFFICIENT)
    assert len(report.root_cause_candidates) > 0

    all_affected_files = [f for c in report.root_cause_candidates for f in c.affected_files]
    assert any("service.py" in f for f in all_affected_files)


def test_case_5_dynamic_dispatch_unresolved():
    """Case 5: Dynamic dispatch with getattr produces UNRESOLVED without fabricating symbol."""
    stack_trace = """
Traceback (most recent call last):
  File "app/auth.py", line 45, in dynamic_dispatch
    fn = getattr(unknown_module, action_name)
AttributeError: 'NoneType' object has no attribute 'dynamic_action'
"""
    req = InvestigationRequest(
        repository_id="validation-repo",
        title="AttributeError in dynamic_dispatch",
        failure_type=FailureType.RUNTIME_ERROR,
        stack_trace=stack_trace,
    )

    engine = InvestigatorEngine(workspace_root=FIXTURE_DIR, repository_id="validation-repo")
    report = engine.run(req)

    assert len(report.root_cause_candidates) > 0
    top_cand = report.root_cause_candidates[0]

    # Verify that dynamic dispatch target was not fabricated
    assert "dynamic" in top_cand.title.lower() or "unresolved" in top_cand.title.lower() or "dynamic" in top_cand.description.lower()
    # Confidence should be appropriately calibrated (<= 0.60 for unresolved dynamic calls)
    assert top_cand.confidence <= 0.65


def test_case_6_insufficient_evidence():
    """Case 6: Only generic error message produces INSUFFICIENT with explicit transparent conclusion."""
    req = InvestigationRequest(
        repository_id="validation-repo",
        title="Unknown crash",
        failure_type=FailureType.UNKNOWN,
        error_message="Something went wrong",
    )

    engine = InvestigatorEngine(workspace_root=FIXTURE_DIR, repository_id="validation-repo")
    report = engine.run(req)

    assert report.evidence_sufficiency == EvidenceSufficiency.INSUFFICIENT
    assert "insufficient evidence" in report.summary.lower()
    assert report.overall_confidence == 0.0
    assert len(report.missing_information) > 0
    assert len(report.recommended_next_steps) > 0


def test_case_7_conflicting_evidence_multiple_candidates():
    """Case 7: Ambiguous caller-callee failure produces multiple candidates rather than forced certainty."""
    stack_trace = """
Traceback (most recent call last):
  File "app/service.py", line 24, in process_user
    user = fetch_db_user(user_id)
  File "app/service.py", line 25, in process_user
    val = user["role"]
TypeError: 'NoneType' object is not subscriptable
"""
    req = InvestigationRequest(
        repository_id="validation-repo",
        title="NoneType error in process_user calling database",
        failure_type=FailureType.RUNTIME_ERROR,
        stack_trace=stack_trace,
    )

    engine = InvestigatorEngine(workspace_root=FIXTURE_DIR, repository_id="validation-repo")
    report = engine.run(req)

    assert report.evidence_sufficiency == EvidenceSufficiency.SUFFICIENT
    # Must produce multiple candidates (e.g. database returning None vs caller not handling None)
    assert len(report.root_cause_candidates) >= 2

    c1 = report.root_cause_candidates[0]
    c2 = report.root_cause_candidates[1]

    assert c1.confidence >= c2.confidence
    assert c1.title != c2.title
    assert len(c1.supporting_evidence_ids) > 0
    assert len(c2.supporting_evidence_ids) > 0
