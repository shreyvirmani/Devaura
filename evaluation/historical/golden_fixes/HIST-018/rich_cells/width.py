def get_cell_width(text: str) -> int:
    total = 0
    for ch in text:
        code = ord(ch)
        if (code >= 0x1F300 and code <= 0x1F9FF) or (code >= 0x2600 and code <= 0x27BF) or (code >= 0x2E80 and code <= 0x9FFF):
            total += 2
        else:
            total += 1
    return total
