#!/usr/bin/env python3
"""
Erotetic check for a specific skill's typed parameters.

USAGE:
    uv run python -m scripts.erotetic_skill_check --skill deploy-api --prompt "Deploy to AWS"
    uv run python -m scripts.erotetic_skill_check --skill deploy-api --prompt "Deploy to AWS" --base-path /project

Output (JSON):
    {
        "isEmpty": false,
        "unknowns": ["database"],
        "count": 1
    }

When isEmpty is false, the unknowns list contains parameters that need clarification.
When isEmpty is true, all typed parameters have been resolved.
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Ensure scripts module is importable when run directly
if __name__ == "__main__":
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from scripts.skill_loader import load_skill_schema
from scripts.skill_extractor import extract_skill_values
from scripts.z3_erotetic import check_evocation


# Fallback generic patterns (from erotetic-clarification.ts)
# Used when skill has no typed parameters
GENERIC_PATTERNS = {
    "framework": r"\b(fastapi|express|hono|gin|django|flask|rails|spring|nest\.?js)\b",
    "auth_method": r"\b(jwt|oauth|session|api[- ]?key|basic auth|bearer|saml|oidc)\b",
    "database": r"\b(postgres|postgresql|mysql|sqlite|mongodb|redis|dynamodb|firestore)\b",
    "hosting": r"\b(vercel|aws|gcp|azure|heroku|railway|fly\.io|cloudflare)\b",
    "language": r"\b(python|typescript|javascript|go|rust|java|ruby|php)\b",
    "testing": r"\b(pytest|jest|vitest|mocha|junit|rspec)\b",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Erotetic check for skill typed parameters"
    )
    parser.add_argument("--skill", required=True, help="Skill name")
    parser.add_argument("--prompt", required=True, help="User prompt")
    parser.add_argument(
        "--base-path",
        type=Path,
        default=None,
        help="Project base path (defaults to CLAUDE_PROJECT_DIR or cwd)",
    )
    parser.add_argument(
        "--use-generic-fallback",
        action="store_true",
        help="Use generic patterns if skill has no typed params",
    )
    args = parser.parse_args()

    schema = load_skill_schema(args.skill, base_path=args.base_path)

    if schema and schema.parameters:
        # Use skill-specific typed parameters
        propositions = extract_skill_values(args.prompt, schema)
    elif args.use_generic_fallback:
        # Fall back to generic patterns
        propositions = {}
        for prop_name, pattern in GENERIC_PATTERNS.items():
            match = re.search(pattern, args.prompt, re.IGNORECASE)
            propositions[prop_name] = match.group(0).lower() if match else "UNKNOWN"
    else:
        # No typed params and no fallback - return empty evocation
        propositions = {}

    result = check_evocation(propositions)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
