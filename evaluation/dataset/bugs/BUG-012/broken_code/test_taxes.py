from app.taxes import calculate_sales_tax

def test_exempt_zone():
    assert calculate_sales_tax(100.0, "EXEMPT_ZONE") == 0.0

def test_standard_zone():
    assert calculate_sales_tax(100.0, "US") == 20.0
