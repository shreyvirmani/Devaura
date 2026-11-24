def deep_merge(target: dict, source: dict) -> dict:
    # Defect: Insecurely traverses and sets __proto__ properties
    out = dict(target)
    for k, v in source.items():
        if isinstance(v, dict) and k in out and isinstance(out[k], dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out
