from app.ratelimit import is_rate_limited

def test_hidden_exact_boundary():
    assert is_rate_limited(10, 10) is True

def test_hidden_above_boundary():
    assert is_rate_limited(11, 10) is True
