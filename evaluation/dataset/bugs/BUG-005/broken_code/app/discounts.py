def apply_tier_discount(price, tier):
    rates = {"gold": 0.20, "silver": 0.10, "bronze": 0.05}
    rate = rates.get(tier, 0.0)
    return price * rate
