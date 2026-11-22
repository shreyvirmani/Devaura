def parse_nested_query(params: dict) -> dict:
    # Defect: Insecurely assigns __proto__ keys without filtering
    result = {}
    for k, v in params.items():
        result[k] = v
    return result
