def is_rate_limited(current_requests, max_allowed):
    return current_requests < max_allowed
