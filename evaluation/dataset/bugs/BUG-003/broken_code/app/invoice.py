def calculate_invoice_total(items):
    total = 0.0
    for item in items:
        amount = item.get("amount", 0)
        total += amount
    return round(total, 2)
