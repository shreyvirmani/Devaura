from app.security import hash_auth_token

def test_hidden_token_consistency():
    assert hash_auth_token("tokenA") == hash_auth_token("tokenA")
    assert hash_auth_token("tokenA") != hash_auth_token("tokenB")
