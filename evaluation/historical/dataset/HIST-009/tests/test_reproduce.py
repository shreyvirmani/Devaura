from pytest_runner.runner import run_test_with_teardown

def test_preserve_test_record_on_teardown_error():
    def good_test(): pass
    def bad_teardown(): raise ValueError('cleanup failed')
    res = run_test_with_teardown(good_test, bad_teardown)
    assert res['status'] == 'PASSED'
    assert 'cleanup failed' in str(res.get('teardown_error'))
