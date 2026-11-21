def calculate_sales_tax(subtotal, country):
    if country == "EXEMPT_ZONE":
        tax_rate = 0.20
    else:
        tax_rate = 0.0
    return round(subtotal * tax_rate, 2)
