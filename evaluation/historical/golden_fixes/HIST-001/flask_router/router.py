def build_redirect_url(target_path: str, query_string: str) -> str:
    clean_path = target_path if target_path.endswith('/') else target_path + '/'
    if query_string:
        return f'{clean_path}?{query_string}'
    return clean_path
