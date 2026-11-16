"""Unit tests for wrapper generation."""

from runtime.schema_utils import (
    generate_pydantic_model,
    json_schema_to_python_type,
    sanitize_name,
)


def test_json_schema_string_type():
    """Test string type conversion."""
    result = json_schema_to_python_type({"type": "string"}, required=True)
    assert result == "str"

    result = json_schema_to_python_type({"type": "string"}, required=False)
    assert result == "Optional[str]"


def test_json_schema_number_types():
    """Test number type conversions."""
    assert json_schema_to_python_type({"type": "number"}, True) == "float"
    assert json_schema_to_python_type({"type": "integer"}, True) == "int"


def test_json_schema_array_type():
    """Test array type conversion."""
    schema = {"type": "array", "items": {"type": "string"}}
    result = json_schema_to_python_type(schema, True)
    assert result == "List[str]"


def test_json_schema_enum_type():
    """Test enum (Literal) type conversion."""
    schema = {"enum": ["asc", "desc"]}
    result = json_schema_to_python_type(schema, True)
    assert 'Literal["asc", "desc"]' in result


def test_json_schema_union_type():
    """Test union type conversion."""
    schema = {"type": ["string", "null"]}
    result = json_schema_to_python_type(schema, True)
    assert result == "Optional[str]"


def test_json_schema_dict_type():
    """Test dict (additionalProperties) type conversion."""
    schema = {"type": "object", "additionalProperties": {"type": "string"}}
    result = json_schema_to_python_type(schema, True)
    assert result == "Dict[str, str]"


def test_generate_pydantic_model_simple():
    """Test simple Pydantic model generation."""
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name"],
    }

    result = generate_pydantic_model("Person", schema)

    assert "class Person(BaseModel):" in result
    assert "name: str" in result
    assert "age: Optional[int] = None" in result


def test_sanitize_name():
    """Test name sanitization."""
    assert sanitize_name("my-tool") == "my_tool"
    assert sanitize_name("my.tool") == "my_tool"
    assert sanitize_name("list") == "list_"
