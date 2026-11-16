"""
Extract typed parameter values from prompts using skill schemas.

USAGE:
    from scripts.skill_extractor import extract_skill_values
    from scripts.skill_schema_parser import SkillSchema

    result = extract_skill_values(prompt, schema)
    # Returns: {"param1": "value1", "param2": "UNKNOWN"}
"""
import re
from scripts.skill_schema_parser import SkillSchema


UNKNOWN = "UNKNOWN"


def extract_skill_values(prompt: str, schema: SkillSchema) -> dict[str, str]:
    """
    Extract parameter values from prompt using schema patterns.

    Args:
        prompt: The user's prompt text
        schema: The skill schema with typed parameters

    Returns:
        Dict where:
        - Found values are the matched string (lowercased)
        - Missing values are "UNKNOWN" (unless they have defaults)
    """
    result: dict[str, str] = {}

    for param_name, param in schema.parameters.items():
        # Build pattern: use infer_from if present, else join values
        pattern = param.infer_from
        if not pattern and param.values:
            pattern = "|".join(re.escape(v) for v in param.values)

        if not pattern:
            # No pattern available - mark as unknown unless has default
            if param.default is not None:
                result[param_name] = param.default
            else:
                result[param_name] = UNKNOWN
            continue

        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            result[param_name] = match.group(0).lower()
        elif param.default is not None:
            result[param_name] = param.default
        else:
            result[param_name] = UNKNOWN

    return result
