"""Extract E(X,Q) directly from typed skill schemas.

Unlike prose extraction which requires LLM analysis, schema extraction is
deterministic - it parses typed parameter definitions directly.

USAGE:
    from scripts.skill_schema_extractor import extract_eqx_from_schema
    result = extract_eqx_from_schema(schema_dict)

    # Result:
    {
        "parameters": {
            "auth_method": {"type": "enum", "values": ["JWT", "OAuth"], ...}
        },
        "unknowns": {"api_key": "UNKNOWN"},
        "z3_checkable": ["auth_method", "verbose"]
    }

THEORY:
    E(X,Q) extraction from schema is straightforward:
    - Required params without defaults are UNKNOWN
    - Finite-domain types (enum, bool, bounded int) are Z3-checkable
    - String and unbounded int are NOT Z3-checkable (infinite domain)
"""
from typing import TypedDict, Any

# Sentinel for unknown values (matches z3_erotetic.py)
UNKNOWN = "UNKNOWN"


class SchemaExtractionResult(TypedDict):
    """Result of E(X,Q) extraction from schema."""
    parameters: dict[str, dict[str, Any]]  # param_name -> full spec
    unknowns: dict[str, str]               # param_name -> "UNKNOWN"
    z3_checkable: list[str]                # finite-domain params


def extract_eqx_from_schema(schema: dict[str, Any]) -> SchemaExtractionResult:
    """
    Extract E(X,Q) from schema definition.

    Directly parses typed parameter definitions without LLM.
    ~5ms performance (vs ~1500ms for LLM extraction).

    Args:
        schema: Schema dict with optional "parameters" key

    Returns:
        SchemaExtractionResult with parameters, unknowns, z3_checkable

    Example:
        >>> schema = {"parameters": {"x": {"type": "enum", "values": ["a", "b"]}}}
        >>> result = extract_eqx_from_schema(schema)
        >>> result["z3_checkable"]
        ['x']
    """
    parameters: dict[str, dict[str, Any]] = {}
    unknowns: dict[str, str] = {}
    z3_checkable: list[str] = []

    raw_params = schema.get("parameters", {})
    if not isinstance(raw_params, dict):
        raw_params = {}

    for name, spec in raw_params.items():
        if not isinstance(spec, dict):
            continue

        # Store full param spec
        parameters[name] = spec

        # Check if UNKNOWN: required without default
        is_required = spec.get("required", False)
        has_default = spec.get("default") is not None

        if is_required and not has_default:
            unknowns[name] = UNKNOWN

        # Check if Z3-checkable: finite domain
        param_type = spec.get("type", "string")

        if param_type == "enum":
            # Enum is always finite (set of values)
            z3_checkable.append(name)
        elif param_type == "bool":
            # Bool is finite (True/False)
            z3_checkable.append(name)
        elif param_type == "int":
            # Int is finite only if bounded
            has_min = spec.get("min") is not None
            has_max = spec.get("max") is not None
            if has_min and has_max:
                z3_checkable.append(name)
        # string, duration, etc. are infinite domain - not Z3-checkable

    return SchemaExtractionResult(
        parameters=parameters,
        unknowns=unknowns,
        z3_checkable=z3_checkable
    )
