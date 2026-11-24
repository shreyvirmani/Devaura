from typing import List, Tuple

def encode_query_params(params: List[Tuple[str, str]]) -> str:
    # Defect: Converts to dict, collapsing duplicate keys
    param_dict = dict(params)
    return '&'.join(f'{k}={v}' for k, v in param_dict.items())
