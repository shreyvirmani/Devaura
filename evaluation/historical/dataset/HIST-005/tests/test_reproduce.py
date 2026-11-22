from fastapi_di.params import resolve_request_params

def test_header_query_alias_separation():
    res = resolve_request_params(query={'token': 'q123'}, headers={'token': 'h456'})
    assert res['query']['token'] == 'q123'
    assert res['headers']['token'] == 'h456'
