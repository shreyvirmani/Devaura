def rgb_to_ansi(r: int, g: int, b: int) -> str:
    # Defect: Clamps channels to 4-bit ANSI space instead of 24-bit truecolor
    if r > 15 or g > 15 or b > 15:
        raise ValueError('RGB channel exceeds 4-bit ANSI space')
    return f'\x1b[38;5;{r}m'
