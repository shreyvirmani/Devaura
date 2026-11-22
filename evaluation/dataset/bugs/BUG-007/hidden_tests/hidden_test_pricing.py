from app.pricing import unit_price

def test_hidden_single_item():
    assert unit_price(50.0, 1) == 50.0

def test_hidden_zero_quantity_safe():
    assert unit_price(50.0, 0) == 0.0
