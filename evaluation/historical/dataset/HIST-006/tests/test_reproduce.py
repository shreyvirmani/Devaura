from sa_compiler.tokenizer import extract_bind_params

def test_json_colon_escaping():
    params = extract_bind_params('SELECT data->>:field FROM logs WHERE id = :log_id')
    assert 'log_id' in params
