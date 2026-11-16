"""Skill Tracing - Braintrust integration for skill system decisions.

Phases 19-20 of Self-Improving Skill System.

This module handles:
- Phase 19: Tracing skill lookups (which skill matched, confidence, source)
- Phase 20: Tracing JIT generation (questions asked, answers received, skill generated)

Usage:
    from scripts.agentica_patterns.skill_tracing import SkillTracer, trace_skill_lookup

    # Get tracer for session
    tracer = SkillTracer(session_id='abc-123')

    # Trace a skill lookup
    tracer.trace_lookup(
        query='implement user auth',
        skill_name='auth-skill',
        confidence=0.85,
        source='keyword'
    )

    # Trace JIT generation
    tracer.trace_jit_generation(
        original_prompt='implement webhook',
        questions_asked=['What auth method?'],
        answers_received=['JWT'],
        generated_skill_name='webhook-handler',
        generation_time_ms=1500
    )

Plan reference: thoughts/shared/plans/self-improving-skill-system.md
"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Tracer version for debugging
TRACER_VERSION = '1.0.0'

# Singleton cache for tracers by session
_tracer_cache: dict[str, 'SkillTracer'] = {}


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class TraceSpan:
    """A trace span for Braintrust logging.

    Attributes:
        span_type: Type of span (skill_lookup, jit_generation)
        parent_span_id: Parent session span ID
        metadata: Span metadata dict
        timestamp: When the span was created
    """
    span_type: str
    parent_span_id: str
    metadata: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# =============================================================================
# SkillTracer Class
# =============================================================================


class SkillTracer:
    """Traces skill system decisions to Braintrust.

    Provides tracing for:
    - Skill lookups (keyword, intent, memory matches)
    - JIT skill generation (questions, answers, generated skills)

    Gracefully degrades when Braintrust is unavailable.

    Attributes:
        session_id: Parent session ID for trace hierarchy
    """

    def __init__(self, session_id: str):
        """Initialize the tracer.

        Args:
            session_id: Parent session ID to link traces to
        """
        self.session_id = session_id
        self._api_key = os.environ.get('BRAINTRUST_API_KEY')

    # =========================================================================
    # Availability Check
    # =========================================================================

    def is_available(self) -> bool:
        """Check if Braintrust tracing is available.

        Returns:
            True if API key is configured, False otherwise
        """
        return bool(os.environ.get('BRAINTRUST_API_KEY'))

    # =========================================================================
    # Phase 19: Skill Lookup Tracing
    # =========================================================================

    def trace_lookup(
        self,
        query: str,
        skill_name: str | None,
        confidence: float,
        source: str
    ) -> None:
        """Trace a skill lookup decision.

        Records which skill matched (if any), the confidence level,
        and the source of the match (keyword, intent, memory, none).

        Args:
            query: The original user query
            skill_name: Name of matched skill (None if no match)
            confidence: Confidence score (0.0 to 1.0)
            source: Match source ('keyword', 'intent', 'memory', 'none')
        """
        metadata = {
            'query': query,
            'skill_name': skill_name,
            'confidence': confidence,
            'source': source,
            'timestamp': datetime.now().isoformat(),
            'tracer_version': TRACER_VERSION,
        }

        self._log_span(
            span_type='skill_lookup',
            parent_span_id=self.session_id,
            metadata=metadata
        )

    # =========================================================================
    # Phase 20: JIT Generation Tracing
    # =========================================================================

    def trace_jit_generation(
        self,
        original_prompt: str,
        questions_asked: list[str],
        answers_received: list[str],
        generated_skill_name: str,
        generation_time_ms: int,
        research_performed: list[dict[str, str]] | None = None,
        used_defaults: bool = False
    ) -> None:
        """Trace a JIT skill generation process.

        Records the full generation process including questions asked,
        answers received, research performed, and the generated skill.

        Args:
            original_prompt: The user's original prompt
            questions_asked: List of Q-heuristic questions asked
            answers_received: List of user answers
            generated_skill_name: Name of the generated skill
            generation_time_ms: Time taken to generate in milliseconds
            research_performed: Optional list of research queries made
            used_defaults: Whether default values were used
        """
        metadata = {
            'original_prompt': original_prompt,
            'questions_asked': questions_asked,
            'answers_received': answers_received,
            'generated_skill_name': generated_skill_name,
            'generation_time_ms': generation_time_ms,
            'used_defaults': used_defaults,
            'timestamp': datetime.now().isoformat(),
            'tracer_version': TRACER_VERSION,
        }

        if research_performed:
            metadata['research_performed'] = research_performed

        self._log_span(
            span_type='jit_generation',
            parent_span_id=self.session_id,
            metadata=metadata
        )

    # =========================================================================
    # Internal Logging
    # =========================================================================

    def _log_span(
        self,
        span_type: str,
        parent_span_id: str,
        metadata: dict[str, Any]
    ) -> None:
        """Log a span to Braintrust.

        Gracefully handles unavailable Braintrust service.

        Args:
            span_type: Type of span
            parent_span_id: Parent span ID
            metadata: Span metadata
        """
        if not self.is_available():
            # Gracefully degrade - just return without logging
            return

        try:
            # Import braintrust lazily to avoid import errors
            import braintrust

            # Log to Braintrust
            # Use the existing project from environment or default
            project_name = os.environ.get('BRAINTRUST_PROJECT', 'agentica')

            # Log as a span event
            braintrust.log(
                project=project_name,
                input={'span_type': span_type},
                output=metadata,
                metadata={
                    'parent_span_id': parent_span_id,
                    'span_type': span_type,
                    **metadata
                }
            )

        except ImportError:
            # braintrust not installed - graceful degradation
            pass
        except Exception:
            # Any other error - graceful degradation
            # Don't let tracing failures affect skill system
            pass


# =============================================================================
# Convenience Functions
# =============================================================================


def get_tracer(session_id: str) -> SkillTracer:
    """Get or create a tracer for a session.

    Returns cached tracer for repeated calls with same session_id.

    Args:
        session_id: Session ID for the tracer

    Returns:
        SkillTracer instance
    """
    if session_id not in _tracer_cache:
        _tracer_cache[session_id] = SkillTracer(session_id)
    return _tracer_cache[session_id]


def trace_skill_lookup(
    session_id: str,
    query: str,
    skill_name: str | None,
    confidence: float,
    source: str
) -> None:
    """Convenience function to trace a skill lookup.

    Args:
        session_id: Parent session ID
        query: The original user query
        skill_name: Name of matched skill (None if no match)
        confidence: Confidence score
        source: Match source
    """
    tracer = get_tracer(session_id)
    tracer.trace_lookup(query, skill_name, confidence, source)


def trace_skill_generation(
    session_id: str,
    original_prompt: str,
    questions_asked: list[str],
    answers_received: list[str],
    generated_skill_name: str,
    generation_time_ms: int,
    research_performed: list[dict[str, str]] | None = None,
    used_defaults: bool = False
) -> None:
    """Convenience function to trace JIT skill generation.

    Args:
        session_id: Parent session ID
        original_prompt: The user's original prompt
        questions_asked: List of questions asked
        answers_received: List of answers received
        generated_skill_name: Name of generated skill
        generation_time_ms: Generation time in ms
        research_performed: Optional research queries
        used_defaults: Whether defaults were used
    """
    tracer = get_tracer(session_id)
    tracer.trace_jit_generation(
        original_prompt=original_prompt,
        questions_asked=questions_asked,
        answers_received=answers_received,
        generated_skill_name=generated_skill_name,
        generation_time_ms=generation_time_ms,
        research_performed=research_performed,
        used_defaults=used_defaults
    )
