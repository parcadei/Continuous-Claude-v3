"""
v6.0-hybrid Skill Schema

Pydantic models for the decision theory-based skill format.
Implements Options Framework: Skill := (I, Y, U, pi, beta) with embedded Q-guidance.

Usage:
    from scripts.skill_schema_v6 import SkillV6, QTableEntry, PolicyPhase

References:
    - thoughts/shared/agents/decision-theory-research/3-skill-format.md
    - thoughts/shared/agents/decision-theory-research/JURY_VERDICT.md
"""

from typing import Literal, Optional, Any
from pydantic import BaseModel, field_validator, model_validator


# Q-value types: symbolic for readability
QValue = Literal["HIGH", "MED", "LOW", "-inf"]


def q_ord(q: QValue) -> float:
    """Convert Q-value to numeric for ordering. HIGH > MED > LOW > -inf."""
    mapping = {
        "HIGH": 1.0,
        "MED": 0.5,
        "LOW": 0.1,
        "-inf": float("-inf")
    }
    return mapping.get(q, 0.5)  # Default to MED


class QTableEntry(BaseModel):
    """Entry in a Q-table with action, value, reasoning, and mitigation.

    The mitigation column is REQUIRED for forbidden actions (Q=-inf).
    This preserves the 'why' that pure decision theory loses.
    """
    action: str
    q_value: QValue
    why: str
    mitigation: Optional[str] = None

    @model_validator(mode='after')
    def check_mitigation_for_forbidden(self) -> 'QTableEntry':
        """Forbidden actions (Q=-inf) MUST have mitigation."""
        if self.q_value == "-inf" and not self.mitigation:
            raise ValueError(
                f"mitigation required for forbidden action '{self.action}' (Q=-inf). "
                "The mitigation column preserves the 'why' - what should be done instead."
            )
        return self


def sort_by_q(entries: list[QTableEntry]) -> list[QTableEntry]:
    """Sort Q-table entries by Q-value descending (HIGH first, -inf last)."""
    return sorted(entries, key=lambda e: q_ord(e.q_value), reverse=True)


class InitiationSpec(BaseModel):
    """When to activate or skip this skill.

    Maps to Options Framework: I (Initiation set).
    """
    activate: list[str]  # Conditions when skill should be used
    skip: list[str]  # Conditions when skill should NOT be used


class ObservationSpec(BaseModel):
    """What signals the skill can observe.

    Maps to Options Framework: Y (Observation space).
    """
    signal: str  # What is observed
    source: str  # Where it comes from
    interpretation: str  # What it means for the skill


class ActionSpaceSpec(BaseModel):
    """Available and forbidden actions.

    Maps to Options Framework: U (Action space).
    """
    primary: list[str]  # Allowed tools/actions
    forbidden: list[str]  # Never allowed (static constraints)


class PolicyPhase(BaseModel):
    """A phase in the skill's policy with embedded Q-table.

    Maps to Options Framework: pi (Policy) - partitioned into phases.
    """
    name: str  # e.g., "P0: Problem Elicitation"
    policy_rules: list[str]  # eta |-> action mappings
    q_table: list[QTableEntry] = []  # Phase-specific Q-guidance


class TerminationSpec(BaseModel):
    """When the skill terminates.

    Maps to Options Framework: beta (Termination function).
    """
    success: list[str]  # Conditions for beta=1.0 (done, succeeded)
    failure: list[str]  # Conditions for beta=1.0 (done, failed)


class SkillV6(BaseModel):
    """v6.0-hybrid Skill Schema.

    Implements the Options Framework: Skill := (I, Y, U, pi, beta)
    with embedded Q-guidance in each policy phase.

    Token efficiency: ~3x compression vs prose while preserving signal.
    """
    name: str
    version: Literal["6.0-hybrid"]
    description: str

    # Options Framework components
    initiation: InitiationSpec  # I
    observation_space: list[ObservationSpec]  # Y
    action_space: ActionSpaceSpec  # U
    policy: list[PolicyPhase]  # pi (with embedded Q)
    termination: dict[str, list[str]]  # beta (flexible format)

    # Additional metadata
    output_schema: dict[str, Any]  # Required output structure
    invariants: list[str]  # English invariants (no formal axioms)

    @field_validator('version')
    @classmethod
    def check_version(cls, v: str) -> str:
        """Ensure version is exactly '6.0-hybrid'."""
        if v != "6.0-hybrid":
            raise ValueError(f"Version must be '6.0-hybrid', got '{v}'")
        return v
