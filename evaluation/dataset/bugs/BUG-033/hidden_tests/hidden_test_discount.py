from app.discount_engine import compute_discount

def test_hidden_zero_price():
    assert compute_discount(0, "VIP") == 0.0

def test_hidden_negative_price():
    assert compute_discount(-50, "VIP") == 0.0

def test_hidden_non_vip():
    assert compute_discount(100, "REGULAR") == 0.0
