"""
Type inference utilities for discovering Pydantic models from API responses.

This module infers Pydantic models from actual response data when output
schemas are not available or incomplete.
"""

from typing import Any


def infer_python_type(value: Any) -> str:
    """
    Infer Python type from a value.

    Args:
        value: The value to infer type from

    Returns:
        Python type hint string (e.g., "str", "int", "List[str]")

    Examples:
        >>> infer_python_type("hello")
        'str'
        >>> infer_python_type(42)
        'int'
        >>> infer_python_type([1, 2, 3])
        'List[int]'
    """
    if value is None:
        return "Optional[Any]"
    elif isinstance(value, bool):
        return "bool"
    elif isinstance(value, int):
        return "int"
    elif isinstance(value, float):
        return "float"
    elif isinstance(value, str):
        return "str"
    elif isinstance(value, list):
        if not value:
            return "List[Any]"
        # Infer from first element
        item_type = infer_python_type(value[0])
        return f"List[{item_type}]"
    elif isinstance(value, dict):
        if not value:
            return "Dict[str, Any]"
        # Check if all values have same type
        value_types = set(infer_python_type(v) for v in value.values())
        if len(value_types) == 1:
            value_type = value_types.pop()
            return f"Dict[str, {value_type}]"
        else:
            return "Dict[str, Any]"
    else:
        return "Any"


def infer_pydantic_model_from_response(
    tool_name: str,
    response_data: Any,
    description: str | None = None,
) -> str:
    """
    Infer Pydantic model from actual response data.

    All fields are marked Optional for defensive coding (handle missing data).

    Args:
        tool_name: Name of the tool that produced response
        response_data: Actual response data from tool execution
        description: Optional tool description

    Returns:
        Python code for Pydantic model

    Example:
        >>> response = {"name": "John", "age": 30, "tags": ["python", "mcp"]}
        >>> code = infer_pydantic_model_from_response("get_user", response)
        >>> print(code)
        class GetUserResult(BaseModel):
            '''Result from get_user tool.'''
            name: Optional[str] = None
            age: Optional[int] = None
            tags: Optional[List[str]] = None
    """
    # Normalize tool name for model name
    model_name = "".join(word.capitalize() for word in tool_name.split("_")) + "Result"

    if not isinstance(response_data, dict):
        # Non-dict responses become wrapped
        inferred_type = infer_python_type(response_data)
        return f"""
class {model_name}(BaseModel):
    '''Result from {tool_name} tool.'''
    value: {inferred_type} = None
"""

    # Build model fields from dict
    lines = [f"class {model_name}(BaseModel):"]

    # Add docstring
    if description:
        lines.append(f'    """{description}"""')
    else:
        lines.append(f'    """Result from {tool_name} tool."""')

    # Generate fields (all Optional for defensive coding)
    if not response_data:
        lines.append("    pass")
    else:
        for key, value in response_data.items():
            # Sanitize field name
            field_name = key.replace("-", "_").replace(".", "_")
            if field_name.startswith("_"):
                field_name = field_name[1:]

            inferred_type = infer_python_type(value)
            # All fields Optional (defensive)
            if inferred_type.startswith("Optional"):
                lines.append(f"    {field_name}: {inferred_type} = None")
            else:
                lines.append(f"    {field_name}: Optional[{inferred_type}] = None")

    return "\n".join(lines)


def merge_response_schemas(schemas: list[dict[str, Any]]) -> dict[str, str]:
    """
    Merge multiple response schemas into unified field types.

    When executing the same tool with different parameters, we may get
    slightly different response structures. This merges them conservatively.

    Args:
        schemas: List of response schemas to merge

    Returns:
        Dict mapping field name to merged type hint
    """
    if not schemas:
        return {}

    if len(schemas) == 1:
        return {key: infer_python_type(value) for key, value in schemas[0].items()}

    # Find all field names across all schemas
    all_fields: set[str] = set()
    for schema in schemas:
        if isinstance(schema, dict):
            all_fields.update(schema.keys())

    # Merge types conservatively (use Any if types differ)
    merged = {}
    for field in all_fields:
        field_types = set()
        for schema in schemas:
            if isinstance(schema, dict) and field in schema:
                field_types.add(infer_python_type(schema[field]))

        if len(field_types) == 1:
            # Consistent type
            merged[field] = field_types.pop()
        else:
            # Mixed types - use Any
            merged[field] = "Any"

    return merged
