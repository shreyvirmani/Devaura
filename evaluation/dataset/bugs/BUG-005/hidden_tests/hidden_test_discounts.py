from app.discounts import apply_tier_discount

def test_hidden_silver_discount():
    assert apply_tier_discount(100.0, "silver") == 90.0

def test_hidden_unknown_tier():
    assert apply_tier_discount(100.0, "guest") == 100.0
