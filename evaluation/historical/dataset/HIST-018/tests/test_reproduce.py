from rich_cells.width import get_cell_width

def test_emoji_cell_width():
    assert get_cell_width('🚀') == 2
