"""
Z3 Erotetic Checker - E(X,Q) Formal Verification Foundation.

This module provides a foundation for erotetic (question-based) reasoning
using constraint solving to determine which propositions are UNKNOWN
(not entailed by the context).

USAGE:
    from scripts.z3_erotetic import check_evocation, UNKNOWN

    result = check_evocation({
        "auth_method": True,        # Known true
        "session_duration": False,  # Known false
        "rate_limit": "JWT",        # Known value (string)
        "error_format": "UNKNOWN",  # Unknown - not entailed
        "validation": None,         # Unknown - not entailed (None variant)
    })

    # Result:
    {
        "isEmpty": False,           # True if no unknowns
        "unknowns": ["error_format", "validation"],  # List of unknown prop names
        "count": 2                  # Number of unknowns
    }

Theory:
    E(X,Q) represents propositions that cannot be entailed (True/False)
    from the context X via question-heuristic Q. When E(X,Q) = {} (empty),
    all propositions are determined and implementation can proceed.

Note:
    - "UNKNOWN" (uppercase string) = unknown proposition
    - None = unknown proposition
    - False, 0, empty string, empty list, empty dict = KNOWN (don't confuse falsy with unknown)
    - Lists and dicts = known (complex values are considered resolved)
    - "unknown" (lowercase) = known string value (not the sentinel)
"""

from typing import Any

# Exported constant for marking unknown propositions
UNKNOWN = "UNKNOWN"


def check_evocation(propositions: dict[str, Any]) -> dict[str, Any]:
    """
    Check which propositions are UNKNOWN (not entailed by context).

    Args:
        propositions: Dict where values are:
            - TRUE/FALSE/string = known (entailed)
            - "UNKNOWN" string or None = unknown (not entailed)
            - Lists/dicts = known (complex values are considered resolved)

    Returns:
        {
            "isEmpty": bool,      # True if no unknowns
            "unknowns": list,     # List of unknown proposition names (strings, no dupes)
            "count": int          # Number of unknowns (== len(unknowns))
        }
    """
    unknowns: list[str] = []

    for key, value in propositions.items():
        if _is_unknown(value):
            # Convert key to string (handles non-string keys like integers)
            unknowns.append(str(key))

    # Remove duplicates while preserving order (though dict keys are unique,
    # this ensures the contract is explicit)
    unknowns = list(dict.fromkeys(unknowns))

    count = len(unknowns)

    return {
        "isEmpty": count == 0,
        "unknowns": unknowns,
        "count": count,
    }


def _is_unknown(value: Any) -> bool:
    """
    Determine if a value represents an unknown proposition.

    Unknown values:
        - None
        - "UNKNOWN" (case-sensitive, uppercase only)

    Known values (everything else):
        - True, False (booleans)
        - 0, 42, -1, 3.14 (numbers)
        - "", "value", "unknown" (strings other than "UNKNOWN")
        - [], [1, 2, 3] (lists)
        - {}, {"key": "value"} (dicts)

    Note: We explicitly check for None and "UNKNOWN" string.
    All other values are considered known.
    """
    if value is None:
        return True
    if value == UNKNOWN and isinstance(value, str):
        return True
    return False
