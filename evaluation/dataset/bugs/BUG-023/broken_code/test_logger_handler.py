from app.logger_handler import handle_error

def test_successful_action():
    assert handle_error(lambda: "OK") == "OK"

def test_failed_action():
    assert handle_error(lambda: 1 / 0) == "Error: division by zero"
