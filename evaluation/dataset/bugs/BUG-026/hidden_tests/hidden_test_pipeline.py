from app.formatter import format_output
from app.parser import extract_token

def test_hidden_empty_string():
    assert format_output(extract_token("")) == "Output: "

def test_hidden_none_input():
    assert format_output(extract_token(None)) == "Output: "

def test_hidden_whitespace_only():
    assert format_output(extract_token("   ")) == "Output: "

def test_hidden_multiple_semicolons():
    assert format_output(extract_token("token=xyz;foo;bar")) == "Output: xyz"
