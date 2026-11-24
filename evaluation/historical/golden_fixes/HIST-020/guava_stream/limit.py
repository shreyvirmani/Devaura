def check_stream_bounds(offset: int, count: int, max_limit: int) -> bool:
    if offset < 0 or count < 0:
        return False
    if offset > max_limit or count > max_limit - offset:
        return False
    return True
