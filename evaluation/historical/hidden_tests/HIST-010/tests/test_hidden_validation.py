from marshmallow_schema.fields import deserialize_string_list

def test_list_allow_none_element():
    res = deserialize_string_list(['a', None], allow_none_element=True)
    assert res == ['a', None]

def test_list_all_strings():
    assert deserialize_string_list([' apple ']) == ['apple']
