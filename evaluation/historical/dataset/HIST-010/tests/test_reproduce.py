from marshmallow_schema.fields import deserialize_string_list
import pytest

def test_list_none_element_validation():
    with pytest.raises(ValueError):
        deserialize_string_list(['valid', None], allow_none_element=False)
