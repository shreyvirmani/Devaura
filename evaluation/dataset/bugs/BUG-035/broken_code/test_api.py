from app.api_layer import get_user_view

def test_valid_user():
    assert get_user_view(1)["status"] == 200

def test_missing_user():
    assert get_user_view(-1)["status"] == 404
