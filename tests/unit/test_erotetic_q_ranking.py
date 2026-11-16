"""Tests for erotetic Q-value ranking integration.

TDD: These tests are written BEFORE implementation.
Run: uv run pytest tests/unit/test_erotetic_q_ranking.py -v
"""

import pytest
from typing import NamedTuple


class TestErotetticQRanking:
    """Tests for Q-value ranking of erotetic propositions."""

    def test_import_q_ranking_module(self):
        """Q-ranking module should be importable."""
        from scripts.erotetic_q_ranking import rank_by_q, QRankedProposition
        assert rank_by_q is not None
        assert QRankedProposition is not None

    def test_rank_propositions_by_architectural_impact(self):
        """Propositions should be ranked by architectural impact."""
        from scripts.erotetic_q_ranking import rank_by_q

        unknowns = ["framework", "auth_method", "database", "testing"]

        ranked = rank_by_q(unknowns)

        # Framework should be HIGH (max architectural impact)
        assert ranked[0].proposition == "framework"
        assert ranked[0].q_value == "HIGH"

        # Testing should be lower (less architectural impact)
        testing_entry = next(r for r in ranked if r.proposition == "testing")
        assert testing_entry.q_value in ["MED", "LOW"]

    def test_q_ranked_proposition_has_why_field(self):
        """QRankedProposition should include why explanation."""
        from scripts.erotetic_q_ranking import rank_by_q

        ranked = rank_by_q(["framework"])

        assert ranked[0].why is not None
        assert len(ranked[0].why) > 0
        # Why should explain the architectural impact
        assert "partitions" in ranked[0].why.lower() or "architecture" in ranked[0].why.lower()

    def test_empty_unknowns_returns_empty_list(self):
        """Empty unknowns list should return empty ranked list."""
        from scripts.erotetic_q_ranking import rank_by_q

        ranked = rank_by_q([])

        assert ranked == []

    def test_unknown_proposition_gets_default_ranking(self):
        """Unknown/unrecognized propositions get MED default."""
        from scripts.erotetic_q_ranking import rank_by_q

        ranked = rank_by_q(["custom_unknown_prop"])

        assert len(ranked) == 1
        assert ranked[0].proposition == "custom_unknown_prop"
        assert ranked[0].q_value == "MED"
        assert "unrecognized" in ranked[0].why.lower() or "default" in ranked[0].why.lower()


class TestQValueMapping:
    """Tests for Q-value definitions per proposition type."""

    def test_framework_is_high_impact(self):
        """Framework choice should be HIGH Q-value."""
        from scripts.erotetic_q_ranking import get_q_config

        config = get_q_config("framework")
        assert config.q_value == "HIGH"
        assert "entire" in config.why.lower() or "partitions" in config.why.lower()

    def test_auth_method_is_high_impact(self):
        """Auth method should be HIGH Q-value (major architectural decision)."""
        from scripts.erotetic_q_ranking import get_q_config

        config = get_q_config("auth_method")
        assert config.q_value == "HIGH"

    def test_database_is_high_impact(self):
        """Database choice should be HIGH Q-value."""
        from scripts.erotetic_q_ranking import get_q_config

        config = get_q_config("database")
        assert config.q_value == "HIGH"

    def test_testing_is_medium_impact(self):
        """Testing strategy is MED (affects quality, not core architecture)."""
        from scripts.erotetic_q_ranking import get_q_config

        config = get_q_config("testing")
        assert config.q_value == "MED"

    def test_hosting_is_medium_impact(self):
        """Hosting platform is MED (can change, affects deploy only)."""
        from scripts.erotetic_q_ranking import get_q_config

        config = get_q_config("hosting")
        assert config.q_value == "MED"


class TestIntegrationWithZ3Erotetic:
    """Tests for integration with existing z3_erotetic.py."""

    def test_rank_z3_output(self):
        """Should rank output from z3_erotetic.check_evocation."""
        from scripts.erotetic_q_ranking import rank_z3_unknowns

        # Simulate z3_erotetic output
        z3_result = {
            "isEmpty": False,
            "unknowns": ["framework", "database", "testing"],
            "count": 3
        }

        ranked = rank_z3_unknowns(z3_result)

        assert len(ranked) == 3
        # First should be highest impact
        assert ranked[0].q_value == "HIGH"
        # Should be sorted by Q-value descending
        q_values = [r.q_value for r in ranked]
        assert q_values[0] in ["HIGH"]  # Top is HIGH

    def test_empty_z3_result_returns_empty(self):
        """Empty z3 result (no unknowns) returns empty list."""
        from scripts.erotetic_q_ranking import rank_z3_unknowns

        z3_result = {
            "isEmpty": True,
            "unknowns": [],
            "count": 0
        }

        ranked = rank_z3_unknowns(z3_result)

        assert ranked == []
