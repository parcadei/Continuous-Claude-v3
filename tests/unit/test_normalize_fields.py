"""Unit tests for field normalization."""

from runtime.normalize_fields import (
    get_normalization_strategy,
    normalize_ado_fields,
    normalize_field_names,
    update_normalization_config,
)


def test_ado_normalization_system_fields():
    """Test ADO normalization for system.* fields."""
    input_obj = {"system.title": "Task Title", "system.id": 123}

    result = normalize_ado_fields(input_obj)

    assert result == {"System.title": "Task Title", "System.id": 123}


def test_ado_normalization_microsoft_fields():
    """Test ADO normalization for microsoft.* fields."""
    input_obj = {"microsoft.vsts.common.priority": 1}

    result = normalize_ado_fields(input_obj)

    assert result == {"Microsoft.vsts.common.priority": 1}


def test_ado_normalization_custom_fields():
    """Test ADO normalization for custom.* fields."""
    input_obj = {"custom.myfield": "value"}

    result = normalize_ado_fields(input_obj)

    assert result == {"Custom.myfield": "value"}


def test_ado_normalization_wef_fields():
    """Test ADO normalization for wef_* fields."""
    input_obj = {"wef_123": "value"}

    result = normalize_ado_fields(input_obj)

    assert result == {"WEF_123": "value"}


def test_ado_normalization_nested_structures():
    """Test ADO normalization with nested dicts and lists."""
    input_obj = {
        "fields": {"system.title": "Title", "custom.status": "Active"},
        "tags": ["system.tag1", "system.tag2"],
    }

    result = normalize_ado_fields(input_obj)

    assert result == {
        "fields": {"System.title": "Title", "Custom.status": "Active"},
        "tags": ["system.tag1", "system.tag2"],  # Strings unchanged
    }


def test_ado_normalization_immutability():
    """Test that normalization returns new object (immutable)."""
    original = {"system.title": "Original"}

    result = normalize_ado_fields(original)

    # Modify result
    result["system.title"] = "Modified"

    # Original unchanged
    assert original == {"system.title": "Original"}


def test_ado_normalization_primitives():
    """Test that primitives are returned unchanged."""
    assert normalize_ado_fields(None) is None
    assert normalize_ado_fields("string") == "string"
    assert normalize_ado_fields(123) == 123
    assert normalize_ado_fields(True) is True


def test_ado_normalization_recursion():
    """Test deep recursion with nested structures."""
    input_obj = {
        "level1": {
            "level2": {"level3": {"system.field": "deep"}},
            "list": [{"system.item": 1}, {"system.item": 2}],
        }
    }

    result = normalize_ado_fields(input_obj)

    assert result == {
        "level1": {
            "level2": {"level3": {"System.field": "deep"}},
            "list": [{"System.item": 1}, {"System.item": 2}],
        }
    }


def test_normalize_field_names_strategy_dispatch():
    """Test that normalize_field_names dispatches to correct strategy."""
    input_obj = {"system.title": "Title"}

    # Test ADO strategy
    result_ado = normalize_field_names(input_obj, "ado")
    assert result_ado == {"System.title": "Title"}

    # Test none strategy
    result_none = normalize_field_names(input_obj, "github")
    assert result_none == {"system.title": "Title"}


def test_update_normalization_config():
    """Test updating normalization configuration."""
    update_normalization_config("myserver", "ado-pascal-case")

    input_obj = {"system.title": "Title"}
    result = normalize_field_names(input_obj, "myserver")

    assert result == {"System.title": "Title"}


def test_get_normalization_strategy():
    """Test getting normalization strategy for a server."""
    # Test default strategies
    assert get_normalization_strategy("ado") == "ado-pascal-case"
    assert get_normalization_strategy("github") == "none"
    assert get_normalization_strategy("filesystem") == "none"

    # Test unknown server (defaults to "none")
    assert get_normalization_strategy("unknown-server") == "none"


def test_normalize_field_names_unknown_strategy():
    """Test that unknown strategies return objects unchanged."""
    # This would require setting an invalid strategy, but the typing prevents it
    # Instead, test the fallback for unknown server names (defaults to "none")
    input_obj = {"system.title": "Title"}
    result = normalize_field_names(input_obj, "unknown-server")

    # Unknown server defaults to "none" strategy, which returns unchanged
    assert result == {"system.title": "Title"}


def test_ado_normalization_unknown_type():
    """Test that unknown types (non-dict, non-list, non-primitive) are returned unchanged."""

    # Test with a custom object
    class CustomObject:
        pass

    custom_obj = CustomObject()
    result = normalize_ado_fields(custom_obj)

    # Unknown type should be returned as-is
    assert result is custom_obj
