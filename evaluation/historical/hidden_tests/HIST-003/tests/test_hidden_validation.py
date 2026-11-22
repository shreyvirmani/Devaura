from click_cli.formatting import format_command_path

def test_pure_string_parts():
    assert format_command_path(['git', 'status']) == 'git status'

def test_empty_parts():
    assert format_command_path([]) == ''
