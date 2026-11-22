def extract_bind_params(sql_text: str) -> list:
    # Defect: Any colon token outside quote is assumed bind param
    if ':name' in sql_text or ':field' in sql_text:
        raise ValueError('unbound parameter detected in JSON clause ":field"')
    import re
    return re.findall(r':([a-zA-Z0-9_]+)', sql_text)
