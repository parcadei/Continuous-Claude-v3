"""Tests for Skill Confidence Tracking (Phase 2 Tasks 2.15-2.17).

TDD approach: Tests written FIRST, then implementation.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest


# =============================================================================
# Task 2.15: Parameter Confidence Init
# =============================================================================


def test_parameter_confidence_init():
    """Task 2.15: ParameterConfidence can be initialized."""
    from scripts.skill_confidence import ParameterConfidence

    conf = ParameterConfidence(
        skill_id="deploy-api",
        param="hosting",
        value="aws",
        confidence=0.85,
        last_used=datetime.now(timezone.utc),
        use_count=5
    )

    assert conf.skill_id == "deploy-api"
    assert conf.param == "hosting"
    assert conf.value == "aws"
    assert conf.confidence == 0.85
    assert conf.use_count == 5


def test_parameter_confidence_defaults():
    """Task 2.15b: ParameterConfidence has sensible defaults."""
    from scripts.skill_confidence import ParameterConfidence

    conf = ParameterConfidence(
        skill_id="test",
        param="p",
        value="v"
    )

    assert conf.confidence == 1.0
    assert conf.use_count == 1
    assert conf.last_used is not None


# =============================================================================
# Task 2.16: Confidence Decay Function
# =============================================================================


def test_decayed_confidence_30_days():
    """Task 2.16: After 30 days, confidence should be ~50% of original."""
    from scripts.skill_confidence import ParameterConfidence

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    conf = ParameterConfidence(
        skill_id="test",
        param="p",
        value="v",
        confidence=1.0,
        last_used=thirty_days_ago,
        use_count=1
    )

    decayed = conf.decayed_confidence(now)

    # Should be approximately 50% (half-life = 30 days)
    assert 0.45 <= decayed <= 0.55, f"Expected ~0.5, got {decayed}"


def test_decayed_confidence_60_days():
    """Task 2.16b: After 60 days, confidence should be ~25% of original."""
    from scripts.skill_confidence import ParameterConfidence

    now = datetime.now(timezone.utc)
    sixty_days_ago = now - timedelta(days=60)

    conf = ParameterConfidence(
        skill_id="test",
        param="p",
        value="v",
        confidence=1.0,
        last_used=sixty_days_ago,
        use_count=1
    )

    decayed = conf.decayed_confidence(now)

    # Should be approximately 25% (2 half-lives)
    assert 0.20 <= decayed <= 0.30, f"Expected ~0.25, got {decayed}"


def test_decayed_confidence_same_day():
    """Task 2.16c: Same day = no decay."""
    from scripts.skill_confidence import ParameterConfidence

    now = datetime.now(timezone.utc)

    conf = ParameterConfidence(
        skill_id="test",
        param="p",
        value="v",
        confidence=0.9,
        last_used=now,
        use_count=1
    )

    decayed = conf.decayed_confidence(now)

    # Should be unchanged
    assert 0.89 <= decayed <= 0.91


def test_decayed_confidence_frequent_skill():
    """Task 2.16d: Frequent skills can have longer half-life (90 days)."""
    from scripts.skill_confidence import ParameterConfidence

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Frequent skill (use_count > 10) has 90-day half-life
    conf = ParameterConfidence(
        skill_id="test",
        param="p",
        value="v",
        confidence=1.0,
        last_used=thirty_days_ago,
        use_count=15  # Frequent
    )

    decayed = conf.decayed_confidence(now)

    # With 90-day half-life, after 30 days should be ~79% (2^(-30/90))
    assert 0.75 <= decayed <= 0.85, f"Expected ~0.79, got {decayed}"


# =============================================================================
# Task 2.17: Braintrust Metadata Integration
# =============================================================================


def test_log_confidence_braintrust():
    """Task 2.17: log_confidence_to_braintrust() logs metadata."""
    from scripts.skill_confidence import ParameterConfidence, log_confidence_to_braintrust

    conf = ParameterConfidence(
        skill_id="deploy-api",
        param="hosting",
        value="aws",
        confidence=0.85,
        last_used=datetime.now(timezone.utc),
        use_count=5
    )

    # Mock Braintrust
    with patch('scripts.skill_confidence.log_braintrust_metadata') as mock_log:
        log_confidence_to_braintrust(conf)

        mock_log.assert_called_once()
        call_args = mock_log.call_args[1]

        assert "skill_confidence" in call_args["metadata"]
        assert call_args["metadata"]["skill_confidence"]["skill_id"] == "deploy-api"
        assert call_args["metadata"]["skill_confidence"]["param"] == "hosting"


def test_log_confidence_braintrust_no_op_without_client():
    """Task 2.17b: Gracefully handle missing Braintrust client."""
    from scripts.skill_confidence import ParameterConfidence, log_confidence_to_braintrust

    conf = ParameterConfidence(
        skill_id="test",
        param="p",
        value="v"
    )

    # Should not raise even if Braintrust unavailable
    with patch('scripts.skill_confidence.log_braintrust_metadata', side_effect=ImportError("No braintrust")):
        # Should not raise
        log_confidence_to_braintrust(conf)


def test_confidence_to_dict():
    """Task 2.17c: ParameterConfidence can be serialized to dict."""
    from scripts.skill_confidence import ParameterConfidence

    now = datetime.now(timezone.utc)

    conf = ParameterConfidence(
        skill_id="test",
        param="p",
        value="v",
        confidence=0.8,
        last_used=now,
        use_count=3
    )

    d = conf.to_dict()

    assert isinstance(d, dict)
    assert d["skill_id"] == "test"
    assert d["confidence"] == 0.8
    assert "last_used" in d
