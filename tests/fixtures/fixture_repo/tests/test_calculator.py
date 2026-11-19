import pytest
from calculator.core import Calculator
from calculator.utils import CalculationError


def test_add():
    calc = Calculator()
    assert calc.add(2, 3) == 5
    assert calc.add(-1, 1) == 0


def test_subtract():
    calc = Calculator()
    assert calc.subtract(10, 4) == 6


def test_multiply():
    calc = Calculator()
    assert calc.multiply(3, 7) == 21


def test_divide():
    calc = Calculator()
    assert calc.divide(10, 2) == 5.0
    with pytest.raises(CalculationError):
        calc.divide(10, 0)
