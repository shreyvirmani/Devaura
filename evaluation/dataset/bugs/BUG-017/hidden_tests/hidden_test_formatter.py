from app.formatter import format_header

def test_hidden_custom_prefix():
    assert format_header("Report", "== ") == "== Report"
