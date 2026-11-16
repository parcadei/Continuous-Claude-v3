"""Tests for v6.0-hybrid skill schema.

TDD: These tests are written BEFORE implementation.
Run: uv run pytest tests/unit/test_skill_schema_v6.py -v
"""

import pytest
from typing import Optional


class TestSkillSchemaV6:
    """Tests for SkillV6 Pydantic model."""

    def test_import_schema_module(self):
        """Schema module should be importable."""
        from scripts.skill_schema_v6 import SkillV6
        assert SkillV6 is not None

    def test_q_table_entry_requires_mitigation_for_forbidden(self):
        """QTableEntry with Q=-inf MUST have mitigation."""
        from scripts.skill_schema_v6 import QTableEntry

        # Valid: -inf with mitigation
        entry = QTableEntry(
            action="spawn_before_read",
            q_value="-inf",
            why="Agent hallucinates without context",
            mitigation="read first"
        )
        assert entry.mitigation == "read first"

        # Invalid: -inf without mitigation should raise
        with pytest.raises(ValueError, match="mitigation required"):
            QTableEntry(
                action="spawn_before_read",
                q_value="-inf",
                why="Agent hallucinates without context",
                mitigation=None
            )

    def test_q_table_entry_mitigation_optional_for_non_forbidden(self):
        """QTableEntry with Q!=inf can omit mitigation."""
        from scripts.skill_schema_v6 import QTableEntry

        entry = QTableEntry(
            action="read_fully",
            q_value="HIGH",
            why="Full context prevents drift"
        )
        assert entry.mitigation is None

    def test_policy_phase_has_q_table(self):
        """PolicyPhase should contain embedded Q-table."""
        from scripts.skill_schema_v6 import PolicyPhase, QTableEntry

        phase = PolicyPhase(
            name="P0: Problem Elicitation",
            policy_rules=["eta |-> ask(problem_description) if not has_problem_desc"],
            q_table=[
                QTableEntry(
                    action="spawn_early",
                    q_value="-inf",
                    why="Missing problem desc causes churn",
                    mitigation="elicit first"
                )
            ]
        )
        assert len(phase.q_table) == 1
        assert phase.q_table[0].action == "spawn_early"

    def test_skill_v6_requires_version_6_hybrid(self):
        """SkillV6 must have version='6.0-hybrid'."""
        from scripts.skill_schema_v6 import SkillV6, InitiationSpec, ActionSpaceSpec

        # Valid version
        skill = SkillV6(
            name="debug",
            version="6.0-hybrid",
            description="Debug issues",
            initiation=InitiationSpec(activate=["user_reports_issue"], skip=["implementation_work"]),
            observation_space=[],
            action_space=ActionSpaceSpec(primary=["Read", "Bash"], forbidden=["Write"]),
            policy=[],
            termination={"success": ["root_cause_found"], "failure": ["scope_external"]},
            output_schema={},
            invariants=[]
        )
        assert skill.version == "6.0-hybrid"

        # Invalid version
        with pytest.raises(ValueError):
            SkillV6(
                name="debug",
                version="5.0-hybrid",  # Wrong version
                description="Debug issues",
                initiation=InitiationSpec(activate=["user_reports_issue"], skip=[]),
                observation_space=[],
                action_space=ActionSpaceSpec(primary=["Read"], forbidden=[]),
                policy=[],
                termination={},
                output_schema={},
                invariants=[]
            )

    def test_initiation_spec_has_activate_and_skip(self):
        """InitiationSpec has activate (when to use) and skip (when not to use)."""
        from scripts.skill_schema_v6 import InitiationSpec

        spec = InitiationSpec(
            activate=["user_reports_issue", "testing_failure"],
            skip=["implementation_work", "feature_building"]
        )
        assert "user_reports_issue" in spec.activate
        assert "feature_building" in spec.skip

    def test_action_space_spec_has_primary_and_forbidden(self):
        """ActionSpaceSpec has primary (allowed) and forbidden tools."""
        from scripts.skill_schema_v6 import ActionSpaceSpec

        spec = ActionSpaceSpec(
            primary=["Read", "Bash", "Task"],
            forbidden=["Write", "Edit"]
        )
        assert "Read" in spec.primary
        assert "Edit" in spec.forbidden

    def test_observation_spec_has_signal_source_interpretation(self):
        """ObservationSpec defines what the skill can observe."""
        from scripts.skill_schema_v6 import ObservationSpec

        spec = ObservationSpec(
            signal="problem_desc",
            source="user prompt",
            interpretation="what went wrong"
        )
        assert spec.signal == "problem_desc"


class TestSkillSchemaV6Serialization:
    """Tests for serialization/deserialization."""

    def test_skill_v6_to_dict(self):
        """SkillV6 should serialize to dict."""
        from scripts.skill_schema_v6 import SkillV6, InitiationSpec, ActionSpaceSpec

        skill = SkillV6(
            name="debug",
            version="6.0-hybrid",
            description="Debug issues",
            initiation=InitiationSpec(activate=["issue"], skip=[]),
            observation_space=[],
            action_space=ActionSpaceSpec(primary=["Read"], forbidden=[]),
            policy=[],
            termination={"success": [], "failure": []},
            output_schema={},
            invariants=[]
        )
        d = skill.model_dump()
        assert d["name"] == "debug"
        assert d["version"] == "6.0-hybrid"

    def test_skill_v6_from_dict(self):
        """SkillV6 should deserialize from dict."""
        from scripts.skill_schema_v6 import SkillV6

        data = {
            "name": "debug",
            "version": "6.0-hybrid",
            "description": "Debug issues",
            "initiation": {"activate": ["issue"], "skip": []},
            "observation_space": [],
            "action_space": {"primary": ["Read"], "forbidden": []},
            "policy": [],
            "termination": {"success": [], "failure": []},
            "output_schema": {},
            "invariants": []
        }
        skill = SkillV6.model_validate(data)
        assert skill.name == "debug"


class TestQValueOrdering:
    """Tests for Q-value comparison and ordering."""

    def test_q_value_ordering(self):
        """Q-values should have defined ordering: HIGH > MED > LOW > -inf."""
        from scripts.skill_schema_v6 import q_ord

        assert q_ord("HIGH") > q_ord("MED")
        assert q_ord("MED") > q_ord("LOW")
        assert q_ord("LOW") > q_ord("-inf")
        assert q_ord("-inf") == float("-inf")

    def test_sort_q_table_entries_by_q_value(self):
        """Q-table entries should be sortable by Q-value."""
        from scripts.skill_schema_v6 import QTableEntry, sort_by_q

        entries = [
            QTableEntry(action="a", q_value="LOW", why="w"),
            QTableEntry(action="b", q_value="HIGH", why="w"),
            QTableEntry(action="c", q_value="-inf", why="w", mitigation="m"),
            QTableEntry(action="d", q_value="MED", why="w"),
        ]

        sorted_entries = sort_by_q(entries)
        assert [e.action for e in sorted_entries] == ["b", "d", "a", "c"]
