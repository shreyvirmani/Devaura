def run_test_with_teardown(test_fn, teardown_fn) -> dict:
    outcome = {'status': 'PASSED', 'teardown_error': None}
    try:
        test_fn()
    except Exception as e:
        outcome['status'] = 'FAILED'
        outcome['test_error'] = e
    try:
        teardown_fn()
    except Exception as e:
        outcome['teardown_error'] = e
    return outcome
