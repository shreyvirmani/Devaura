from app.config_loader import build_config

def test_hidden_isolated_calls():
    c1 = build_config()
    c1["temp"] = 1
    c2 = build_config()
    assert "temp" not in c2
