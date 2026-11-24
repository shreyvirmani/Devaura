from jinja_core.sandbox import safe_lookup
import pytest

def test_sandbox_attribute_guard():
    with pytest.raises(PermissionError):
        safe_lookup({'__globals__': {}}, '__globals__')
