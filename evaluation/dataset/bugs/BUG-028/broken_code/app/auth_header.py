def make_headers(api_key):
    # Schema migrated to x-api-key
    return {"x-api-key": api_key}
