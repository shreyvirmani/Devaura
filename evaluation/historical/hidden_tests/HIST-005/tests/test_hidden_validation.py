from fastapi_di.params import resolve_request_params

def test_empty_headers_and_query():
    res = resolve_request_params({}, {})
    assert res == {'query': {}, 'headers': {}}
