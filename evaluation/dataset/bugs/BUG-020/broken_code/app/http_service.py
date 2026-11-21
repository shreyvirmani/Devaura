def get_request_timeout(override=None):
    if override is not None:
        return override
    return 5
