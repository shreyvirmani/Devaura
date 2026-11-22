from app.auth_policy import has_access

def test_hidden_superuser():
    assert has_access("superuser") is True

def test_hidden_anonymous():
    assert has_access("") is False
