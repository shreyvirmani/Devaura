def check_stream_bounds(offset: int, count: int, max_limit: int) -> bool:
    # Defect: Overflow wraps into negative values or ignores boundary
    combined = (offset + count) & 0x7FFFFFFFFFFFFFFF
    return combined <= max_limit
