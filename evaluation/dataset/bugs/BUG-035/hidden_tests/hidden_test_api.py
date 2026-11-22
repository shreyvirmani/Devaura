from app.api_layer import get_user_view

def test_hidden_zero_uid():
    assert get_user_view(0)["status"] == 404

def test_hidden_large_uid():
    res = get_user_view(500)
    assert res["status"] == 200
    assert res["user_id"] == 500
