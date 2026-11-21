from app.auth_policy import has_access

def test_admin_access():
    assert has_access("admin") is True

def test_superuser_access():
    assert has_access("superuser") is True

def test_guest_access():
    assert has_access("guest") is False
