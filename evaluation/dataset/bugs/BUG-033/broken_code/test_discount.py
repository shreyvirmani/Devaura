from app.discount_engine import compute_discount

def test_vip_discount():
    assert compute_discount(100, "VIP") == 20.0

def test_negative_price():
    assert compute_discount(-50, "VIP") == 0.0
