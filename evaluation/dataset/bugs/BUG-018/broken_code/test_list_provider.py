from app.list_provider import get_active_tags

def test_returns_list_of_tags():
    tags = get_active_tags()
    assert isinstance(tags, list)
    assert "v1" in tags
    assert "v2" not in tags
