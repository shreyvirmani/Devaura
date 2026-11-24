from typing import List, Tuple

def encode_query_params(params: List[Tuple[str, str]]) -> str:
    return '&'.join(f'{k}={v}' for k, v in params)
