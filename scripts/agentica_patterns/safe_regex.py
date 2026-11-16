"""
Safe regex utilities to prevent ReDoS (Regular Expression Denial of Service) attacks.

This module provides:
1. is_safe_regex() - Static analysis to detect dangerous patterns
2. safe_regex_match() - Timeout-protected regex execution
3. regex_complexity() - Complexity scoring for patterns

Key dangerous patterns detected:
- Nested quantifiers: (a+)+, (.*)+, (.+)+ - O(2^n) exponential
- Overlapping alternation: (a|aa)+, (a|a?)+ - O(n^k) polynomial
- Multiple adjacent quantifiers: a+a+, .*.* - O(n^k) polynomial
"""

import re
import threading

# Detection patterns for dangerous regex constructs
DANGEROUS_PATTERNS = [
    # Nested quantifiers - exponential backtracking: (a+)+, (a*)+, (.*)+, etc.
    re.compile(r"\([^)]*[+*][^)]*\)[+*?]"),
    # Multiple greedy dots: .*.*
    re.compile(r"\.\*\.\*"),
    # Multiple greedy plus dots: .+.+
    re.compile(r"\.\+\.\+"),
    # Multiple large ranges: {n,m}...{n,m}
    re.compile(r"\{[0-9]+,[0-9]+\}.*\{[0-9]+,[0-9]+\}"),
]

# Pattern to detect overlapping alternation: (a|aa)+, (a|a?)+
# This catches cases where one alternative is a prefix/suffix of another
OVERLAPPING_ALT_PATTERN = re.compile(r"\(([^|)]+)\|(\1|\1.|\.\1|\1\?|\?\1)[^)]*\)[+*]")

# Pattern to detect multiple adjacent quantifiers on same-ish patterns: a+a+, .*.*
# This creates polynomial complexity
POLYNOMIAL_PATTERN = re.compile(r"([+*])[^+*\[\(]{0,3}([+*])")

# Pattern for nested group with quantifier followed by outer quantifier
NESTED_QUANTIFIER_STRICT = re.compile(r"\([^()]*[+*?](\{[0-9,]+\})?[^()]*\)[+*?]")


def is_safe_regex(pattern: str) -> bool:
    """
    Check if a regex pattern is safe from ReDoS attacks.

    Uses static analysis to detect patterns known to cause:
    - Exponential backtracking (nested quantifiers)
    - Polynomial backtracking (overlapping alternation, multiple quantifiers)

    Args:
        pattern: The regex pattern string to analyze

    Returns:
        True if the pattern appears safe, False if it could cause ReDoS

    Examples:
        >>> is_safe_regex("(a+)+")  # Nested quantifier - dangerous
        False
        >>> is_safe_regex("^[a-z]+$")  # Simple pattern - safe
        True
    """
    # None input is not safe (invalid input)
    if pattern is None:
        return False

    # Empty pattern is safe (matches nothing or empty string)
    if not pattern:
        return True

    # Check for syntactically invalid pattern first
    try:
        re.compile(pattern)
    except re.error:
        # Invalid patterns can't be executed, so they're "safe" in that sense
        # But we return True here because we're checking safety, not validity
        return True

    # Check each dangerous pattern
    for dangerous in DANGEROUS_PATTERNS:
        if dangerous.search(pattern):
            return False

    # Check for nested quantifiers with strict pattern
    if NESTED_QUANTIFIER_STRICT.search(pattern):
        return False

    # Check for polynomial patterns: multiple quantifiers in sequence
    # Count quantifiers (+, *, {n,m})
    quantifier_positions = []
    i = 0
    in_class = False
    escaped = False

    while i < len(pattern):
        char = pattern[i]

        if escaped:
            escaped = False
            i += 1
            continue

        if char == "\\":
            escaped = True
            i += 1
            continue

        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif not in_class and char in "+*":
            quantifier_positions.append(i)
        elif not in_class and char == "{":
            # Look for {n,m} pattern
            j = i + 1
            while j < len(pattern) and pattern[j] in "0123456789,":
                j += 1
            if j < len(pattern) and pattern[j] == "}":
                quantifier_positions.append(i)

        i += 1

    # If we have 3+ quantifiers on similar patterns, it's likely polynomial
    if len(quantifier_positions) >= 3:
        # Check if they're operating on similar patterns (e.g., a+a+a+)
        # Look for patterns like X+X+X+ where X is similar
        match_count = 0
        for pos in quantifier_positions:
            if pos > 0:
                # Check what's being quantified
                before = pattern[max(0, pos - 5) : pos]
                if "." in before or re.search(r"[a-z]", before):
                    match_count += 1
        if match_count >= 3:
            return False

    # Check for overlapping alternation
    if OVERLAPPING_ALT_PATTERN.search(pattern):
        return False

    # Specific check for (a|aa)+ style patterns
    alt_groups = re.findall(r"\(([^)]+)\)[+*]", pattern)
    for group in alt_groups:
        if "|" in group:
            alternatives = group.split("|")
            for i, alt1 in enumerate(alternatives):
                for alt2 in alternatives[i + 1 :]:
                    # Check if one is prefix/suffix of other
                    if alt1 and alt2:
                        if alt1.startswith(alt2) or alt2.startswith(alt1):
                            return False
                        if alt1 == alt2:  # Identical alternatives
                            return False

    return True


def safe_regex_match(
    pattern: str,
    text: str,
    timeout_ms: int = 100,
    case_insensitive: bool = False,
) -> bool | None:
    """
    Safely execute a regex match with timeout protection.

    First checks if the pattern is safe using static analysis.
    If unsafe or invalid, returns None immediately.
    If safe, executes with a timeout to catch edge cases.

    Args:
        pattern: The regex pattern to match
        text: The text to search
        timeout_ms: Maximum execution time in milliseconds (default 100)
        case_insensitive: Whether to use case-insensitive matching

    Returns:
        True: Pattern matched the text
        False: Pattern did not match the text
        None: Pattern is unsafe, invalid, or execution timed out

    Examples:
        >>> safe_regex_match("jwt", "use JWT auth", case_insensitive=True)
        True
        >>> safe_regex_match("(a+)+b", "a" * 30)  # Evil pattern
        None
    """
    # Handle None inputs gracefully
    if pattern is None or text is None:
        return None

    # Check if pattern is safe first
    if not is_safe_regex(pattern):
        return None

    # Try to compile the pattern
    try:
        flags = re.IGNORECASE if case_insensitive else 0
        compiled = re.compile(pattern, flags)
    except re.error:
        return None

    # Execute with timeout protection
    result: list[bool | None] = [None]  # Use list to allow modification in nested function
    exception: list[Exception | None] = [None]

    def do_match() -> None:
        try:
            match = compiled.search(text)
            result[0] = match is not None
        except Exception as e:
            exception[0] = e

    # Run in a thread with timeout
    thread = threading.Thread(target=do_match)
    thread.daemon = True
    thread.start()
    thread.join(timeout=timeout_ms / 1000.0)

    if thread.is_alive():
        # Timed out - pattern took too long
        return None

    if exception[0] is not None:
        return None

    return result[0] if result[0] is not None else None


def regex_complexity(pattern: str) -> int:
    """
    Calculate a complexity score for a regex pattern.

    Higher scores indicate more dangerous patterns:
    - 0-4: Constant time (literal strings)
    - 5-9: Linear time (single quantifier, no nesting)
    - 10-49: Superlinear but likely OK with reasonable input
    - 50-99: Polynomial - potentially dangerous
    - 100+: Exponential - definitely dangerous

    Args:
        pattern: The regex pattern to analyze

    Returns:
        Integer complexity score (0-200+)

    Examples:
        >>> regex_complexity("exact")  # Literal
        0
        >>> regex_complexity("^[a-z]+$")  # Simple quantifier
        5
        >>> regex_complexity("(a+)+")  # Nested quantifier - exponential
        150
    """
    if not pattern:
        return 0

    score = 0

    # Check for invalid pattern
    try:
        re.compile(pattern)
    except re.error:
        return 0  # Invalid patterns don't execute

    # Count basic quantifiers
    quantifiers = len(re.findall(r"[+*?]", pattern))
    score += quantifiers * 2

    # Count bounded quantifiers {n,m}
    bounded = re.findall(r"\{(\d+),(\d+)\}", pattern)
    for lower, upper in bounded:
        range_size = int(upper) - int(lower)
        score += min(range_size // 10, 5)  # Cap contribution

    # Count alternation groups
    alternations = len(re.findall(r"\|", pattern))
    score += alternations

    # Count nested groups (groups inside groups)
    depth = 0
    max_depth = 0
    for char in pattern:
        if char == "(":
            depth += 1
            max_depth = max(max_depth, depth)
        elif char == ")":
            depth -= 1
    score += max_depth * 3

    # Heavy penalties for dangerous patterns

    # Nested quantifiers: (x+)+ = exponential
    if NESTED_QUANTIFIER_STRICT.search(pattern):
        score += 100

    # Multiple greedy patterns: .*.* = polynomial
    if re.search(r"\.\*.*\.\*", pattern):
        score += 50

    if re.search(r"\.\+.*\.\+", pattern):
        score += 50

    # Overlapping alternation in quantified group
    if OVERLAPPING_ALT_PATTERN.search(pattern):
        score += 75

    # Multiple adjacent quantifiers on similar patterns
    adj_quants = len(re.findall(r"[+*]\S{0,3}[+*]", pattern))
    score += adj_quants * 20

    # Check for polynomial patterns like a+a+a+
    repeated_quant = re.findall(r"([a-zA-Z0-9])\+\1\+", pattern)
    score += len(repeated_quant) * 30

    return score
