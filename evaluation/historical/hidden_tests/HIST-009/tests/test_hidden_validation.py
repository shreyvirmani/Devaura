from pytest_runner.runner import run_test_with_teardown

def test_clean_test_and_teardown():
    res = run_test_with_teardown(lambda: None, lambda: None)
    assert res == {'status': 'PASSED', 'teardown_error': None}
