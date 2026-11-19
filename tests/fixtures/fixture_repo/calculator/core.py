"""Core calculator implementation for basic arithmetic operations."""
from typing import Union
from calculator.utils import format_result, CalculationError

Number = Union[int, float]


class Calculator:
    """Standard calculator performing addition, subtraction, multiplication, and division."""

    def __init__(self, precision: int = 4) -> None:
        self.precision = precision

    def add(self, a: Number, b: Number) -> Number:
        """Adds two numbers."""
        self._validate_number(a)
        self._validate_number(b)
        result = a + b
        return format_result(result, self.precision)

    def subtract(self, a: Number, b: Number) -> Number:
        """Subtracts b from a."""
        self._validate_number(a)
        self._validate_number(b)
        result = a - b
        return format_result(result, self.precision)

    def multiply(self, a: Number, b: Number) -> Number:
        """Multiplies two numbers."""
        self._validate_number(a)
        self._validate_number(b)
        result = a * b
        return format_result(result, self.precision)

    def divide(self, a: Number, b: Number) -> Number:
        """Divides a by b with zero-division safeguard."""
        self._validate_number(a)
        self._validate_number(b)
        if b == 0:
            raise CalculationError("Cannot divide by zero.")
        result = a / b
        return format_result(result, self.precision)

    def _validate_number(self, value: Number) -> None:
        """Validates that input is a numeric type."""
        if not isinstance(value, (int, float)):
            raise TypeError(f"Expected number, got {type(value).__name__}")
