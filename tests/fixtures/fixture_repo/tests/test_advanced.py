import pytest
from calculator.advanced import ScientificCalculator
from calculator.utils import CalculationError


def test_power():
    calc = ScientificCalculator()
    assert calc.power(2, 3) == 8.0
    assert calc.power(5, 0) == 1.0


def test_sqrt():
    calc = ScientificCalculator()
    assert calc.sqrt(9) == 3.0
    with pytest.raises(CalculationError):
        calc.sqrt(-4)
