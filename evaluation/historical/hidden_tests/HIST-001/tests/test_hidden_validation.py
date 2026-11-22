from flask_router.router import build_redirect_url

def test_slash_redirect_empty_query():
    assert build_redirect_url('/items', '') == '/items/'

def test_slash_redirect_complex_query():
    assert build_redirect_url('/users/', 'a=1&b=2') == '/users/?a=1&b=2'
