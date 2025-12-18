"""Tests for validation utilities."""

import pytest

from knowgraph.shared.validation import (
    ValidationError,
    default_if_none,
    filter_none_values,
    has_none_values,
    require_all_not_none,
    require_dict_not_empty,
    require_in_range,
    require_list_not_empty,
    require_non_negative,
    require_not_empty,
    require_not_none,
    require_positive,
    require_type,
    validate_async_params,
    validate_async_return_not_none,
    validate_list_items,
    validate_params,
    validate_return_not_none,
)


class TestRequireNotNone:
    """Test require_not_none function."""

    def test_valid_value(self):
        """Test with valid non-None value."""
        result = require_not_none("test", "param")
        assert result == "test"

    def test_none_value(self):
        """Test with None value raises error."""
        with pytest.raises(ValidationError, match="param must not be None"):
            require_not_none(None, "param")

    def test_zero_is_valid(self):
        """Test that zero is considered valid."""
        result = require_not_none(0, "count")
        assert result == 0

    def test_empty_string_is_valid(self):
        """Test that empty string is considered valid for this function."""
        result = require_not_none("", "text")
        assert result == ""


class TestRequireNotEmpty:
    """Test require_not_empty function."""

    def test_valid_string(self):
        """Test with valid non-empty string."""
        result = require_not_empty("hello", "text")
        assert result == "hello"

    def test_none_value(self):
        """Test with None value raises error."""
        with pytest.raises(ValidationError, match="text must not be None"):
            require_not_empty(None, "text")

    def test_empty_string(self):
        """Test with empty string raises error."""
        with pytest.raises(ValidationError, match="text must not be empty"):
            require_not_empty("", "text")

    def test_whitespace_only(self):
        """Test with whitespace-only string raises error."""
        with pytest.raises(ValidationError, match="text must not be empty"):
            require_not_empty("   ", "text")

    def test_string_with_content(self):
        """Test with string containing whitespace and content."""
        result = require_not_empty("  hello  ", "text")
        assert result == "  hello  "


class TestRequirePositive:
    """Test require_positive function."""

    def test_positive_integer(self):
        """Test with positive integer."""
        result = require_positive(5, "count")
        assert result == 5

    def test_positive_float(self):
        """Test with positive float."""
        result = require_positive(3.14, "value")
        assert result == 3.14

    def test_zero(self):
        """Test with zero raises error."""
        with pytest.raises(ValidationError, match="count must be positive"):
            require_positive(0, "count")

    def test_negative(self):
        """Test with negative value raises error."""
        with pytest.raises(ValidationError, match="count must be positive"):
            require_positive(-5, "count")

    def test_none_value(self):
        """Test with None raises error."""
        with pytest.raises(ValidationError, match="count must not be None"):
            require_positive(None, "count")


class TestRequireNonNegative:
    """Test require_non_negative function."""

    def test_positive_value(self):
        """Test with positive value."""
        result = require_non_negative(5, "count")
        assert result == 5

    def test_zero(self):
        """Test with zero is valid."""
        result = require_non_negative(0, "count")
        assert result == 0

    def test_negative(self):
        """Test with negative value raises error."""
        with pytest.raises(ValidationError, match="count must be non-negative"):
            require_non_negative(-1, "count")

    def test_none_value(self):
        """Test with None raises error."""
        with pytest.raises(ValidationError, match="count must not be None"):
            require_non_negative(None, "count")


class TestRequireInRange:
    """Test require_in_range function."""

    def test_value_in_range(self):
        """Test with value in range."""
        result = require_in_range(5, 0, 10, "value")
        assert result == 5

    def test_value_at_min(self):
        """Test with value at minimum."""
        result = require_in_range(0, 0, 10, "value")
        assert result == 0

    def test_value_at_max(self):
        """Test with value at maximum."""
        result = require_in_range(10, 0, 10, "value")
        assert result == 10

    def test_value_below_range(self):
        """Test with value below range raises error."""
        with pytest.raises(ValidationError, match="value must be between 0 and 10"):
            require_in_range(-1, 0, 10, "value")

    def test_value_above_range(self):
        """Test with value above range raises error."""
        with pytest.raises(ValidationError, match="value must be between 0 and 10"):
            require_in_range(11, 0, 10, "value")

    def test_none_value(self):
        """Test with None raises error."""
        with pytest.raises(ValidationError, match="value must not be None"):
            require_in_range(None, 0, 10, "value")


class TestRequireListNotEmpty:
    """Test require_list_not_empty function."""

    def test_non_empty_list(self):
        """Test with non-empty list."""
        result = require_list_not_empty([1, 2, 3], "items")
        assert result == [1, 2, 3]

    def test_empty_list(self):
        """Test with empty list raises error."""
        with pytest.raises(ValidationError, match="items must not be empty"):
            require_list_not_empty([], "items")

    def test_none_value(self):
        """Test with None raises error."""
        with pytest.raises(ValidationError, match="items must not be None"):
            require_list_not_empty(None, "items")


class TestRequireDictNotEmpty:
    """Test require_dict_not_empty function."""

    def test_non_empty_dict(self):
        """Test with non-empty dict."""
        result = require_dict_not_empty({"a": 1}, "data")
        assert result == {"a": 1}

    def test_empty_dict(self):
        """Test with empty dict raises error."""
        with pytest.raises(ValidationError, match="data must not be empty"):
            require_dict_not_empty({}, "data")

    def test_none_value(self):
        """Test with None raises error."""
        with pytest.raises(ValidationError, match="data must not be None"):
            require_dict_not_empty(None, "data")


class TestRequireType:
    """Test require_type function."""

    def test_correct_type(self):
        """Test with correct type."""
        result = require_type("hello", str, "text")
        assert result == "hello"

    def test_wrong_type(self):
        """Test with wrong type raises error."""
        with pytest.raises(ValidationError, match="value must be of type str, got int"):
            require_type(123, str, "value")

    def test_none_value(self):
        """Test with None raises error."""
        with pytest.raises(ValidationError, match="value must not be None"):
            require_type(None, str, "value")


class TestValidateParams:
    """Test validate_params decorator."""

    def test_valid_params(self):
        """Test decorator with valid parameters."""
        @validate_params(
            name=require_not_empty,
            count=require_positive
        )
        def process(name: str, count: int):
            return f"{name}: {count}"

        result = process("test", 5)
        assert result == "test: 5"

    def test_invalid_param(self):
        """Test decorator with invalid parameter."""
        @validate_params(
            name=require_not_empty,
            count=require_positive
        )
        def process(name: str, count: int):
            return f"{name}: {count}"

        with pytest.raises(ValidationError, match="count must be positive"):
            process("test", 0)

    def test_none_param(self):
        """Test decorator with None parameter."""
        @validate_params(name=require_not_none)
        def process(name: str):
            return name

        with pytest.raises(ValidationError, match="name must not be None"):
            process(None)

    def test_optional_param(self):
        """Test decorator with optional parameter."""
        @validate_params(name=require_not_empty)
        def process(name: str, optional: str = "default"):
            return f"{name}-{optional}"

        result = process("test")
        assert result == "test-default"


class TestValidateAsyncParams:
    """Test validate_async_params decorator."""

    @pytest.mark.asyncio
    async def test_valid_params(self):
        """Test decorator with valid parameters."""
        @validate_async_params(
            name=require_not_empty,
            count=require_positive
        )
        async def process(name: str, count: int):
            return f"{name}: {count}"

        result = await process("test", 5)
        assert result == "test: 5"

    @pytest.mark.asyncio
    async def test_invalid_param(self):
        """Test decorator with invalid parameter."""
        @validate_async_params(count=require_positive)
        async def process(count: int):
            return count

        with pytest.raises(ValidationError, match="count must be positive"):
            await process(0)


class TestValidateReturnNotNone:
    """Test validate_return_not_none decorator."""

    def test_valid_return(self):
        """Test with valid non-None return."""
        @validate_return_not_none
        def get_value():
            return "test"

        result = get_value()
        assert result == "test"

    def test_none_return(self):
        """Test with None return raises error."""
        @validate_return_not_none
        def get_value():
            return None

        with pytest.raises(ValidationError, match="get_value returned None"):
            get_value()

    def test_zero_return(self):
        """Test that zero return is valid."""
        @validate_return_not_none
        def get_value():
            return 0

        result = get_value()
        assert result == 0


class TestValidateAsyncReturnNotNone:
    """Test validate_async_return_not_none decorator."""

    @pytest.mark.asyncio
    async def test_valid_return(self):
        """Test with valid non-None return."""
        @validate_async_return_not_none
        async def get_value():
            return "test"

        result = await get_value()
        assert result == "test"

    @pytest.mark.asyncio
    async def test_none_return(self):
        """Test with None return raises error."""
        @validate_async_return_not_none
        async def get_value():
            return None

        with pytest.raises(ValidationError, match="get_value returned None"):
            await get_value()


class TestDefaultIfNone:
    """Test default_if_none function."""

    def test_none_value(self):
        """Test with None returns default."""
        result = default_if_none(None, "default")
        assert result == "default"

    def test_non_none_value(self):
        """Test with non-None returns value."""
        result = default_if_none("value", "default")
        assert result == "value"

    def test_zero_value(self):
        """Test with zero returns zero, not default."""
        result = default_if_none(0, 10)
        assert result == 0

    def test_empty_string(self):
        """Test with empty string returns empty string."""
        result = default_if_none("", "default")
        assert result == ""


class TestFilterNoneValues:
    """Test filter_none_values function."""

    def test_no_none_values(self):
        """Test with dict containing no None values."""
        data = {"a": 1, "b": 2}
        result = filter_none_values(data)
        assert result == {"a": 1, "b": 2}

    def test_some_none_values(self):
        """Test with dict containing some None values."""
        data = {"a": 1, "b": None, "c": 3}
        result = filter_none_values(data)
        assert result == {"a": 1, "c": 3}

    def test_all_none_values(self):
        """Test with dict containing all None values."""
        data = {"a": None, "b": None}
        result = filter_none_values(data)
        assert result == {}

    def test_empty_dict(self):
        """Test with empty dict."""
        result = filter_none_values({})
        assert result == {}


class TestHasNoneValues:
    """Test has_none_values function."""

    def test_no_none_values(self):
        """Test with dict containing no None values."""
        data = {"a": 1, "b": 2}
        assert has_none_values(data) is False

    def test_some_none_values(self):
        """Test with dict containing some None values."""
        data = {"a": 1, "b": None}
        assert has_none_values(data) is True

    def test_all_none_values(self):
        """Test with dict containing all None values."""
        data = {"a": None, "b": None}
        assert has_none_values(data) is True

    def test_empty_dict(self):
        """Test with empty dict."""
        assert has_none_values({}) is False


class TestRequireAllNotNone:
    """Test require_all_not_none function."""

    def test_no_none_values(self):
        """Test with dict containing no None values."""
        data = {"a": 1, "b": 2}
        result = require_all_not_none(data)
        assert result == {"a": 1, "b": 2}

    def test_with_none_value(self):
        """Test with dict containing None value raises error."""
        data = {"a": 1, "b": None}
        with pytest.raises(ValidationError, match="b must not be None"):
            require_all_not_none(data)

    def test_with_prefix(self):
        """Test error message includes prefix."""
        data = {"field": None}
        with pytest.raises(ValidationError, match="obj.field must not be None"):
            require_all_not_none(data, prefix="obj")

    def test_empty_dict(self):
        """Test with empty dict."""
        result = require_all_not_none({})
        assert result == {}


class TestValidateListItems:
    """Test validate_list_items function."""

    def test_valid_items(self):
        """Test with all valid items."""
        items = ["a", "b", "c"]
        result = validate_list_items(items, require_not_empty, "texts")
        assert result == ["a", "b", "c"]

    def test_invalid_item(self):
        """Test with invalid item raises error."""
        items = ["a", "", "c"]
        with pytest.raises(ValidationError, match="texts\\[1\\] must not be empty"):
            validate_list_items(items, require_not_empty, "texts")

    def test_none_list(self):
        """Test with None list raises error."""
        with pytest.raises(ValidationError, match="texts must not be None"):
            validate_list_items(None, require_not_empty, "texts")

    def test_empty_list(self):
        """Test with empty list returns empty list."""
        result = validate_list_items([], require_not_empty, "texts")
        assert result == []

    def test_with_numbers(self):
        """Test validating list of numbers."""
        items = [1, 2, 3]
        result = validate_list_items(items, require_positive, "counts")
        assert result == [1, 2, 3]


class TestValidationEdgeCases:
    """Test edge cases in validation."""

    def test_nested_validation(self):
        """Test nested validation calls."""
        @validate_params(name=require_not_empty)
        def process(name: str):
            return require_positive(len(name), "length")

        result = process("test")
        assert result == 4

    def test_multiple_validators(self):
        """Test multiple validators on same parameter."""
        def validate_username(value, name):
            value = require_not_none(value, name)
            value = require_not_empty(value, name)
            # Validate length but return original value
            require_in_range(len(value), 3, 20, f"{name} length")
            return value

        result = validate_username("john_doe", "username")
        assert result == "john_doe"

        with pytest.raises(ValidationError):
            validate_username("ab", "username")

    def test_conditional_validation(self):
        """Test conditional validation logic."""
        def validate_optional_positive(value, name):
            if value is not None:
                return require_positive(value, name)
            return value

        assert validate_optional_positive(5, "count") == 5
        assert validate_optional_positive(None, "count") is None

        with pytest.raises(ValidationError):
            validate_optional_positive(0, "count")

    def test_custom_error_messages(self):
        """Test custom error message in ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            require_positive(-1, "count")

        assert "count must be positive" in str(exc_info.value)

    def test_validation_preserves_type(self):
        """Test that validation preserves original type."""
        int_result = require_positive(5, "count")
        assert isinstance(int_result, int)

        float_result = require_positive(3.14, "value")
        assert isinstance(float_result, float)
