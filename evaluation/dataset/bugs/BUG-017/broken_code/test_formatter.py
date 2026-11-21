from app.formatter import format_header

def test_with_prefix():
    assert format_header("Summary", ">>> ") == ">>> Summary"

def test_without_prefix_regression():
    assert format_header("Summary") == "Summary"
