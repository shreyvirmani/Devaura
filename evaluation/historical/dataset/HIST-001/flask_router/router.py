def build_redirect_url(target_path: str, query_string: str) -> str:
    # Defect: Ignores query_string when appending trailing slash
    clean_path = target_path if target_path.endswith('/') else target_path + '/'
    return clean_path
