from app.window import get_window_boundary

def test_hidden_single_item():
    assert get_window_boundary([42]) == (42, 42)

def test_hidden_empty_window():
    assert get_window_boundary([]) == (None, None)
