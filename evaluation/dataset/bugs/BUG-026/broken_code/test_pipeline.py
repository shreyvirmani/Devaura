from app.formatter import format_output
from app.parser import extract_token

def test_valid_token():
    assert format_output(extract_token("token=abc;123")) == "Output: abc"

def test_missing_token():
    assert format_output(extract_token("no_token_here")) == "Output: "
