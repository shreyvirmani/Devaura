def resolve_request_params(query: dict, headers: dict) -> dict:
    return {
        'query': dict(query),
        'headers': dict(headers),
    }
