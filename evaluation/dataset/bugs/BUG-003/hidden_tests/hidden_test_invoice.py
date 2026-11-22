from app.invoice import calculate_invoice_total

def test_hidden_empty_items():
    assert calculate_invoice_total([]) == 0.0

def test_hidden_multiple_mixed():
    assert calculate_invoice_total([{"amount": "50.25"}, {"amount": 49.75}]) == 100.0
