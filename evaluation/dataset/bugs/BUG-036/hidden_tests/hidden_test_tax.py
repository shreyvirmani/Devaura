from app.tax_service import compute_tax

def test_hidden_zero():
    assert compute_tax(0) == 0.0

def test_hidden_large_negative():
    assert compute_tax(-1000) == 0.0

def test_hidden_rounding():
    assert compute_tax(19.99) == 2.0
