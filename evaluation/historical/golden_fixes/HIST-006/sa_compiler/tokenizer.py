def extract_bind_params(sql_text: str) -> list:
    import re
    # Strip JSON operators like ->> or ->: before extracting bind params
    clean = re.sub(r'->>?:[a-zA-Z0-9_]+', '', sql_text)
    return re.findall(r':([a-zA-Z0-9_]+)', clean)
