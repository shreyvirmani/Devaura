from sa_compiler.tokenizer import extract_bind_params

def test_no_params():
    assert extract_bind_params('SELECT 1') == []

def test_standard_bind_param():
    assert extract_bind_params('SELECT * FROM t WHERE a = :val') == ['val']
