def rebuild_auth_headers(headers: dict, orig_host: str, new_host: str) -> dict:
    out = dict(headers)
    out['Host'] = new_host
    if orig_host.lower() != new_host.lower() and 'Authorization' in out:
        del out['Authorization']
    return out
