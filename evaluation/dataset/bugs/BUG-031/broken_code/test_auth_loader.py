from app.auth_loader import hash_password

def test_hash():
    h = hash_password("admin")
    assert len(h) == 64
