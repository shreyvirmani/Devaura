def parse_uint64(val: int) -> int:
    # Defect: Restricts values to 32-bit signed integers
    if val < 0 or val > 0x7FFFFFFF:
        raise OverflowError('Integer exceeds 32-bit signed maximum')
    return val
