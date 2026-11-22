def parse_nested_query(params: dict) -> dict:
    forbidden = {'__proto__', 'constructor', 'prototype'}
    result = {}
    for k, v in params.items():
        if k in forbidden:
            continue
        result[k] = v
    return result
