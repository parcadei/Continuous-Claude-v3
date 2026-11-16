"""
Tests for patterns module refactor.

These tests verify that after refactoring patterns.py into a package,
all patterns remain importable from both:
1. The package root: from scripts.agentica_patterns.patterns import Swarm
2. Direct module imports: from scripts.agentica_patterns.patterns.swarm import Swarm

All tests should FAIL with ImportError initially (RED phase of TDD).
"""

import pytest


# =============================================================================
# Package Root Imports (from scripts.agentica_patterns.patterns import X)
# =============================================================================


class TestPackageRootImports:
    """Test that all patterns are importable from the package root."""

    def test_import_swarm_from_package(self):
        """Swarm should be importable from patterns package root."""
        from scripts.agentica_patterns.patterns import Swarm
        assert Swarm is not None

    def test_import_pipeline_from_package(self):
        """Pipeline should be importable from patterns package root."""
        from scripts.agentica_patterns.patterns import Pipeline
        assert Pipeline is not None

    def test_import_hierarchical_from_package(self):
        """Hierarchical should be importable from patterns package root."""
        from scripts.agentica_patterns.patterns import Hierarchical
        assert Hierarchical is not None

    def test_import_jury_from_package(self):
        """Jury should be importable from patterns package root."""
        from scripts.agentica_patterns.patterns import Jury
        assert Jury is not None

    def test_import_generator_critic_from_package(self):
        """GeneratorCritic should be importable from patterns package root."""
        from scripts.agentica_patterns.patterns import GeneratorCritic
        assert GeneratorCritic is not None

    def test_import_circuit_breaker_from_package(self):
        """CircuitBreaker should be importable from patterns package root."""
        from scripts.agentica_patterns.patterns import CircuitBreaker
        assert CircuitBreaker is not None

    def test_import_adversarial_from_package(self):
        """Adversarial should be importable from patterns package root."""
        from scripts.agentica_patterns.patterns import Adversarial
        assert Adversarial is not None

    def test_import_chain_of_responsibility_from_package(self):
        """ChainOfResponsibility should be importable from patterns package root."""
        from scripts.agentica_patterns.patterns import ChainOfResponsibility
        assert ChainOfResponsibility is not None

    def test_import_map_reduce_from_package(self):
        """MapReduce should be importable from patterns package root."""
        from scripts.agentica_patterns.patterns import MapReduce
        assert MapReduce is not None

    def test_import_blackboard_from_package(self):
        """Blackboard should be importable from patterns package root."""
        from scripts.agentica_patterns.patterns import Blackboard
        assert Blackboard is not None

    def test_import_event_driven_from_package(self):
        """EventDriven should be importable from patterns package root."""
        from scripts.agentica_patterns.patterns import EventDriven
        assert EventDriven is not None


# =============================================================================
# Direct Module Imports (from scripts.agentica_patterns.patterns.X import Y)
# =============================================================================


class TestDirectModuleImports:
    """Test that all patterns are importable from their own modules."""

    def test_import_swarm_direct(self):
        """Swarm should be importable from its own module."""
        from scripts.agentica_patterns.patterns.swarm import Swarm
        assert Swarm is not None

    def test_import_pipeline_direct(self):
        """Pipeline should be importable from its own module."""
        from scripts.agentica_patterns.patterns.pipeline import Pipeline
        assert Pipeline is not None

    def test_import_hierarchical_direct(self):
        """Hierarchical should be importable from its own module."""
        from scripts.agentica_patterns.patterns.hierarchical import Hierarchical
        assert Hierarchical is not None

    def test_import_jury_direct(self):
        """Jury should be importable from its own module."""
        from scripts.agentica_patterns.patterns.jury import Jury
        assert Jury is not None

    def test_import_generator_critic_direct(self):
        """GeneratorCritic should be importable from its own module."""
        from scripts.agentica_patterns.patterns.generator_critic import GeneratorCritic
        assert GeneratorCritic is not None

    def test_import_circuit_breaker_direct(self):
        """CircuitBreaker should be importable from its own module."""
        from scripts.agentica_patterns.patterns.circuit_breaker import CircuitBreaker
        assert CircuitBreaker is not None

    def test_import_adversarial_direct(self):
        """Adversarial should be importable from its own module."""
        from scripts.agentica_patterns.patterns.adversarial import Adversarial
        assert Adversarial is not None

    def test_import_chain_of_responsibility_direct(self):
        """ChainOfResponsibility should be importable from its own module."""
        from scripts.agentica_patterns.patterns.chain_of_responsibility import ChainOfResponsibility
        assert ChainOfResponsibility is not None

    def test_import_map_reduce_direct(self):
        """MapReduce should be importable from its own module."""
        from scripts.agentica_patterns.patterns.map_reduce import MapReduce
        assert MapReduce is not None

    def test_import_blackboard_direct(self):
        """Blackboard should be importable from its own module."""
        from scripts.agentica_patterns.patterns.blackboard import Blackboard
        assert Blackboard is not None

    def test_import_event_driven_direct(self):
        """EventDriven should be importable from its own module."""
        from scripts.agentica_patterns.patterns.event_driven import EventDriven
        assert EventDriven is not None


# =============================================================================
# Primitives Imports (should still work from primitives module)
# =============================================================================


class TestPrimitivesImports:
    """Test that primitives remain importable from their current location."""

    def test_import_consensus_from_primitives(self):
        """Consensus should be importable from primitives."""
        from scripts.agentica_patterns.patterns.primitives import Consensus
        assert Consensus is not None

    def test_import_consensus_mode_from_primitives(self):
        """ConsensusMode should be importable from primitives."""
        from scripts.agentica_patterns.patterns.primitives import ConsensusMode
        assert ConsensusMode is not None

    def test_import_aggregator_from_primitives(self):
        """Aggregator should be importable from primitives."""
        from scripts.agentica_patterns.patterns.primitives import Aggregator
        assert Aggregator is not None

    def test_import_aggregate_mode_from_primitives(self):
        """AggregateMode should be importable from primitives."""
        from scripts.agentica_patterns.patterns.primitives import AggregateMode
        assert AggregateMode is not None

    def test_import_handoff_state_from_primitives(self):
        """HandoffState should be importable from primitives."""
        from scripts.agentica_patterns.patterns.primitives import HandoffState
        assert HandoffState is not None


# =============================================================================
# Supporting Types Imports
# =============================================================================


class TestSupportingTypesImports:
    """Test that supporting types are importable from patterns package."""

    def test_import_handler_from_package(self):
        """Handler dataclass should be importable from patterns package."""
        from scripts.agentica_patterns.patterns import Handler
        assert Handler is not None

    def test_import_specialist_from_package(self):
        """Specialist dataclass should be importable from patterns package."""
        from scripts.agentica_patterns.patterns import Specialist
        assert Specialist is not None

    def test_import_event_from_package(self):
        """Event dataclass should be importable from patterns package."""
        from scripts.agentica_patterns.patterns import Event
        assert Event is not None

    def test_import_subscriber_from_package(self):
        """Subscriber dataclass should be importable from patterns package."""
        from scripts.agentica_patterns.patterns import Subscriber
        assert Subscriber is not None

    def test_import_circuit_state_from_package(self):
        """CircuitState enum should be importable from patterns package."""
        from scripts.agentica_patterns.patterns import CircuitState
        assert CircuitState is not None

    def test_import_blackboard_state_from_package(self):
        """BlackboardState should be importable from patterns package."""
        from scripts.agentica_patterns.patterns import BlackboardState
        assert BlackboardState is not None

    def test_import_blackboard_result_from_package(self):
        """BlackboardResult should be importable from patterns package."""
        from scripts.agentica_patterns.patterns import BlackboardResult
        assert BlackboardResult is not None
