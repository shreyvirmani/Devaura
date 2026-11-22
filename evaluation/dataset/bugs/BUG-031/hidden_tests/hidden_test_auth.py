from app.auth_loader import hash_password

def test_hidden_empty_password():
    assert len(hash_password("")) == 64

def test_hidden_deterministic():
    assert hash_password("test") == hash_password("test")
