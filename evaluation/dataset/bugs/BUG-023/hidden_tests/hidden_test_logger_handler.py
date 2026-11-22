from app.logger_handler import handle_error

def test_hidden_custom_exception():
    def failing():
        raise KeyError("missing")
    assert "Error:" in handle_error(failing)
