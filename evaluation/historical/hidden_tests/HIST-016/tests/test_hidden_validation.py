from gin_fs.static import resolve_static_path

def test_valid_static_path():
    res = resolve_static_path('/var/www/static', 'css/app.css')
    assert res.endswith('css/app.css') or res.endswith('css\\app.css')
