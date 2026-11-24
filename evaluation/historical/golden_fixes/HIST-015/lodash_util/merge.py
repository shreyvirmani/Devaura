def deep_merge(target: dict, source: dict) -> dict:
    FORBIDDEN_KEYS = {'__proto__', 'constructor', 'prototype'}
    out = dict(target)
    for k, v in source.items():
        if k in FORBIDDEN_KEYS:
            continue
        if isinstance(v, dict) and k in out and isinstance(out[k], dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out
