from app.list_provider import get_active_tags

def test_hidden_tag_membership():
    tags = get_active_tags()
    assert "v1" in tags
    assert "v2" not in tags
