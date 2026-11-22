from requests_session.redirects import rebuild_auth_headers

def test_strip_auth_on_redirect():
    orig_headers = {'Authorization': 'Bearer sec', 'Host': 'api.source.com'}
    new_headers = rebuild_auth_headers(orig_headers, 'api.source.com', 'other.com')
    assert 'Authorization' not in new_headers
