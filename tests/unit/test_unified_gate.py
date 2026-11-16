"""Tests for the unified orchestration gate.

The unified gate implements a 3-gate flow:
1. Erotetic Gate - Blocks when unknowns exist in the task specification
2. Resources Gate - Blocks when insufficient system resources
3. Composition Gate - Blocks on invalid pattern algebra

All gates must pass before reaching the OrchestrationLayer.
"""

import pytest

from scripts.agentica_patterns.unified_gate import (
    ClarificationRequired,
    CompositionInvalid,
    ResourcesInsufficient,
    UnifiedGate,
)


class TestGate1Erotetic:
    """Tests for the Erotetic gate - blocks when unknowns exist."""

    def test_gate1_blocks_on_unknowns(self):
        """Should raise ClarificationRequired when E(X,Q) != {}."""
        gate = UnifiedGate()

        # Task with unresolved unknowns
        task = {
            "description": "Implement the feature",
            "unknowns": ["Which database to use?", "What is the target schema?"],
        }

        with pytest.raises(ClarificationRequired) as exc_info:
            gate.check_erotetic(task)

        assert len(exc_info.value.unknowns) == 2
        assert "Which database to use?" in exc_info.value.unknowns
        assert "What is the target schema?" in exc_info.value.unknowns

    def test_gate1_passes_when_specified(self):
        """Should continue when E(X,Q) = {}."""
        gate = UnifiedGate()

        # Fully specified task - no unknowns
        task = {
            "description": "Implement the feature using PostgreSQL with users table",
            "unknowns": [],
        }

        # Should not raise
        result = gate.check_erotetic(task)
        assert result is True

    def test_gate1_passes_with_no_unknowns_key(self):
        """Should pass when unknowns key is missing (assumed specified)."""
        gate = UnifiedGate()

        task = {
            "description": "Simple task with all info provided",
        }

        result = gate.check_erotetic(task)
        assert result is True


class TestGate2Resources:
    """Tests for the Resources gate - blocks when insufficient."""

    def test_gate2_blocks_on_insufficient_resources(self):
        """Should raise ResourcesInsufficient when RAM/CPU too low."""
        gate = UnifiedGate()

        # Request more resources than available
        requirements = {
            "ram_gb": 128,  # Exceeds typical system
            "cpu_cores": 64,
        }

        with pytest.raises(ResourcesInsufficient) as exc_info:
            gate.check_resources(requirements)

        assert exc_info.value.bottleneck in ["ram", "cpu"]
        assert exc_info.value.suggestion is not None

    def test_gate2_passes_when_resources_available(self):
        """Should continue when resources sufficient."""
        gate = UnifiedGate()

        # Minimal resource requirements
        requirements = {
            "ram_gb": 1,
            "cpu_cores": 1,
        }

        result = gate.check_resources(requirements)
        assert result is True

    def test_gate2_passes_with_no_requirements(self):
        """Should pass when no specific requirements given."""
        gate = UnifiedGate()

        result = gate.check_resources({})
        assert result is True

    def test_gate2_reports_ram_bottleneck(self):
        """Should identify RAM as bottleneck when RAM insufficient."""
        gate = UnifiedGate()

        requirements = {
            "ram_gb": 1000,  # 1TB - definitely insufficient
            "cpu_cores": 1,
        }

        with pytest.raises(ResourcesInsufficient) as exc_info:
            gate.check_resources(requirements)

        assert exc_info.value.bottleneck == "ram"

    def test_gate2_reports_cpu_bottleneck(self):
        """Should identify CPU as bottleneck when CPU insufficient."""
        gate = UnifiedGate()

        requirements = {
            "ram_gb": 1,
            "cpu_cores": 1000,  # Definitely insufficient
        }

        with pytest.raises(ResourcesInsufficient) as exc_info:
            gate.check_resources(requirements)

        assert exc_info.value.bottleneck == "cpu"


class TestGate3Composition:
    """Tests for the Composition gate - blocks on invalid algebra."""

    def test_gate3_blocks_on_invalid_composition(self):
        """Should raise CompositionInvalid for Jury |[shared] (Jury needs iso)."""
        gate = UnifiedGate()

        # Jury pattern with shared composition - invalid!
        # Jury requires isolated agents for independent voting
        composition = {
            "pattern": "Jury",
            "composition_mode": "shared",  # Invalid for Jury
        }

        with pytest.raises(CompositionInvalid) as exc_info:
            gate.check_composition(composition)

        assert len(exc_info.value.errors) > 0
        assert any("Jury" in err or "shared" in err or "iso" in err
                   for err in exc_info.value.errors)

    def test_gate3_passes_on_valid_composition(self):
        """Should continue for Pipeline ;[handoff] Swarm."""
        gate = UnifiedGate()

        # Valid composition: Pipeline with handoff to Swarm
        composition = {
            "pattern": "Pipeline",
            "composition_mode": "handoff",
            "next_pattern": "Swarm",
        }

        result = gate.check_composition(composition)
        assert result is True

    def test_gate3_validates_jury_requires_iso(self):
        """Jury pattern must use isolated composition mode."""
        gate = UnifiedGate()

        # Jury with iso mode - valid
        valid_jury = {
            "pattern": "Jury",
            "composition_mode": "iso",
        }

        result = gate.check_composition(valid_jury)
        assert result is True

    def test_gate3_validates_swarm_allows_shared(self):
        """Swarm pattern can use shared composition mode."""
        gate = UnifiedGate()

        composition = {
            "pattern": "Swarm",
            "composition_mode": "shared",
        }

        result = gate.check_composition(composition)
        assert result is True

    def test_gate3_blocks_on_circular_dependency(self):
        """Should detect circular pattern dependencies."""
        gate = UnifiedGate()

        # Pattern that references itself
        composition = {
            "pattern": "Pipeline",
            "stages": ["A", "B", "A"],  # Circular reference
            "allow_cycles": False,
        }

        with pytest.raises(CompositionInvalid) as exc_info:
            gate.check_composition(composition)

        assert any("circular" in err.lower() or "cycle" in err.lower()
                   for err in exc_info.value.errors)


class TestFullFlow:
    """Tests for the complete 3-gate flow."""

    def test_full_flow_succeeds(self):
        """Should reach OrchestrationLayer when all gates pass."""
        gate = UnifiedGate()

        # Fully valid request
        request = {
            "task": {
                "description": "Build a data pipeline",
                "unknowns": [],
            },
            "resources": {
                "ram_gb": 4,
                "cpu_cores": 2,
            },
            "composition": {
                "pattern": "Pipeline",
                "composition_mode": "handoff",
            },
        }

        # Should pass all gates and return orchestration-ready result
        result = gate.validate(request)

        assert result["passed"] is True
        assert result["ready_for_orchestration"] is True

    def test_full_flow_fails_at_gate1(self):
        """Should fail fast at Gate 1 if unknowns exist."""
        gate = UnifiedGate()

        request = {
            "task": {
                "description": "Build something",
                "unknowns": ["What exactly?"],
            },
            "resources": {"ram_gb": 4, "cpu_cores": 2},
            "composition": {"pattern": "Pipeline", "composition_mode": "handoff"},
        }

        with pytest.raises(ClarificationRequired):
            gate.validate(request)

    def test_full_flow_fails_at_gate2(self):
        """Should fail at Gate 2 if resources insufficient."""
        gate = UnifiedGate()

        request = {
            "task": {
                "description": "Build a data pipeline",
                "unknowns": [],
            },
            "resources": {
                "ram_gb": 1000,  # Insufficient
                "cpu_cores": 2,
            },
            "composition": {"pattern": "Pipeline", "composition_mode": "handoff"},
        }

        with pytest.raises(ResourcesInsufficient):
            gate.validate(request)

    def test_full_flow_fails_at_gate3(self):
        """Should fail at Gate 3 if composition invalid."""
        gate = UnifiedGate()

        request = {
            "task": {
                "description": "Build with voting",
                "unknowns": [],
            },
            "resources": {"ram_gb": 4, "cpu_cores": 2},
            "composition": {
                "pattern": "Jury",
                "composition_mode": "shared",  # Invalid for Jury
            },
        }

        with pytest.raises(CompositionInvalid):
            gate.validate(request)

    def test_gate_order_is_erotetic_resources_composition(self):
        """Gates should be checked in order: Erotetic -> Resources -> Composition."""
        gate = UnifiedGate()

        # Request that would fail all 3 gates
        # Should fail at Gate 1 (Erotetic) first
        request = {
            "task": {
                "description": "?",
                "unknowns": ["Everything"],
            },
            "resources": {"ram_gb": 1000, "cpu_cores": 1000},
            "composition": {"pattern": "Jury", "composition_mode": "shared"},
        }

        # Should raise ClarificationRequired (Gate 1), not the others
        with pytest.raises(ClarificationRequired):
            gate.validate(request)


class TestExceptionDetails:
    """Tests for exception message details."""

    def test_clarification_required_has_unknowns_list(self):
        """ClarificationRequired should contain list of unknowns."""
        unknowns = ["Q1", "Q2", "Q3"]
        exc = ClarificationRequired(unknowns)

        assert exc.unknowns == unknowns
        assert "Q1" in str(exc)

    def test_resources_insufficient_has_bottleneck_and_suggestion(self):
        """ResourcesInsufficient should contain bottleneck and suggestion."""
        exc = ResourcesInsufficient(
            bottleneck="ram",
            suggestion="Consider using streaming or batch processing"
        )

        assert exc.bottleneck == "ram"
        assert exc.suggestion == "Consider using streaming or batch processing"
        assert "ram" in str(exc)

    def test_composition_invalid_has_errors_list(self):
        """CompositionInvalid should contain list of errors."""
        errors = ["Jury requires iso mode", "Cannot chain with shared state"]
        exc = CompositionInvalid(errors)

        assert exc.errors == errors
        assert "Jury requires iso mode" in str(exc)
