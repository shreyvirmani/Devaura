def run_test_with_teardown(test_fn, teardown_fn) -> dict:
    # Defect: Wipes outcome dict on teardown exception
    outcome = {'status': 'PASSED'}
    try:
        test_fn()
    except Exception:
        outcome['status'] = 'FAILED'
    try:
        teardown_fn()
    except Exception:
        raise RuntimeError('fixture teardown wiped test execution record')
    return outcome
