from app.taxes import calculate_sales_tax

def test_hidden_standard_tax():
    assert calculate_sales_tax(100.0, "ZONE_A") == 20.0

def test_hidden_zero_amount():
    assert calculate_sales_tax(0.0, "ZONE_A") == 0.0
