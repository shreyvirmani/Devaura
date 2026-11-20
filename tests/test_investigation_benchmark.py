"""Phase 4 Evaluation Benchmark Suite (Section 24).

Measures and asserts the 12 Phase 4 metrics across the deterministic fixture cases:
1. issue_localization_accuracy
2. root_cause_candidate_accuracy
3. top_1_root_cause_accuracy
4. top_3_root_cause_accuracy
5. evidence_retrieval_precision
6. evidence_sufficiency_accuracy
7. false_confidence_rate
8. unsupported_claim_rate
9. tool_selection_accuracy
10. average_iterations
11. average_latency_ms
12. token_usage
"""

from pathlib import Path
import pytest

from agent.evaluator import EvaluationTestCase, InvestigationEvaluator
from agent.models import EvidenceSufficiency, FailureType, InvestigationRequest

FIXTURE_DIR = str(Path(__file__).parent / "fixtures" / "validation_repo")


def test_investigation_benchmark_suite():
    evaluator = InvestigationEvaluator(workspace_root=FIXTURE_DIR)

    test_cases = [
        # Case 1: Direct failure in app/service.py
        EvaluationTestCase(
            case_id="case-1",
            name="Direct Failure in Service",
            request=InvestigationRequest(
                repository_id="validation-repo",
                title="TypeError in UserService.process_user",
                failure_type=FailureType.RUNTIME_ERROR,
                stack_trace="""
Traceback (most recent call last):
  File "app/service.py", line 25, in process_user
    user_data = user.get("name")
TypeError: 'NoneType' object is not subscriptable
""",
            ),
            expected_failing_file="app/service.py",
            expected_sufficiency=EvidenceSufficiency.SUFFICIENT,
            expected_keywords_in_candidate=["service.py", "process_user"],
        ),
        # Case 2: Disambiguation: users.py get_user
        EvaluationTestCase(
            case_id="case-2",
            name="Disambiguate users.py vs database.py",
            request=InvestigationRequest(
                repository_id="validation-repo",
                title="ValueError in users.py get_user",
                failure_type=FailureType.RUNTIME_ERROR,
                stack_trace="""
Traceback (most recent call last):
  File "app/users.py", line 14, in get_user
    return save_user({"id": user_id})
ValueError: invalid user id
""",
            ),
            expected_failing_file="app/users.py",
            expected_sufficiency=EvidenceSufficiency.SUFFICIENT,
            expected_keywords_in_candidate=["users.py"],
        ),
        # Case 3: Recent regression commit
        EvaluationTestCase(
            case_id="case-3",
            name="Recent Regression in Database",
            request=InvestigationRequest(
                repository_id="validation-repo",
                title="Database connection error",
                failure_type=FailureType.RUNTIME_ERROR,
                stack_trace="""
Traceback (most recent call last):
  File "app/database.py", line 22, in get_user
    cursor.execute("SELECT * FROM users")
DatabaseError: connection refused
""",
                commit_sha="c0ffee1234567890abcdef1234567890abcdef12",
            ),
            expected_failing_file="app/database.py",
            expected_sufficiency=EvidenceSufficiency.SUFFICIENT,
            expected_keywords_in_candidate=["database.py"],
        ),
        # Case 4: Test failure to source mapping
        EvaluationTestCase(
            case_id="case-4",
            name="Test Failure to Source Mapping",
            request=InvestigationRequest(
                repository_id="validation-repo",
                title="test_service_process failure",
                failure_type=FailureType.TEST_FAILURE,
                failed_tests=[
                    {
                        "test_file": "tests/test_service.py",
                        "test_function": "test_service_process",
                        "assertion": "assert res is not None",
                        "expected": "User",
                        "actual": "None",
                    }
                ],
            ),
            expected_failing_file="app/service.py",
            expected_sufficiency=EvidenceSufficiency.SUFFICIENT,
            expected_keywords_in_candidate=["service"],
        ),
        # Case 5: Dynamic dispatch unresolved
        EvaluationTestCase(
            case_id="case-5",
            name="Dynamic Dispatch Unresolved",
            request=InvestigationRequest(
                repository_id="validation-repo",
                title="AttributeError in dynamic_dispatch",
                failure_type=FailureType.RUNTIME_ERROR,
                stack_trace="""
Traceback (most recent call last):
  File "app/auth.py", line 45, in dynamic_dispatch
    fn = getattr(unknown_module, action_name)
AttributeError: 'NoneType' object has no attribute 'dynamic_action'
""",
            ),
            expected_failing_file="app/auth.py",
            expected_sufficiency=EvidenceSufficiency.SUFFICIENT,
            expected_keywords_in_candidate=["dynamic"],
            expect_unresolved=True,
        ),
        # Case 6: Insufficient evidence
        EvaluationTestCase(
            case_id="case-6",
            name="Generic Crash Without Evidence",
            request=InvestigationRequest(
                repository_id="validation-repo",
                title="Unknown crash",
                failure_type=FailureType.UNKNOWN,
                error_message="Something went wrong",
            ),
            expected_failing_file=None,
            expected_sufficiency=EvidenceSufficiency.INSUFFICIENT,
        ),
        # Case 7: Conflicting evidence / multi-candidate
        EvaluationTestCase(
            case_id="case-7",
            name="Conflicting Caller Callee Failure",
            request=InvestigationRequest(
                repository_id="validation-repo",
                title="NoneType error in process_user calling database",
                failure_type=FailureType.RUNTIME_ERROR,
                stack_trace="""
Traceback (most recent call last):
  File "app/service.py", line 24, in process_user
    user = fetch_db_user(user_id)
  File "app/service.py", line 25, in process_user
    val = user["role"]
TypeError: 'NoneType' object is not subscriptable
""",
            ),
            expected_failing_file="app/service.py",
            expected_sufficiency=EvidenceSufficiency.SUFFICIENT,
            expected_keywords_in_candidate=["database", "service"],
            expect_multiple_candidates=True,
        ),
    ]

    report = evaluator.evaluate_test_cases(test_cases)

    print("\n--- PHASE 4 INVESTIGATION EVALUATION BENCHMARK ---")
    print(f"Total Cases:                   {report.total_cases}")
    print(f"Issue Localization Accuracy:   {report.issue_localization_accuracy * 100:.1f}%")
    print(f"Root Cause Candidate Accuracy: {report.root_cause_candidate_accuracy * 100:.1f}%")
    print(f"Top-1 Candidate Accuracy:      {report.top_1_root_cause_accuracy * 100:.1f}%")
    print(f"Top-3 Candidate Accuracy:      {report.top_3_root_cause_accuracy * 100:.1f}%")
    print(f"Evidence Retrieval Precision:  {report.evidence_retrieval_precision * 100:.1f}%")
    print(f"Evidence Sufficiency Accuracy: {report.evidence_sufficiency_accuracy * 100:.1f}%")
    print(f"False Confidence Rate:         {report.false_confidence_rate * 100:.1f}%")
    print(f"Unsupported Claim Rate:        {report.unsupported_claim_rate * 100:.1f}%")
    print(f"Tool Selection Accuracy:       {report.tool_selection_accuracy * 100:.1f}%")
    print(f"Average Iterations:            {report.average_iterations} / 5")
    print(f"Average Latency:               {report.average_latency_ms:.2f} ms")

    # Target assertion thresholds
    assert report.issue_localization_accuracy >= 0.85, f"Localization accuracy below target: {report.issue_localization_accuracy}"
    assert report.root_cause_candidate_accuracy >= 0.85, f"Candidate accuracy below target: {report.root_cause_candidate_accuracy}"
    assert report.top_1_root_cause_accuracy >= 0.85, f"Top-1 accuracy below target: {report.top_1_root_cause_accuracy}"
    assert report.top_3_root_cause_accuracy >= 0.85, f"Top-3 accuracy below target: {report.top_3_root_cause_accuracy}"
    assert report.evidence_sufficiency_accuracy >= 0.85, f"Sufficiency accuracy below target: {report.evidence_sufficiency_accuracy}"
    assert report.false_confidence_rate == 0.0, f"False confidence rate must be 0.0: {report.false_confidence_rate}"
    assert report.unsupported_claim_rate == 0.0, f"Unsupported claims found: {report.unsupported_claim_rate}"
    assert report.tool_selection_accuracy == 1.0
    assert report.average_iterations <= 5.0
