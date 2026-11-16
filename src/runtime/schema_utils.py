"""
JSON Schema to Pydantic model conversion utilities.

Converts MCP tool schemas (JSON Schema format) to Pydantic model definitions.
"""

from typing import Any


def json_schema_to_python_type(schema: dict[str, Any], required: bool = True) -> str:
    """
    Convert JSON Schema type to Python type hint string.

    Args:
        schema: JSON Schema definition
        required: Whether field is required

    Returns:
        Python type hint string (e.g., "str", "Optional[int]", "List[str]")

    Examples:
        >>> json_schema_to_python_type({"type": "string"}, True)
        'str'
        >>> json_schema_to_python_type({"type": "string"}, False)
        'Optional[str]'
        >>> json_schema_to_python_type({"type": "array", "items": {"type": "string"}})
        'List[str]'
    """
    # Handle union types: ["string", "null"]
    if isinstance(schema.get("type"), list):
        types = schema["type"]
        if "null" in types:
            required = False
            types = [t for t in types if t != "null"]
            if len(types) == 1:
                schema = {"type": types[0]}

    # Handle enum
    if "enum" in schema:
        enum_values = schema["enum"]
        # Use Literal type
        literal_values = ", ".join([f'"{v}"' for v in enum_values])
        base_type = f"Literal[{literal_values}]"
        return f"Optional[{base_type}]" if not required else base_type

    # Get base type
    schema_type = schema.get("type", "object")

    type_mapping = {
        "string": "str",
        "number": "float",
        "integer": "int",
        "boolean": "bool",
        "null": "None",
    }

    if schema_type in type_mapping:
        base_type = type_mapping[schema_type]
        return f"Optional[{base_type}]" if not required else base_type

    elif schema_type == "array":
        items_schema = schema.get("items", {"type": "object"})
        item_type = json_schema_to_python_type(items_schema, required=True)
        base_type = f"List[{item_type}]"
        return f"Optional[{base_type}]" if not required else base_type

    elif schema_type == "object":
        # Check for additionalProperties (Dict type)
        if "additionalProperties" in schema:
            value_schema = schema["additionalProperties"]
            if isinstance(value_schema, bool):
                value_type = "Any"
            else:
                value_type = json_schema_to_python_type(value_schema, required=True)
            base_type = f"Dict[str, {value_type}]"
            return f"Optional[{base_type}]" if not required else base_type

        # Otherwise, nested Pydantic model (will be generated separately)
        return "Dict[str, Any]" if required else "Optional[Dict[str, Any]]"

    # Fallback
    return "Any" if required else "Optional[Any]"


def generate_pydantic_model(
    model_name: str,
    schema: dict[str, Any],
    description: str | None = None,
) -> str:
    """
    Generate Pydantic model class from JSON Schema.

    Args:
        model_name: Name of the Pydantic model class
        schema: JSON Schema definition
        description: Optional model description

    Returns:
        Python code for Pydantic model

    Example:
        >>> schema = {
        ...     "type": "object",
        ...     "properties": {
        ...         "name": {"type": "string"},
        ...         "age": {"type": "integer"}
        ...     },
        ...     "required": ["name"]
        ... }
        >>> print(generate_pydantic_model("Person", schema))
        class Person(BaseModel):
            '''Generated model'''
            name: str
            age: Optional[int] = None
    """
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    lines = [f"class {model_name}(BaseModel):"]

    # Add docstring
    if description:
        lines.append(f'    """{description}"""')
    else:
        lines.append('    """Generated Pydantic model."""')

    # Generate fields
    if not properties:
        lines.append("    pass")
    else:
        for field_name, field_schema in properties.items():
            is_required = field_name in required_fields
            field_type = json_schema_to_python_type(field_schema, is_required)
            field_desc = field_schema.get("description", "")

            if is_required:
                lines.append(f"    {field_name}: {field_type}")
            else:
                lines.append(f"    {field_name}: {field_type} = None")

            if field_desc:
                lines.append(f'    """{field_desc}"""')

    return "\n".join(lines)


def sanitize_name(name: str) -> str:
    """
    Sanitize name for Python identifier.

    Args:
        name: Original name

    Returns:
        Valid Python identifier

    Examples:
        >>> sanitize_name("my-tool")
        'my_tool'
        >>> sanitize_name("list")
        'list_'
    """
    # Replace hyphens with underscores
    name = name.replace("-", "_").replace(".", "_")

    # Handle Python keywords
    python_keywords = {"list", "dict", "set", "type", "class", "def", "import"}
    if name in python_keywords:
        name = name + "_"

    return name
