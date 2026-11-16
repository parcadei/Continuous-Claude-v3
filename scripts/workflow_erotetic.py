#!/usr/bin/env python3
"""
Workflow Erotetic Gate - Proposition Extraction and Gate Evaluation (Python side)

This module provides:
1. extract_propositions() - Extract framework, auth_method, database etc from input
2. generate_clarification_questions() - Generate Q-value ordered questions
3. format_gate_status() - Format as E:X R:O C:->
4. evaluate_erotetic_gate() - Return continue/block decision
5. generate_block_feedback() - Don Norman error messages
6. call_z3_erotetic() - Integration with z3_erotetic for formal verification

USAGE:
    from scripts.workflow_erotetic import extract_propositions, evaluate_erotetic_gate

    props = extract_propositions("Build a FastAPI backend with JWT")
    result = evaluate_erotetic_gate("Build an API backend")
    if result["decision"] == "block":
        print(f"Missing: {result['unknowns']}")
"""

import re
import json
import subprocess
from typing import Optional
from pathlib import Path

# ============================================================
# Constants
# ============================================================

# Pattern to detect implementation tasks
IMPL_PATTERNS = re.compile(r'\b(build|implement|create|add|develop|design|set up|write)\b', re.IGNORECASE)
NON_IMPL_PATTERNS = re.compile(r'\b(fix|run|show|explain|list|search|rename|delete|update)\b', re.IGNORECASE)

# Domain-specific proposition extractors
PROPOSITION_PATTERNS: dict[str, re.Pattern] = {
    'framework': re.compile(r'\b(fastapi|express|hono|gin|django|flask|rails|spring|nest\.?js)\b', re.IGNORECASE),
    'auth_method': re.compile(r'\b(jwt|oauth\d?|session|api[- ]?key|basic auth|bearer|saml|oidc)\b', re.IGNORECASE),
    'database': re.compile(r'\b(postgres(?:ql)?|mysql|sqlite|mongodb|redis|dynamodb|firestore)\b', re.IGNORECASE),
    'hosting': re.compile(r'\b(vercel|aws|gcp|azure|heroku|railway|fly\.io|cloudflare)\b', re.IGNORECASE),
    'language': re.compile(r'\b(python|typescript|javascript|go|rust|java|ruby|php)\b', re.IGNORECASE),
    'testing': re.compile(r'\b(pytest|jest|vitest|mocha|junit|rspec)\b', re.IGNORECASE),
}

# Critical propositions - gate blocks if these are missing
CRITICAL_PROPOSITIONS = ['framework', 'auth_method', 'database']

# Q-value ordering (higher = more architectural impact, asked first)
Q_VALUE_ORDER: dict[str, int] = {
    'framework': 100,
    'database': 90,
    'auth_method': 80,
    'hosting': 60,
    'language': 50,
    'testing': 30,
}

# Default options for common propositions
PROPOSITION_OPTIONS: dict[str, list[str]] = {
    'framework': ['FastAPI', 'Express', 'Django', 'Flask', 'NestJS', 'Rails', 'Spring', 'Hono'],
    'auth_method': ['JWT', 'OAuth', 'Session', 'API Key', 'SAML', 'OIDC'],
    'database': ['PostgreSQL', 'MySQL', 'SQLite', 'MongoDB', 'Redis', 'DynamoDB'],
    'hosting': ['AWS', 'GCP', 'Azure', 'Vercel', 'Heroku', 'Railway', 'Fly.io'],
    'language': ['Python', 'TypeScript', 'JavaScript', 'Go', 'Rust', 'Java', 'Ruby'],
    'testing': ['pytest', 'Jest', 'Vitest', 'Mocha', 'JUnit', 'RSpec'],
}

# Why explanations for propositions
PROPOSITION_WHY: dict[str, str] = {
    'framework': 'The framework choice impacts architecture, dependencies, and development patterns.',
    'auth_method': 'Authentication choice affects security architecture and integration complexity.',
    'database': 'Database selection impacts data modeling, scalability, and query patterns.',
    'hosting': 'Hosting platform choice affects deployment, scaling, and operational complexity.',
    'language': 'Language choice depends on team expertise, ecosystem, and performance needs.',
    'testing': 'Testing framework choice affects test structure and CI/CD integration.',
}


# ============================================================
# Utility Functions
# ============================================================

def _find_first_match(prompt: str, pattern: re.Pattern) -> int:
    """Find the position of the first match, or -1 if not found."""
    match = pattern.search(prompt)
    return match.start() if match else -1


def _is_implementation_task(prompt: str) -> bool:
    """Check if the prompt is an implementation task."""
    if not prompt or not prompt.strip():
        return False

    impl_pos = _find_first_match(prompt, IMPL_PATTERNS)
    non_impl_pos = _find_first_match(prompt, NON_IMPL_PATTERNS)

    if impl_pos == -1:
        return False
    if non_impl_pos == -1:
        return True
    return impl_pos < non_impl_pos


def _to_title_case(s: str) -> str:
    """Convert snake_case to Title Case."""
    return ' '.join(word.capitalize() for word in s.split('_'))


def _normalize_value(value: str, prop_name: str) -> str:
    """Normalize extracted values to standard form."""
    value = value.lower()
    # Handle special cases
    if value == 'nest.js':
        value = 'nestjs'
    if value == 'postgres':
        value = 'postgresql'
    if value.startswith('oauth'):
        value = 'oauth'
    return value


# ============================================================
# Main Functions
# ============================================================

def extract_propositions(prompt: str) -> dict[str, str]:
    """
    Extract propositions from a prompt using pattern matching.

    Args:
        prompt: User input text

    Returns:
        Dict where found values are lowercase strings, missing values are "UNKNOWN".
    """
    propositions: dict[str, str] = {}

    # Handle empty or whitespace-only input
    if not prompt or not prompt.strip():
        for prop_name in PROPOSITION_PATTERNS:
            propositions[prop_name] = 'UNKNOWN'
        return propositions

    for prop_name, pattern in PROPOSITION_PATTERNS.items():
        match = pattern.search(prompt)
        if match:
            propositions[prop_name] = _normalize_value(match.group(0), prop_name)
        else:
            propositions[prop_name] = 'UNKNOWN'

    return propositions


def generate_clarification_questions(unknowns: list[str]) -> list[dict]:
    """
    Generate clarification questions for a list of unknown propositions.
    Questions are ordered by Q-value (architectural impact).

    Args:
        unknowns: List of unknown proposition names

    Returns:
        List of question dicts with header, proposition, options, why fields.
    """
    if not unknowns:
        return []

    # Sort by Q-value (higher = more important = asked first)
    sorted_unknowns = sorted(
        unknowns,
        key=lambda p: Q_VALUE_ORDER.get(p, 10),
        reverse=True
    )

    questions = []
    for proposition in sorted_unknowns:
        questions.append({
            'header': _to_title_case(proposition),
            'proposition': proposition,
            'options': PROPOSITION_OPTIONS.get(proposition, ['Other (specify)']),
            'why': PROPOSITION_WHY.get(
                proposition,
                f'The {proposition} choice impacts the overall architecture and implementation.'
            ),
        })

    return questions


def format_gate_status(
    erotetic: str = 'pending',
    resources: str = 'pending',
    composition: str = 'pending'
) -> str:
    """
    Format gate status for display (StatusLine format).

    Args:
        erotetic: 'pass', 'block', or 'pending'
        resources: 'pass', 'block', or 'pending'
        composition: 'pass', 'block', or 'pending'

    Returns:
        Status string like "E:X R:O C:->"
    """
    status_chars = {
        'pass': '\u2713',    # checkmark
        'block': '\u2717',   # X mark
        'pending': '\u25CB', # circle
    }

    e_char = status_chars.get(erotetic, '\u25CB')
    r_char = status_chars.get(resources, '\u25CB')
    c_char = status_chars.get(composition, '\u25CB')

    return f'E:{e_char} R:{r_char} C:{c_char}'


def evaluate_erotetic_gate(prompt: str) -> dict:
    """
    Evaluate the erotetic gate for a prompt.

    Args:
        prompt: User input text

    Returns:
        Dict with decision ('continue'/'block'), unknowns list, and optional feedback.
    """
    # Non-implementation tasks always pass
    if not _is_implementation_task(prompt):
        return {
            'decision': 'continue',
            'unknowns': [],
        }

    # Extract propositions
    propositions = extract_propositions(prompt)

    # Find unknown critical propositions
    unknowns = [
        prop for prop in CRITICAL_PROPOSITIONS
        if propositions.get(prop) == 'UNKNOWN'
    ]

    if not unknowns:
        return {
            'decision': 'continue',
            'unknowns': [],
        }

    # Gate blocks - generate feedback
    feedback = generate_block_feedback('Erotetic', unknowns)

    return {
        'decision': 'block',
        'unknowns': unknowns,
        'feedback': feedback,
    }


def generate_block_feedback(
    gate: str,
    unknowns: list[str],
    suggestions: Optional[list[str]] = None
) -> dict:
    """
    Generate structured feedback for a blocked gate (Don Norman principles).

    Args:
        gate: Gate name ('Erotetic', 'Resources', 'Composition')
        unknowns: List of unknown proposition names
        suggestions: Optional list of suggestions

    Returns:
        Feedback dict with gate, status, title, details, suggestion fields.
    """
    unknowns_list = ', '.join(unknowns) if unknowns else 'general requirements'

    return {
        'gate': gate,
        'status': 'block',
        'title': f'Missing {len(unknowns)} critical proposition(s) to resolve',
        'details': f'The following must be clarified before proceeding: {unknowns_list}',
        'suggestion': (suggestions[0] if suggestions else
            'Please specify the missing values using AskUserQuestion or select from options.'),
    }


def call_z3_erotetic(propositions: dict[str, str]) -> dict:
    """
    Call z3_erotetic to compute E(X,Q) for formal verification.

    Args:
        propositions: Dict of proposition name -> value (or "UNKNOWN")

    Returns:
        Dict with isEmpty (bool), unknowns (list), count (int).
    """
    # Import directly if available (preferred for testing)
    try:
        from scripts.z3_erotetic import check_evocation
        return check_evocation(propositions)
    except ImportError:
        pass

    # Fallback to CLI
    try:
        project_dir = Path(__file__).parent.parent
        result = subprocess.run(
            ['uv', 'run', 'python', 'scripts/z3_erotetic_cli.py',
             '--props', json.dumps(propositions)],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            return json.loads(result.stdout.strip())
    except Exception:
        pass

    # Fallback: compute locally
    unknowns = [k for k, v in propositions.items() if v == 'UNKNOWN' or v is None]
    return {
        'isEmpty': len(unknowns) == 0,
        'unknowns': unknowns,
        'count': len(unknowns),
    }


# ============================================================
# CLI entry point
# ============================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Workflow Erotetic Gate CLI')
    parser.add_argument('--prompt', help='User prompt to evaluate')
    parser.add_argument('--extract', action='store_true', help='Extract propositions only')
    parser.add_argument('--evaluate', action='store_true', help='Evaluate gate decision')
    args = parser.parse_args()

    if args.prompt:
        if args.extract:
            result = extract_propositions(args.prompt)
        elif args.evaluate:
            result = evaluate_erotetic_gate(args.prompt)
        else:
            result = evaluate_erotetic_gate(args.prompt)
        print(json.dumps(result, indent=2))
