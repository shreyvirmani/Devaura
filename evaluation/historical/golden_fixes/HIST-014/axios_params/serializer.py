def serialize_params(params: dict) -> str:
    parts = []
    for k, v in sorted(params.items()):
        if isinstance(v, list):
            for item in v:
                parts.append(f'{k}[]={item}')
        else:
            parts.append(f'{k}={v}')
    return '&'.join(parts)
