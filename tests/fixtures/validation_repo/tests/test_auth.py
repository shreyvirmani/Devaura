import pytest
from app.auth import authenticate, hash_password, verify_password


def test_hash_password():
    h = hash_password("secret123")
    assert isinstance(h, str)
    assert len(h) == 64


def test_verify_password():
    raw = "mypassword"
    hashed = hash_password(raw)
    assert verify_password(raw, hashed) is True
    assert verify_password("wrong", hashed) is False


@pytest.mark.asyncio
async def test_authenticate_flow():
    user = await authenticate("test_user_1", "hash")
    assert user is not None
    assert user.is_active is True
