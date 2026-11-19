"""Advanced scientific calculator extending core arithmetic."""
import math
from calculator.core import Calculator, Number
from calculator.utils import format_result, CalculationError


class ScientificCalculator(Calculator):
    """Scientific calculator extending base Calculator with exponential and power operations."""

    def power(self, base: Number, exponent: Number) -> Number:
        """Raises base to the power of exponent."""
        self._validate_number(base)
        self._validate_number(exponent)
        result = math.pow(base, exponent)
        return format_result(result, self.precision)

    def sqrt(self, value: Number) -> Number:
        """Computes square root of a non-negative number."""
        self._validate_number(value)
        if value < 0:
            raise CalculationError("Cannot compute square root of negative number.")
        result = math.sqrt(value)
        return format_result(result, self.precision)
