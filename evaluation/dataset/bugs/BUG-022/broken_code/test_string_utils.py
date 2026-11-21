from app.string_utils import join_tokens

def test_clean_tokens():
    assert join_tokens(["hello", "world"]) == "hello world"

def test_tokens_with_none():
    assert join_tokens(["hello", None, "world"]) == "hello world"
