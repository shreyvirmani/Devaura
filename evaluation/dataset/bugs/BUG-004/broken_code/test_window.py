from app.window import get_window_boundary

def test_non_empty_window():
    assert get_window_boundary([10, 20, 30]) == (10, 30)

def test_empty_window():
    assert get_window_boundary([]) == (None, None)
