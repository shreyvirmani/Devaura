from app.display import render_balance

def test_hidden_zero_balance():
    assert render_balance("Savings", 0) == "Savings: $0.00"

def test_hidden_large_balance():
    assert render_balance("Vault", 1000000) == "Vault: $1,000,000.00"
