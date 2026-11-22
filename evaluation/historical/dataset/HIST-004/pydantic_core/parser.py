def parse_union_value(val, allowed_types: list):
    # Defect: treats None as unparseable unless explicitly 'null'
    if val is None and 'null' not in allowed_types:
        raise ValueError('invalid union resolution for None value')
    return val
