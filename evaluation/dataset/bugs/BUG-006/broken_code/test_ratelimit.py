from app.ratelimit import is_rate_limited

def test_under_limit():
    assert is_rate_limited(5, 10) is False

def test_over_limit():
    assert is_rate_limited(12, 10) is True

def test_at_limit():
    assert is_rate_limited(10, 10) is True
