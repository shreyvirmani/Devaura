from app.discounts import apply_tier_discount

def test_gold_discount():
    assert apply_tier_discount(100.0, "gold") == 80.0

def test_unknown_tier():
    assert apply_tier_discount(100.0, "guest") == 100.0
