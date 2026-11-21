from app.display import render_balance

def test_render_balance():
    assert render_balance("Checking", 1500) == "Checking: $1,500.00"
