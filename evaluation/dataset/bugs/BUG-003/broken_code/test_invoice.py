from app.invoice import calculate_invoice_total

def test_numeric_items():
    assert calculate_invoice_total([{"amount": 10.5}, {"amount": 20.0}]) == 30.5

def test_string_item_coercion():
    assert calculate_invoice_total([{"amount": "15.50"}, {"amount": 4.5}]) == 20.0
