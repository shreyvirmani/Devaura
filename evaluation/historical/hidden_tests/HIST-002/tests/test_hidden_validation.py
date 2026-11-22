from requests_session.redirects import rebuild_auth_headers

def test_keep_auth_on_same_host():
    orig_headers = {'Authorization': 'Bearer sec', 'Host': 'api.source.com'}
    new_headers = rebuild_auth_headers(orig_headers, 'api.source.com', 'api.source.com')
    assert new_headers.get('Authorization') == 'Bearer sec'
