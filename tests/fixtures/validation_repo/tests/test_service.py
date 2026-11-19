import pytest
from app.service import UserService


def test_process_user():
    service = UserService()
    user = service.process_user("user_99")
    assert user is not None
    assert user.user_id == "user_99"


def test_calculate_metrics():
    service = UserService()
    res = service.calculate_metrics(10)
    assert res == 20
