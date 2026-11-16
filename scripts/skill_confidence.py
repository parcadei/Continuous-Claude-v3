"""Skill Parameter Confidence Tracking (Phase 2 Tasks 2.15-2.17).

USAGE:
    from scripts.skill_confidence import ParameterConfidence, log_confidence_to_braintrust

    # Track confidence for a parameter
    conf = ParameterConfidence(
        skill_id="deploy-api",
        param="hosting",
        value="aws",
        confidence=0.85,
        last_used=datetime.now(timezone.utc),
        use_count=5
    )

    # Get decayed confidence
    current_conf = conf.decayed_confidence(datetime.now(timezone.utc))

    # Log to Braintrust
    log_confidence_to_braintrust(conf)

Confidence decay:
- Infrequent skills (use_count <= 10): 30-day half-life
- Frequent skills (use_count > 10): 90-day half-life
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any


# Decay constants
INFREQUENT_HALF_LIFE_DAYS = 30
FREQUENT_HALF_LIFE_DAYS = 90
FREQUENT_USE_THRESHOLD = 10


@dataclass
class ParameterConfidence:
    """Confidence tracking for a skill parameter.

    Task 2.15: Defines the confidence tracking dataclass.

    Fields:
        skill_id: Name of the skill
        param: Parameter name
        value: Current learned value
        confidence: Base confidence level (0.0-1.0)
        last_used: When the parameter was last used successfully
        use_count: Number of successful uses
    """
    skill_id: str
    param: str
    value: str
    confidence: float = 1.0
    last_used: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    use_count: int = 1

    def decayed_confidence(self, now: datetime | None = None) -> float:
        """Calculate confidence with time-based decay.

        Task 2.16: Implements exponential decay.

        Decay formula: confidence * 0.5^(days / half_life)

        Half-life selection:
        - Infrequent skills (use_count <= 10): 30 days
        - Frequent skills (use_count > 10): 90 days

        Args:
            now: Current time (defaults to now)

        Returns:
            Decayed confidence value (0.0-1.0)
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Ensure timezone-aware comparison
        last_used = self.last_used
        if last_used.tzinfo is None:
            last_used = last_used.replace(tzinfo=timezone.utc)

        days_since_use = (now - last_used).total_seconds() / (24 * 3600)

        # Select half-life based on usage frequency
        if self.use_count > FREQUENT_USE_THRESHOLD:
            half_life = FREQUENT_HALF_LIFE_DAYS
        else:
            half_life = INFREQUENT_HALF_LIFE_DAYS

        # Exponential decay
        decay_factor = 0.5 ** (days_since_use / half_life)

        return self.confidence * decay_factor

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "skill_id": self.skill_id,
            "param": self.param,
            "value": self.value,
            "confidence": self.confidence,
            "last_used": self.last_used.isoformat(),
            "use_count": self.use_count
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ParameterConfidence':
        """Create from dictionary."""
        last_used = data.get("last_used")
        if isinstance(last_used, str):
            last_used = datetime.fromisoformat(last_used)

        return cls(
            skill_id=data["skill_id"],
            param=data["param"],
            value=data["value"],
            confidence=data.get("confidence", 1.0),
            last_used=last_used or datetime.now(timezone.utc),
            use_count=data.get("use_count", 1)
        )


def log_braintrust_metadata(metadata: dict[str, Any]) -> None:
    """Log metadata to Braintrust (mock-able dependency).

    In production, this would use the Braintrust SDK.
    """
    try:
        import braintrust
        braintrust.log(metadata=metadata)
    except ImportError:
        # Braintrust not available - no-op
        pass


def log_confidence_to_braintrust(conf: ParameterConfidence) -> None:
    """Log confidence data to Braintrust metadata.

    Task 2.17: Integrates confidence tracking with Braintrust.

    Args:
        conf: ParameterConfidence to log
    """
    metadata = {
        "skill_confidence": {
            "skill_id": conf.skill_id,
            "param": conf.param,
            "value": conf.value,
            "confidence": conf.confidence,
            "decayed_confidence": conf.decayed_confidence(),
            "last_used": conf.last_used.isoformat(),
            "use_count": conf.use_count
        }
    }

    try:
        log_braintrust_metadata(metadata=metadata)
    except Exception:
        # Gracefully handle errors - don't let logging break the flow
        pass


def update_confidence_on_use(conf: ParameterConfidence) -> ParameterConfidence:
    """Update confidence after successful use.

    Resets decay timer and increments use count.

    Args:
        conf: Current confidence

    Returns:
        Updated ParameterConfidence
    """
    return ParameterConfidence(
        skill_id=conf.skill_id,
        param=conf.param,
        value=conf.value,
        confidence=min(conf.confidence + 0.05, 1.0),  # Slight boost on use
        last_used=datetime.now(timezone.utc),
        use_count=conf.use_count + 1
    )


def update_confidence_on_correction(
    conf: ParameterConfidence,
    new_value: str
) -> ParameterConfidence:
    """Update confidence after user correction.

    Reduces confidence and updates value.

    Args:
        conf: Current confidence
        new_value: Corrected value

    Returns:
        Updated ParameterConfidence with new value
    """
    return ParameterConfidence(
        skill_id=conf.skill_id,
        param=conf.param,
        value=new_value,
        confidence=max(conf.confidence - 0.1, 0.1),  # Reduce on correction
        last_used=datetime.now(timezone.utc),
        use_count=conf.use_count  # Don't increment on correction
    )
