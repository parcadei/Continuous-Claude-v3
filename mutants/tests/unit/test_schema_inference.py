"""Unit tests for schema inference."""

from runtime.schema_inference import (
    infer_pydantic_model_from_response,
    infer_python_type,
    merge_response_schemas,
)


def test_infer_python_type_primitives():
    """Test primitive type inference."""
    assert infer_python_type("hello") == "str"
    assert infer_python_type(42) == "int"
    assert infer_python_type(3.14) == "float"
    assert infer_python_type(True) == "bool"
    assert infer_python_type(None) == "Optional[Any]"


def test_infer_python_type_list():
    """Test list type inference."""
    assert infer_python_type([1, 2, 3]) == "List[int]"
    assert infer_python_type(["a", "b"]) == "List[str]"
    assert infer_python_type([]) == "List[Any]"


def test_infer_python_type_dict():
    """Test dict type inference."""
    assert infer_python_type({"name": "John"}) == "Dict[str, str]"
    assert infer_python_type({"count": 42}) == "Dict[str, int]"
    assert infer_python_type({}) == "Dict[str, Any]"


def test_infer_pydantic_model_simple():
    """Test simple model inference."""
    response = {"name": "John", "age": 30}
    code = infer_pydantic_model_from_response("get_user", response)

    assert "class GetUserResult(BaseModel):" in code
    assert "name: Optional[str] = None" in code
    assert "age: Optional[int] = None" in code


def test_infer_pydantic_model_nested():
    """Test nested structure inference."""
    response = {
        "user": {"name": "John", "age": 30},
        "tags": ["python", "mcp"],
    }
    code = infer_pydantic_model_from_response("get_user", response)

    assert "class GetUserResult(BaseModel):" in code
    assert "user: Optional[Dict[str, Any]] = None" in code
    assert "tags: Optional[List[str]] = None" in code


def test_merge_response_schemas():
    """Test schema merging."""
    schemas = [
        {"name": "John", "age": 30},
        {"name": "Jane", "age": 25},
    ]

    merged = merge_response_schemas(schemas)

    assert merged["name"] == "str"
    assert merged["age"] == "int"


def test_merge_response_schemas_mixed_types():
    """Test merging with mixed types."""
    schemas = [
        {"id": 1},  # int
        {"id": "abc"},  # str
    ]

    merged = merge_response_schemas(schemas)

    # Mixed types default to Any
    assert merged["id"] == "Any"
