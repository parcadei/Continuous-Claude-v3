"""
Erotetic Q-Value Ranking

Ranks erotetic propositions (unknowns) by Q-value based on architectural impact.
Integrates with z3_erotetic.py to provide ordered clarification priorities.

Usage:
    from scripts.erotetic_q_ranking import rank_by_q, rank_z3_unknowns

References:
    - thoughts/shared/agents/decision-theory-research/2-erotetic-integration.md
    - scripts/z3_erotetic.py
"""

from dataclasses import dataclass
from typing import Literal, Optional


QValue = Literal["HIGH", "MED", "LOW"]


@dataclass
class QConfig:
    """Configuration for a proposition's Q-value."""
    q_value: QValue
    why: str


@dataclass
class QRankedProposition:
    """A proposition ranked by Q-value with explanation."""
    proposition: str
    q_value: QValue
    why: str


# Q-value configurations per known proposition type
# Based on architectural impact analysis from Agent 2's research
Q_CONFIGS: dict[str, QConfig] = {
    # HIGH impact - partitions entire solution space
    "framework": QConfig(
        q_value="HIGH",
        why="Framework choice partitions entire solution architecture"
    ),
    "auth_method": QConfig(
        q_value="HIGH",
        why="Auth method determines middleware stack, token storage, session handling"
    ),
    "database": QConfig(
        q_value="HIGH",
        why="Database choice affects data model, queries, migrations"
    ),
    "language": QConfig(
        q_value="HIGH",
        why="Language choice determines runtime, dependencies, tooling"
    ),

    # MEDIUM impact - significant but changeable
    "hosting": QConfig(
        q_value="MED",
        why="Hosting platform affects deployment but can be changed"
    ),
    "testing": QConfig(
        q_value="MED",
        why="Testing strategy affects quality but not core architecture"
    ),
    "styling": QConfig(
        q_value="MED",
        why="Styling approach affects UI but is mostly orthogonal"
    ),
    "state_management": QConfig(
        q_value="MED",
        why="State management affects frontend architecture"
    ),
}

# Default for unrecognized propositions
DEFAULT_Q_CONFIG = QConfig(
    q_value="MED",
    why="Unrecognized proposition - using default MED priority"
)


def q_ord(q: QValue) -> float:
    """Convert Q-value to numeric for sorting. HIGH > MED > LOW."""
    return {"HIGH": 1.0, "MED": 0.5, "LOW": 0.1}.get(q, 0.5)


def get_q_config(proposition: str) -> QConfig:
    """Get Q-value configuration for a proposition.

    Args:
        proposition: The proposition name (e.g., 'framework', 'auth_method')

    Returns:
        QConfig with q_value and why explanation
    """
    return Q_CONFIGS.get(proposition.lower(), DEFAULT_Q_CONFIG)


def rank_by_q(unknowns: list[str]) -> list[QRankedProposition]:
    """Rank unknown propositions by Q-value (architectural impact).

    Args:
        unknowns: List of unknown proposition names

    Returns:
        List of QRankedProposition sorted by Q-value descending (HIGH first)
    """
    if not unknowns:
        return []

    ranked = []
    for prop in unknowns:
        config = get_q_config(prop)
        ranked.append(QRankedProposition(
            proposition=prop,
            q_value=config.q_value,
            why=config.why
        ))

    # Sort by Q-value descending
    return sorted(ranked, key=lambda r: q_ord(r.q_value), reverse=True)


def rank_z3_unknowns(z3_result: dict) -> list[QRankedProposition]:
    """Rank unknowns from z3_erotetic.check_evocation result.

    Args:
        z3_result: Dict with 'isEmpty', 'unknowns', 'count' from z3_erotetic

    Returns:
        List of QRankedProposition sorted by Q-value descending
    """
    if z3_result.get('isEmpty', True):
        return []

    unknowns = z3_result.get('unknowns', [])
    return rank_by_q(unknowns)
