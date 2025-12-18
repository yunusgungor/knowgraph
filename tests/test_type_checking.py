"""Tests for type checking utilities."""

from typing import Any

import pytest

from knowgraph.shared.type_aliases import JsonDict, JsonValue, PathLike
from knowgraph.shared.type_checking import (
    assert_json_dict,
    assert_json_list,
    assert_json_value,
    assert_type,
    check_type_hint,
    get_type_name,
    is_json_dict,
    is_json_list,
    is_json_value,
    is_path_like,
    validate_type_hints,
)
from knowgraph.shared.validation import ValidationError


class TestJsonTypeGuards:
    """Test JSON type guard functions."""

    def test_is_json_dict_valid(self):
        """Test valid JSON dictionaries."""
        assert is_json_dict({})
        assert is_json_dict({"a": 1, "b": "text"})
        assert is_json_dict({"nested": {"key": "value"}})
        assert is_json_dict({"list": [1, 2, 3]})

    def test_is_json_dict_invalid(self):
        """Test invalid JSON dictionaries."""
        assert not is_json_dict("not a dict")
        assert not is_json_dict([1, 2, 3])
        assert not is_json_dict({1: "value"})  # Non-string key
        assert not is_json_dict({"key": object()})  # Non-JSON value

    def test_is_json_list_valid(self):
        """Test valid JSON lists."""
        assert is_json_list([])
        assert is_json_list([1, 2, 3])
        assert is_json_list(["a", "b", "c"])
        assert is_json_list([{"key": "value"}])
        assert is_json_list([[1, 2], [3, 4]])

    def test_is_json_list_invalid(self):
        """Test invalid JSON lists."""
        assert not is_json_list("not a list")
        assert not is_json_list({"key": "value"})
        assert not is_json_list([object()])

    def test_is_json_value_primitives(self):
        """Test JSON value checking for primitives."""
        assert is_json_value(None)
        assert is_json_value("string")
        assert is_json_value(123)
        assert is_json_value(3.14)
        assert is_json_value(True)
        assert is_json_value(False)

    def test_is_json_value_collections(self):
        """Test JSON value checking for collections."""
        assert is_json_value([])
        assert is_json_value({})
        assert is_json_value([1, "two", 3.0])
        assert is_json_value({"key": [1, 2, 3]})

    def test_is_json_value_invalid(self):
        """Test JSON value checking for invalid types."""
        assert not is_json_value(object())
        assert not is_json_value(lambda x: x)
        assert not is_json_value({1, 2, 3})  # set


class TestPathLike:
    """Test path-like type checking."""

    def test_is_path_like_string(self):
        """Test string paths."""
        assert is_path_like("/path/to/file")
        assert is_path_like("relative/path")
        assert is_path_like("")

    def test_is_path_like_path(self):
        """Test Path objects."""
        from pathlib import Path

        assert is_path_like(Path("/path/to/file"))
        assert is_path_like(Path("relative/path"))

    def test_is_path_like_invalid(self):
        """Test non-path types."""
        assert not is_path_like(123)
        assert not is_path_like(["/path"])
        assert not is_path_like(None)


class TestAssertType:
    """Test type assertion functions."""

    def test_assert_type_valid(self):
        """Test with valid types."""
        assert_type("text", str, "param")
        assert_type(123, int, "count")
        assert_type([1, 2], list, "items")

    def test_assert_type_invalid(self):
        """Test with invalid types."""
        with pytest.raises(ValidationError, match="param must be of type str"):
            assert_type(123, str, "param")

    def test_assert_json_dict_valid(self):
        """Test with valid JSON dict."""
        result = assert_json_dict({"a": 1}, "data")
        assert result == {"a": 1}

    def test_assert_json_dict_invalid(self):
        """Test with invalid JSON dict."""
        with pytest.raises(ValidationError, match="data must be a JSON-compatible"):
            assert_json_dict("not a dict", "data")

    def test_assert_json_list_valid(self):
        """Test with valid JSON list."""
        result = assert_json_list([1, 2, 3], "items")
        assert result == [1, 2, 3]

    def test_assert_json_list_invalid(self):
        """Test with invalid JSON list."""
        with pytest.raises(ValidationError, match="items must be a JSON-compatible"):
            assert_json_list("not a list", "items")

    def test_assert_json_value_valid(self):
        """Test with valid JSON value."""
        assert assert_json_value("text", "value") == "text"
        assert assert_json_value(123, "value") == 123
        assert assert_json_value([1, 2], "value") == [1, 2]

    def test_assert_json_value_invalid(self):
        """Test with invalid JSON value."""
        with pytest.raises(ValidationError, match="value must be JSON-serializable"):
            assert_json_value(object(), "value")


class TestCheckTypeHint:
    """Test type hint checking."""

    def test_basic_types(self):
        """Test basic type checking."""
        assert check_type_hint("text", str)
        assert check_type_hint(123, int)
        assert check_type_hint(3.14, float)
        assert check_type_hint(True, bool)

    def test_none_type(self):
        """Test None type checking."""
        assert check_type_hint(None, type(None))
        assert not check_type_hint("text", type(None))

    def test_list_types(self):
        """Test list type checking."""
        assert check_type_hint([1, 2, 3], list[int])
        assert check_type_hint(["a", "b"], list[str])
        assert not check_type_hint([1, "two"], list[int])

    def test_dict_types(self):
        """Test dict type checking."""
        assert check_type_hint({"a": 1}, dict[str, int])
        assert check_type_hint({"x": "y"}, dict[str, str])
        assert not check_type_hint({1: "a"}, dict[str, int])

    def test_optional_types(self):
        """Test Optional type checking."""
        from typing import Optional

        assert check_type_hint(None, Optional[str])
        assert check_type_hint("text", Optional[str])
        assert not check_type_hint(123, Optional[str])

    def test_union_types(self):
        """Test Union type checking."""
        assert check_type_hint("text", str | int)
        assert check_type_hint(123, str | int)
        assert not check_type_hint([], str | int)

    def test_empty_list(self):
        """Test empty list checking."""
        assert check_type_hint([], list)
        assert check_type_hint([], list[int])

    def test_empty_dict(self):
        """Test empty dict checking."""
        assert check_type_hint({}, dict)
        assert check_type_hint({}, dict[str, int])


class TestValidateTypeHints:
    """Test function parameter type validation."""

    def test_valid_parameters(self):
        """Test with valid parameters."""
        def func(name: str, count: int) -> None:
            pass

        # Should not raise
        validate_type_hints(func, ("test", 5), {})

    def test_invalid_parameter(self):
        """Test with invalid parameter type."""
        def func(name: str, count: int) -> None:
            pass

        with pytest.raises(ValidationError, match="Parameter 'count' has invalid type"):
            validate_type_hints(func, ("test", "not_int"), {})

    def test_with_defaults(self):
        """Test with default parameters."""
        def func(name: str, count: int = 10) -> None:
            pass

        # Should not raise
        validate_type_hints(func, ("test",), {})

    def test_with_kwargs(self):
        """Test with keyword arguments."""
        def func(name: str, count: int) -> None:
            pass

        # Should not raise
        validate_type_hints(func, (), {"name": "test", "count": 5})

    def test_no_type_hints(self):
        """Test function without type hints."""
        def func(name, count):
            pass

        # Should not raise
        validate_type_hints(func, ("test", 5), {})


class TestGetTypeName:
    """Test type name extraction."""

    def test_basic_types(self):
        """Test basic type names."""
        assert get_type_name(str) == "str"
        assert get_type_name(int) == "int"
        assert get_type_name(list) == "list"

    def test_none_type(self):
        """Test None type name."""
        assert get_type_name(type(None)) == "None"

    def test_generic_types(self):
        """Test generic type names."""
        assert "list" in get_type_name(list[int]).lower()
        assert "dict" in get_type_name(dict[str, int]).lower()

    def test_optional_type(self):
        """Test Optional type name."""
        from typing import Optional

        name = get_type_name(Optional[str])
        assert "str" in name.lower() or "optional" in name.lower()


class TestTypeAliases:
    """Test type alias usage."""

    def test_path_like_usage(self):
        """Test PathLike type alias."""
        from pathlib import Path

        def process_path(path: PathLike) -> str:
            return str(path)

        assert process_path("/path/to/file") == "/path/to/file"
        assert process_path(Path("/path")) == "/path"

    def test_json_dict_usage(self):
        """Test JsonDict type alias."""
        def process_config(config: JsonDict) -> str:
            return config.get("name", "default")

        assert process_config({"name": "test"}) == "test"

    def test_json_value_usage(self):
        """Test JsonValue type alias."""
        def serialize(value: JsonValue) -> JsonValue:
            return value

        assert serialize("text") == "text"
        assert serialize(123) == 123
        assert serialize([1, 2]) == [1, 2]


class TestTypeCheckingEdgeCases:
    """Test edge cases in type checking."""

    def test_nested_collections(self):
        """Test nested collection type checking."""
        nested = {"a": [1, 2], "b": [3, 4]}
        assert is_json_dict(nested)

        nested_invalid = {"a": [object()]}
        assert not is_json_dict(nested_invalid)

    def test_deeply_nested(self):
        """Test deeply nested structures."""
        deep = {"level1": {"level2": {"level3": [1, 2, 3]}}}
        assert is_json_dict(deep)

    def test_mixed_types_in_list(self):
        """Test mixed types in list."""
        mixed = [1, "two", 3.0, None, True]
        assert is_json_list(mixed)

    def test_empty_collections(self):
        """Test empty collections."""
        assert is_json_dict({})
        assert is_json_list([])
        assert is_json_value({})
        assert is_json_value([])

    def test_unicode_strings(self):
        """Test unicode strings."""
        assert is_json_value("Hello 世界")
        assert is_json_dict({"key": "值"})

    def test_large_numbers(self):
        """Test large numbers."""
        assert is_json_value(10**100)
        assert is_json_value(1.7976931348623157e+308)  # Close to float max

    def test_boolean_values(self):
        """Test boolean values."""
        assert is_json_value(True)
        assert is_json_value(False)
        assert is_json_dict({"flag": True})
        assert is_json_list([True, False, True])


class TestTypeCheckingIntegration:
    """Test type checking integration scenarios."""

    def test_validate_api_response(self):
        """Test validating API response structure."""
        response: JsonDict = {
            "status": "success",
            "data": {"items": [1, 2, 3]},
            "count": 3
        }

        assert is_json_dict(response)
        assert_json_dict(response, "response")

    def test_validate_configuration(self):
        """Test validating configuration data."""
        config: JsonDict = {
            "database": {"host": "localhost", "port": 5432},
            "cache": {"enabled": True, "ttl": 300},
            "features": ["feature1", "feature2"]
        }

        assert is_json_dict(config)
        assert_json_dict(config, "config")

    def test_type_safe_function(self):
        """Test type-safe function with validation."""
        def process_data(data: JsonDict, items: list[str]) -> JsonValue:
            assert_json_dict(data, "data")
            assert_type(items, list, "items")
            return {"processed": True, "count": len(items)}

        result = process_data({"key": "value"}, ["a", "b"])
        assert is_json_dict(result)

    def test_type_guard_in_condition(self):
        """Test using type guards in conditional logic."""
        value: Any = {"key": "value"}

        if is_json_dict(value):
            # TypeGuard narrows type to JsonDict
            assert "key" in value
            assert value["key"] == "value"
