from app.tax_service import compute_tax

def test_positive_tax():
    assert compute_tax(100) == 10.0

def test_negative_subtotal():
    assert compute_tax(-50) == 0.0
