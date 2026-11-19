"""Utility functions and exceptions for the calculator package."""
from typing import Union

Number = Union[int, float]


class CalculationError(Exception):
    """Raised when an invalid mathematical operation occurs."""
    pass


def format_result(value: Number, precision: int = 4) -> Number:
    """Rounds floating point numbers to the specified precision."""
    if isinstance(value, float):
        return round(value, precision)
    return value
