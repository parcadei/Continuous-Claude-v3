"""Cross-Skill Pattern Registry (Phase 3 Tasks 3.7-3.9).

USAGE:
    from scripts.skill_pattern_registry import (
        PatternRegistry,
        register_shared_pattern,
        lookup_shared_pattern,
        lookup_patterns_by_domain,
        get_default_registry
    )

    # Get default registry with built-in patterns
    registry = get_default_registry()

    # Lookup a pattern
    pattern = lookup_shared_pattern(registry, "cloud_provider")

    # Lookup all patterns in a domain
    math_patterns = lookup_patterns_by_domain(registry, "math")

    # Register a new pattern
    register_shared_pattern(
        registry,
        name="my_pattern",
        pattern=r"regex here",
        domain="my_domain",
        description="What it matches"
    )

Shared patterns enable cross-skill reuse of common inference patterns.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PatternRegistry:
    """Registry of shared patterns across skills.

    Task 3.7: Central registry for cross-skill pattern reuse.
    """
    patterns: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(
        self,
        name: str,
        pattern: str,
        domain: str,
        description: str
    ) -> None:
        """Add a pattern to the registry."""
        self.patterns[name] = {
            "name": name,
            "pattern": pattern,
            "domain": domain,
            "description": description
        }

    def get(self, name: str) -> dict[str, Any] | None:
        """Get a pattern by name."""
        return self.patterns.get(name)

    def get_by_domain(self, domain: str) -> list[dict[str, Any]]:
        """Get all patterns in a domain."""
        return [
            p for p in self.patterns.values()
            if p["domain"] == domain
        ]


def register_shared_pattern(
    registry: PatternRegistry,
    name: str,
    pattern: str,
    domain: str,
    description: str
) -> None:
    """Register a pattern for cross-skill reuse.

    Task 3.7: Main registration function.

    Args:
        registry: PatternRegistry instance
        name: Unique pattern name
        pattern: Regex pattern string
        domain: Domain category (e.g., 'infrastructure', 'security', 'math')
        description: Human-readable description
    """
    registry.add(name, pattern, domain, description)


def lookup_shared_pattern(
    registry: PatternRegistry,
    name: str
) -> dict[str, Any] | None:
    """Lookup a shared pattern by name.

    Task 3.8: Pattern lookup function.

    Args:
        registry: PatternRegistry instance
        name: Pattern name to lookup

    Returns:
        Pattern dict or None if not found
    """
    return registry.get(name)


def lookup_patterns_by_domain(
    registry: PatternRegistry,
    domain: str
) -> list[dict[str, Any]]:
    """Lookup all patterns in a domain.

    Task 3.8b: Domain-based lookup.

    Args:
        registry: PatternRegistry instance
        domain: Domain to filter by

    Returns:
        List of patterns in the domain
    """
    return registry.get_by_domain(domain)


def _register_infrastructure_patterns(registry: PatternRegistry) -> None:
    """Register infrastructure-related patterns."""
    register_shared_pattern(
        registry,
        name="cloud_provider",
        pattern=r"\b(aws|gcp|azure|vercel|railway|heroku|digitalocean|netlify)\b",
        domain="infrastructure",
        description="Cloud hosting providers"
    )

    register_shared_pattern(
        registry,
        name="region",
        pattern=r"\b(us-east-[12]|us-west-[12]|eu-west-[123]|eu-central-1|ap-northeast-[12]|ap-southeast-[12])\b",
        domain="infrastructure",
        description="Cloud regions"
    )

    register_shared_pattern(
        registry,
        name="database",
        pattern=r"\b(postgresql?|mysql|mariadb|sqlite|mongodb|redis|dynamodb|firestore)\b",
        domain="infrastructure",
        description="Database systems"
    )


def _register_security_patterns(registry: PatternRegistry) -> None:
    """Register security-related patterns."""
    register_shared_pattern(
        registry,
        name="auth_method",
        pattern=r"\b(jwt|oauth|oauth2|session|api[- ]?key|bearer|saml|oidc|basic[- ]?auth)\b",
        domain="security",
        description="Authentication methods"
    )

    register_shared_pattern(
        registry,
        name="encryption",
        pattern=r"\b(aes|rsa|sha256|sha512|bcrypt|argon2|pbkdf2)\b",
        domain="security",
        description="Encryption algorithms"
    )


def _register_math_patterns(registry: PatternRegistry) -> None:
    """Register math-related patterns.

    Task 3.9: Math domain trial patterns.
    """
    register_shared_pattern(
        registry,
        name="proof_style",
        pattern=r"\b(induction|direct\s*proof|contradiction|contrapositive|constructive|cases|exhaustion)\b",
        domain="math",
        description="Mathematical proof styles"
    )

    register_shared_pattern(
        registry,
        name="axiom_system",
        pattern=r"\b(zfc|zf|peano|arithmetic|set\s*theory|first[- ]?order|second[- ]?order|hol|type\s*theory)\b",
        domain="math",
        description="Mathematical axiom systems"
    )

    register_shared_pattern(
        registry,
        name="math_structure",
        pattern=r"\b(group|ring|field|vector\s*space|algebra|topology|manifold|category)\b",
        domain="math",
        description="Mathematical structures"
    )

    register_shared_pattern(
        registry,
        name="proof_assistant",
        pattern=r"\b(lean|lean4?|coq|isabelle|agda|idris|hol|mizar)\b",
        domain="math",
        description="Proof assistants and theorem provers"
    )


def _register_dev_patterns(registry: PatternRegistry) -> None:
    """Register development-related patterns."""
    register_shared_pattern(
        registry,
        name="framework",
        pattern=r"\b(fastapi|express|hono|gin|django|flask|rails|spring|nest\.?js|next\.?js|nuxt)\b",
        domain="development",
        description="Web frameworks"
    )

    register_shared_pattern(
        registry,
        name="language",
        pattern=r"\b(python|typescript|javascript|rust|go|java|kotlin|swift|ruby|elixir)\b",
        domain="development",
        description="Programming languages"
    )

    register_shared_pattern(
        registry,
        name="test_framework",
        pattern=r"\b(pytest|jest|mocha|vitest|junit|rspec|gotest|cargo[- ]?test)\b",
        domain="development",
        description="Testing frameworks"
    )


# Singleton default registry
_default_registry: PatternRegistry | None = None


def get_default_registry() -> PatternRegistry:
    """Get the default pattern registry with built-in patterns.

    Task 3.9: Returns registry with math domain patterns included.

    Returns:
        PatternRegistry with all default patterns
    """
    global _default_registry

    if _default_registry is None:
        _default_registry = PatternRegistry()
        _register_infrastructure_patterns(_default_registry)
        _register_security_patterns(_default_registry)
        _register_math_patterns(_default_registry)
        _register_dev_patterns(_default_registry)

    return _default_registry


def reset_default_registry() -> None:
    """Reset the default registry (for testing)."""
    global _default_registry
    _default_registry = None
