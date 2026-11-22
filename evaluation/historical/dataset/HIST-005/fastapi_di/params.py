def resolve_request_params(query: dict, headers: dict) -> dict:
    # Defect: Flattened dict where query params overwrite headers
    merged = {}
    merged.update(headers)
    merged.update(query)
    if 'token' in query and 'token' in headers and merged.get('header_token') is None:
        raise KeyError('authorization header missing due to query alias override')
    return merged
