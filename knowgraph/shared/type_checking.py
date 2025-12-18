"""Type checking utilities for KnowGraph.

Provides runtime type checking and validation with comprehensive type hints.
"""

from typing import Any, TypeGuard, get_args, get_origin

from knowgraph.shared.type_aliases import JsonDict, JsonList, JsonValue, PathLike
from knowgraph.shared.validation import ValidationError


def is_json_dict(value: Any) -> TypeGuard[JsonDict]:
    """Check if value is a valid JSON dictionary.

    Args:
    ----
        value: Value to check

    Returns:
    -------
        True if value is a JSON-compatible dictionary
    """
    if not isinstance(value, dict):
        return False

    # Check all keys are strings
    if not all(isinstance(k, str) for k in value):
        return False

    # Check all values are JSON-compatible
    return all(is_json_value(v) for v in value.values())


def is_json_list(value: Any) -> TypeGuard[JsonList]:
    """Check if value is a valid JSON list.

    Args:
    ----
        value: Value to check

    Returns:
    -------
        True if value is a JSON-compatible list
    """
    if not isinstance(value, list):
        return False

    return all(is_json_value(item) for item in value)


def is_json_value(value: Any) -> TypeGuard[JsonValue]:
    """Check if value is JSON-serializable.

    Args:
    ----
        value: Value to check

    Returns:
    -------
        True if value is JSON-compatible
    """
    if value is None:
        return True

    if isinstance(value, (str, int, float, bool)):
        return True

    if isinstance(value, dict):
        return is_json_dict(value)

    if isinstance(value, list):
        return is_json_list(value)

    return False


def is_path_like(value: Any) -> TypeGuard[PathLike]:
    """Check if value is path-like.

    Args:
    ----
        value: Value to check

    Returns:
    -------
        True if value is a string or Path object
    """
    from pathlib import Path
    return isinstance(value, (str, Path))


def assert_type(value: Any, expected_type: type, name: str = "value") -> None:
    """Assert that value is of expected type.

    Args:
    ----
        value: Value to check
        expected_type: Expected type
        name: Name for error message

    Raises:
    ------
        ValidationError: If value is not of expected type
    """
    if not isinstance(value, expected_type):
        raise ValidationError(
            f"{name} must be of type {expected_type.__name__}, got {type(value).__name__}"
        )


def assert_json_dict(value: Any, name: str = "value") -> JsonDict:
    """Assert that value is a JSON dictionary.

    Args:
    ----
        value: Value to check
        name: Name for error message

    Returns:
    -------
        The value if it's a valid JSON dictionary

    Raises:
    ------
        ValidationError: If value is not a JSON dictionary
    """
    if not is_json_dict(value):
        raise ValidationError(f"{name} must be a JSON-compatible dictionary")
    return value


def assert_json_list(value: Any, name: str = "value") -> JsonList:
    """Assert that value is a JSON list.

    Args:
    ----
        value: Value to check
        name: Name for error message

    Returns:
    -------
        The value if it's a valid JSON list

    Raises:
    ------
        ValidationError: If value is not a JSON list
    """
    if not is_json_list(value):
        raise ValidationError(f"{name} must be a JSON-compatible list")
    return value


def assert_json_value(value: Any, name: str = "value") -> JsonValue:
    """Assert that value is JSON-serializable.

    Args:
    ----
        value: Value to check
        name: Name for error message

    Returns:
    -------
        The value if it's JSON-serializable

    Raises:
    ------
        ValidationError: If value is not JSON-serializable
    """
    if not is_json_value(value):
        raise ValidationError(f"{name} must be JSON-serializable")
    return value


def check_type_hint(value: Any, type_hint: type) -> bool:
    """Check if value matches type hint.

    Args:
    ----
        value: Value to check
        type_hint: Type hint to check against

    Returns:
    -------
        True if value matches type hint

    Note:
    ----
        This is a simplified implementation for common cases.
        For complex type hints, use mypy or other static type checkers.
    """
    from typing import Union

    origin = get_origin(type_hint)

    # Handle None/NoneType
    if type_hint is type(None):
        return value is None

    # Handle Union types (including Optional)
    if origin is Union:
        # For Union types, check if value matches any of the types
        args = get_args(type_hint)
        return any(check_type_hint(value, arg) for arg in args)

    # Handle Python 3.10+ union syntax (str | int)
    import types
    if isinstance(type_hint, types.UnionType):
        args = get_args(type_hint)
        return any(check_type_hint(value, arg) for arg in args)

    # Handle list types
    if origin is list:
        if not isinstance(value, list):
            return False
        args = get_args(type_hint)
        if args:
            return all(check_type_hint(item, args[0]) for item in value)
        return True

    # Handle dict types
    if origin is dict:
        if not isinstance(value, dict):
            return False
        args = get_args(type_hint)
        if len(args) == 2:
            key_type, val_type = args
            return all(
                check_type_hint(k, key_type) and check_type_hint(v, val_type)
                for k, v in value.items()
            )
        return True

    # Handle basic types
    if isinstance(type_hint, type):
        return isinstance(value, type_hint)

    # For other complex types, just return True
    return True


def validate_type_hints(func, args: tuple, kwargs: dict) -> None:
    """Validate function arguments against type hints.

    Args:
    ----
        func: Function to validate
        args: Positional arguments
        kwargs: Keyword arguments

    Raises:
    ------
        ValidationError: If any argument doesn't match its type hint

    Note:
    ----
        This requires Python 3.10+ for full support of type hints.
    """
    import inspect

    sig = inspect.signature(func)
    bound = sig.bind(*args, **kwargs)
    bound.apply_defaults()

    for param_name, param_value in bound.arguments.items():
        param = sig.parameters[param_name]

        if param.annotation is not inspect.Parameter.empty:
            if not check_type_hint(param_value, param.annotation):
                raise ValidationError(
                    f"Parameter '{param_name}' has invalid type: "
                    f"expected {param.annotation}, got {type(param_value).__name__}"
                )


def get_type_name(type_hint: Any) -> str:
    """Get a human-readable name for a type hint.

    Args:
    ----
        type_hint: Type hint to get name for

    Returns:
    -------
        String representation of the type hint
    """
    if type_hint is type(None):
        return "None"

    if hasattr(type_hint, "__name__"):
        return type_hint.__name__

    origin = get_origin(type_hint)
    args = get_args(type_hint)

    if origin is not None:
        if args:
            arg_names = ", ".join(get_type_name(arg) for arg in args)
            return f"{get_type_name(origin)}[{arg_names}]"
        return get_type_name(origin)

    return str(type_hint)
