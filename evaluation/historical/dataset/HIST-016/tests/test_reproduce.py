from gin_fs.static import resolve_static_path
import pytest

def test_static_path_traversal_blocked():
    with pytest.raises(PermissionError):
        resolve_static_path('/var/www/static', '../../etc/passwd')
