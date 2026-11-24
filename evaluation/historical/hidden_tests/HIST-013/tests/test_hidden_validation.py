from chalk_ansi.color import rgb_to_ansi

def test_zero_rgb():
    assert rgb_to_ansi(0, 0, 0) == '\x1b[38;2;0;0;0m'

def test_white_rgb():
    assert rgb_to_ansi(255, 255, 255) == '\x1b[38;2;255;255;255m'
