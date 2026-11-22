from click_cli.formatting import format_command_path

def test_unicode_command_path():
    res = format_command_path(['cli', b'sub'])
    assert res == 'cli sub'
