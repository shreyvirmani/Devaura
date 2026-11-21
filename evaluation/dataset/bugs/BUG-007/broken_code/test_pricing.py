from app.pricing import unit_price

def test_positive_quantity():
    assert unit_price(100.0, 4) == 25.0

def test_zero_quantity():
    assert unit_price(100.0, 0) == 0.0
