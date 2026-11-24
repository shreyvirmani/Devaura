from rich_cells.width import get_cell_width

def test_ascii_cell_width():
    assert get_cell_width('hello') == 5

def test_mixed_cell_width():
    assert get_cell_width('hi 🚀') == 5
