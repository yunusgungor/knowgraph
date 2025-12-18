"""Validation utilities for KnowGraph.

Provides functions and decorators for validating inputs, handling None values,
and ensuring data integrity throughout the system.
"""

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from knowgraph.shared.exceptions import KnowGraphError

T = TypeVar("T")


class ValidationError(KnowGraphError):
    """Raised when validation fails."""



def require_not_none(value: T | None, name: str = "value") -> T:
    """Require that a value is not None.

    Args:
    ----
        value: Value to check
        name: Name of the value for error message

    Returns:
    -------
        The value if not None

    Raises:
    ------
        ValidationError: If value is None
    """
    if value is None:
        raise ValidationError(f"{name} must not be None")
    return value


def require_not_empty(value: str | None, name: str = "value") -> str:
    """Require that a string is not None or empty.

    Args:
    ----
        value: String to check
        name: Name of the value for error message

    Returns:
    -------
        The string if not None or empty

    Raises:
    ------
        ValidationError: If value is None or empty
    """
    if value is None:
        raise ValidationError(f"{name} must not be None")
    if not value.strip():
        raise ValidationError(f"{name} must not be empty")
    return value


def require_positive(value: int | float | None, name: str = "value") -> int | float:
    """Require that a number is positive.

    Args:
    ----
        value: Number to check
        name: Name of the value for error message

    Returns:
    -------
        The number if positive

    Raises:
    ------
        ValidationError: If value is None or not positive
    """
    if value is None:
        raise ValidationError(f"{name} must not be None")
    if value <= 0:
        raise ValidationError(f"{name} must be positive, got {value}")
    return value


def require_non_negative(value: int | float | None, name: str = "value") -> int | float:
    """Require that a number is non-negative.

    Args:
    ----
        value: Number to check
        name: Name of the value for error message

    Returns:
    -------
        The number if non-negative

    Raises:
    ------
        ValidationError: If value is None or negative
    """
    if value is None:
        raise ValidationError(f"{name} must not be None")
    if value < 0:
        raise ValidationError(f"{name} must be non-negative, got {value}")
    return value


def require_in_range(
    value: int | float | None,
    min_value: int | float,
    max_value: int | float,
    name: str = "value",
) -> int | float:
    """Require that a number is within a range.

    Args:
    ----
        value: Number to check
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)
        name: Name of the value for error message

    Returns:
    -------
        The number if in range

    Raises:
    ------
        ValidationError: If value is None or out of range
    """
    if value is None:
        raise ValidationError(f"{name} must not be None")
    if not min_value <= value <= max_value:
        raise ValidationError(
            f"{name} must be between {min_value} and {max_value}, got {value}"
        )
    return value


def require_list_not_empty(value: list | None, name: str = "value") -> list:
    """Require that a list is not None or empty.

    Args:
    ----
        value: List to check
        name: Name of the value for error message

    Returns:
    -------
        The list if not None or empty

    Raises:
    ------
        ValidationError: If value is None or empty list
    """
    if value is None:
        raise ValidationError(f"{name} must not be None")
    if not value:
        raise ValidationError(f"{name} must not be empty")
    return value


def require_dict_not_empty(value: dict | None, name: str = "value") -> dict:
    """Require that a dict is not None or empty.

    Args:
    ----
        value: Dict to check
        name: Name of the value for error message

    Returns:
    -------
        The dict if not None or empty

    Raises:
    ------
        ValidationError: If value is None or empty dict
    """
    if value is None:
        raise ValidationError(f"{name} must not be None")
    if not value:
        raise ValidationError(f"{name} must not be empty")
    return value


def require_type(value: Any, expected_type: type, name: str = "value") -> Any:
    """Require that a value is of expected type.

    Args:
    ----
        value: Value to check
        expected_type: Expected type
        name: Name of the value for error message

    Returns:
    -------
        The value if of expected type

    Raises:
    ------
        ValidationError: If value is None or wrong type
    """
    if value is None:
        raise ValidationError(f"{name} must not be None")
    if not isinstance(value, expected_type):
        raise ValidationError(
            f"{name} must be of type {expected_type.__name__}, got {type(value).__name__}"
        )
    return value


def validate_params(**validators):
    """Decorator to validate function parameters.

    Args:
    ----
        **validators: Mapping of parameter names to validator functions

    Returns:
    -------
        Decorated function with parameter validation

    Example:
    -------
        @validate_params(
            name=require_not_empty,
            count=require_positive
        )
        def process(name: str, count: int):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature
            import inspect
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # Validate parameters
            for param_name, validator in validators.items():
                if param_name in bound.arguments:
                    value = bound.arguments[param_name]
                    try:
                        validated = validator(value, param_name)
                        bound.arguments[param_name] = validated
                    except ValidationError:
                        raise

            return func(**bound.arguments)

        return wrapper
    return decorator


def validate_async_params(**validators):
    """Decorator to validate async function parameters.

    Args:
    ----
        **validators: Mapping of parameter names to validator functions

    Returns:
    -------
        Decorated async function with parameter validation

    Example:
    -------
        @validate_async_params(
            name=require_not_empty,
            count=require_positive
        )
        async def process(name: str, count: int):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get function signature
            import inspect
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # Validate parameters
            for param_name, validator in validators.items():
                if param_name in bound.arguments:
                    value = bound.arguments[param_name]
                    try:
                        validated = validator(value, param_name)
                        bound.arguments[param_name] = validated
                    except ValidationError:
                        raise

            return await func(**bound.arguments)

        return wrapper
    return decorator


def validate_return_not_none(func: Callable) -> Callable:
    """Decorator to ensure function doesn't return None.

    Args:
    ----
        func: Function to decorate

    Returns:
    -------
        Decorated function that raises if return value is None
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if result is None:
            raise ValidationError(
                f"{func.__name__} returned None but must return a value"
            )
        return result

    return wrapper


def validate_async_return_not_none(func: Callable) -> Callable:
    """Decorator to ensure async function doesn't return None.

    Args:
    ----
        func: Async function to decorate

    Returns:
    -------
        Decorated async function that raises if return value is None
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        if result is None:
            raise ValidationError(
                f"{func.__name__} returned None but must return a value"
            )
        return result

    return wrapper


def default_if_none(value: T | None, default: T) -> T:
    """Return default value if value is None.

    Args:
    ----
        value: Value to check
        default: Default value to return if value is None

    Returns:
    -------
        Value if not None, otherwise default
    """
    return default if value is None else value


def filter_none_values(data: dict) -> dict:
    """Filter out None values from dictionary.

    Args:
    ----
        data: Dictionary to filter

    Returns:
    -------
        New dictionary without None values
    """
    return {k: v for k, v in data.items() if v is not None}


def has_none_values(data: dict) -> bool:
    """Check if dictionary contains any None values.

    Args:
    ----
        data: Dictionary to check

    Returns:
    -------
        True if any values are None
    """
    return any(v is None for v in data.values())


def require_all_not_none(data: dict, prefix: str = "") -> dict:
    """Require that all dictionary values are not None.

    Args:
    ----
        data: Dictionary to check
        prefix: Prefix for error message keys

    Returns:
    -------
        The dictionary if all values are not None

    Raises:
    ------
        ValidationError: If any value is None
    """
    for key, value in data.items():
        if value is None:
            name = f"{prefix}.{key}" if prefix else key
            raise ValidationError(f"{name} must not be None")
    return data


def validate_list_items(
    items: list | None,
    validator: Callable[[Any, str], Any],
    name: str = "items"
) -> list:
    """Validate all items in a list.

    Args:
    ----
        items: List to validate
        validator: Validator function for each item
        name: Name for error messages

    Returns:
    -------
        List with validated items

    Raises:
    ------
        ValidationError: If list is None or any item fails validation
    """
    if items is None:
        raise ValidationError(f"{name} must not be None")

    validated = []
    for i, item in enumerate(items):
        try:
            validated_item = validator(item, f"{name}[{i}]")
            validated.append(validated_item)
        except ValidationError:
            raise

    return validated
