def parse_uint64(val: int) -> int:
    U64_MAX = 0xFFFFFFFFFFFFFFFF
    if val < 0 or val > U64_MAX:
        raise OverflowError(f'Integer {val} exceeds 64-bit unsigned bounds')
    return val
