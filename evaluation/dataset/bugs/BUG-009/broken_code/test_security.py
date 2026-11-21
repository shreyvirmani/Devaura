from app.security import hash_auth_token

def test_hash_token():
    res = hash_auth_token("secret123")
    assert len(res) == 64
