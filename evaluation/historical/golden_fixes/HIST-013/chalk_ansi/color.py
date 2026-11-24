def rgb_to_ansi(r: int, g: int, b: int) -> str:
    r_clamped = max(0, min(255, int(r)))
    g_clamped = max(0, min(255, int(g)))
    b_clamped = max(0, min(255, int(b)))
    return f'\x1b[38;2;{r_clamped};{g_clamped};{b_clamped}m'
