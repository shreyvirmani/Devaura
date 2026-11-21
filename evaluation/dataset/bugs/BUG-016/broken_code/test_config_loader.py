from app.config_loader import build_config

def test_isolated_configs():
    c1 = build_config({"env": "dev"})
    assert c1 == {"env": "dev", "loaded": True}
    c2 = build_config()
    assert "env" not in c2
