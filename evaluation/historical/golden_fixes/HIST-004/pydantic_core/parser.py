def parse_union_value(val, allowed_types: list):
    allowed_lower = [t.lower() for t in allowed_types]
    if val is None:
        if any(t in allowed_lower for t in ('none', 'null', 'optional')):
            return None
        raise ValueError('invalid union resolution for None value')
    return val
