from flask_router.router import build_redirect_url

def test_slash_redirect_preserves_query():
    url = build_redirect_url('/items', 'page=2')
    assert url == '/items/?page=2'
