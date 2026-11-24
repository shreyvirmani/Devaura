from chalk_ansi.color import rgb_to_ansi

def test_rgb_ansi_formatting():
    res = rgb_to_ansi(255, 128, 0)
    assert res == '\x1b[38;2;255;128;0m'
