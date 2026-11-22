def rebuild_auth_headers(headers: dict, orig_host: str, new_host: str) -> dict:
    # Defect: Keeps Authorization header across domains
    out = dict(headers)
    out['Host'] = new_host
    return out
