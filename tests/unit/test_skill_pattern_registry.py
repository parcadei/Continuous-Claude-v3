"""Tests for Cross-Skill Pattern Registry (Phase 3 Tasks 3.7-3.9).

TDD tests for shared pattern registry across skills.
"""

import pytest
from pathlib import Path


# Task 3.7: Test pattern registry skeleton
class TestPatternRegistry:
    """Task 3.7: Cross-skill pattern registry."""

    def test_register_shared_pattern(self):
        """Register a pattern for cross-skill reuse."""
        from scripts.skill_pattern_registry import (
            PatternRegistry,
            register_shared_pattern
        )

        registry = PatternRegistry()
        register_shared_pattern(
            registry,
            name="cloud_provider",
            pattern=r"\b(aws|gcp|azure|vercel|railway)\b",
            domain="infrastructure",
            description="Common cloud provider names"
        )

        assert "cloud_provider" in registry.patterns
        assert registry.patterns["cloud_provider"]["domain"] == "infrastructure"


# Task 3.8: Test pattern lookup
class TestPatternLookup:
    """Task 3.8: Pattern lookup function."""

    def test_lookup_shared_pattern(self):
        """Lookup shared pattern by name."""
        from scripts.skill_pattern_registry import (
            PatternRegistry,
            register_shared_pattern,
            lookup_shared_pattern
        )

        registry = PatternRegistry()
        register_shared_pattern(
            registry,
            name="auth_method",
            pattern=r"\b(jwt|oauth|session|api[- ]?key)\b",
            domain="security",
            description="Authentication methods"
        )

        result = lookup_shared_pattern(registry, "auth_method")

        assert result is not None
        assert result["pattern"] == r"\b(jwt|oauth|session|api[- ]?key)\b"

    def test_lookup_nonexistent_pattern(self):
        """Lookup returns None for nonexistent pattern."""
        from scripts.skill_pattern_registry import (
            PatternRegistry,
            lookup_shared_pattern
        )

        registry = PatternRegistry()

        result = lookup_shared_pattern(registry, "nonexistent")

        assert result is None

    def test_lookup_by_domain(self):
        """Lookup patterns by domain."""
        from scripts.skill_pattern_registry import (
            PatternRegistry,
            register_shared_pattern,
            lookup_patterns_by_domain
        )

        registry = PatternRegistry()
        register_shared_pattern(registry, "cloud_provider",
                               r"aws|gcp|azure", "infrastructure", "Cloud")
        register_shared_pattern(registry, "region",
                               r"us-east|eu-west", "infrastructure", "Regions")
        register_shared_pattern(registry, "jwt",
                               r"jwt|bearer", "security", "JWT tokens")

        infra_patterns = lookup_patterns_by_domain(registry, "infrastructure")

        assert len(infra_patterns) == 2
        assert "cloud_provider" in [p["name"] for p in infra_patterns]
        assert "region" in [p["name"] for p in infra_patterns]


# Task 3.9: Test math domain patterns
class TestMathDomainPatterns:
    """Task 3.9: Math-specific patterns."""

    def test_math_domain_patterns(self):
        """Math domain has proof_style and axiom_system patterns."""
        from scripts.skill_pattern_registry import (
            get_default_registry,
            lookup_patterns_by_domain
        )

        registry = get_default_registry()
        math_patterns = lookup_patterns_by_domain(registry, "math")

        pattern_names = [p["name"] for p in math_patterns]

        # Required patterns from plan
        assert "proof_style" in pattern_names
        assert "axiom_system" in pattern_names

    def test_proof_style_pattern_matches(self):
        """proof_style pattern matches common proof styles."""
        from scripts.skill_pattern_registry import get_default_registry
        import re

        registry = get_default_registry()
        pattern = registry.patterns["proof_style"]["pattern"]

        regex = re.compile(pattern, re.IGNORECASE)

        # Should match common proof styles
        assert regex.search("prove by induction")
        assert regex.search("direct proof")
        assert regex.search("proof by contradiction")
        assert regex.search("constructive proof")

    def test_axiom_system_pattern_matches(self):
        """axiom_system pattern matches common axiom systems."""
        from scripts.skill_pattern_registry import get_default_registry
        import re

        registry = get_default_registry()
        pattern = registry.patterns["axiom_system"]["pattern"]

        regex = re.compile(pattern, re.IGNORECASE)

        # Should match common axiom systems
        assert regex.search("use ZFC axioms")
        assert regex.search("in Peano arithmetic")
        assert regex.search("ZF set theory")
