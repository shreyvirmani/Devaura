from jinja_core.sandbox import safe_lookup
import pytest

def test_subclasses_blocked():
    with pytest.raises(PermissionError):
        safe_lookup({'__subclasses__': []}, '__subclasses__')

def test_public_attribute_allowed():
    assert safe_lookup({'name': 'jinja'}, 'name') == 'jinja'
