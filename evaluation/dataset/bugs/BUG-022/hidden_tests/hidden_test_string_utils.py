from app.string_utils import join_tokens

def test_hidden_none_tokens():
    assert join_tokens(["foo", None, "bar"]) == "foo bar"

def test_hidden_empty_tokens():
    assert join_tokens([]) == ""
