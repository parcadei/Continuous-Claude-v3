"""Tests for Braintrust skill tracing - Phases 19-20 of Self-Improving Skill System.

Phase 19: Trace skill lookups (which skill matched, confidence, source)
Phase 20: Trace JIT generation (questions asked, answers received, skill generated)

Plan reference: thoughts/shared/plans/self-improving-skill-system.md
"""

import json
from unittest.mock import patch

import pytest

# =============================================================================
# SkillTracer Interface Tests (Phase 19)
# =============================================================================


class TestSkillTracerInterface:
    """Test the SkillTracer class interface."""

    def test_skill_tracer_class_exists(self):
        """SkillTracer class should exist."""
        from scripts.agentica_patterns.skill_tracing import SkillTracer

        assert SkillTracer is not None

    def test_skill_tracer_has_trace_lookup(self):
        """SkillTracer should have trace_lookup method."""
        from scripts.agentica_patterns.skill_tracing import SkillTracer

        tracer = SkillTracer(session_id='test-session')
        assert hasattr(tracer, 'trace_lookup')
        assert callable(tracer.trace_lookup)

    def test_skill_tracer_has_trace_jit_generation(self):
        """SkillTracer should have trace_jit_generation method."""
        from scripts.agentica_patterns.skill_tracing import SkillTracer

        tracer = SkillTracer(session_id='test-session')
        assert hasattr(tracer, 'trace_jit_generation')
        assert callable(tracer.trace_jit_generation)

    def test_skill_tracer_has_is_available(self):
        """SkillTracer should have is_available method."""
        from scripts.agentica_patterns.skill_tracing import SkillTracer

        tracer = SkillTracer(session_id='test-session')
        assert hasattr(tracer, 'is_available')
        assert callable(tracer.is_available)


# =============================================================================
# Skill Lookup Tracing Tests (Phase 19)
# =============================================================================


class TestTraceLookup:
    """Test tracing skill lookups."""

    @pytest.fixture
    def tracer(self):
        """Create a test tracer."""
        from scripts.agentica_patterns.skill_tracing import SkillTracer
        return SkillTracer(session_id='test-session-123')

    def test_trace_lookup_creates_span(self, tracer):
        """trace_lookup should create a Braintrust span."""
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_lookup(
                query='implement user auth',
                skill_name='auth-skill',
                confidence=0.85,
                source='keyword'
            )

            mock_log.assert_called_once()
            call_args = mock_log.call_args[1]
            assert call_args['span_type'] == 'skill_lookup'

    def test_trace_lookup_includes_query(self, tracer):
        """trace_lookup should include the original query."""
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_lookup(
                query='debug memory leak',
                skill_name='debug-skill',
                confidence=0.75,
                source='intent'
            )

            call_args = mock_log.call_args[1]
            assert call_args['metadata']['query'] == 'debug memory leak'

    def test_trace_lookup_includes_matched_skill(self, tracer):
        """trace_lookup should include the matched skill name."""
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_lookup(
                query='test prompt',
                skill_name='matched-skill',
                confidence=0.9,
                source='keyword'
            )

            call_args = mock_log.call_args[1]
            assert call_args['metadata']['skill_name'] == 'matched-skill'

    def test_trace_lookup_includes_confidence(self, tracer):
        """trace_lookup should include confidence score."""
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_lookup(
                query='test',
                skill_name='skill',
                confidence=0.88,
                source='memory'
            )

            call_args = mock_log.call_args[1]
            assert call_args['metadata']['confidence'] == 0.88

    def test_trace_lookup_includes_source(self, tracer):
        """trace_lookup should include match source."""
        with patch.object(tracer, '_log_span') as mock_log:
            # Test keyword source
            tracer.trace_lookup(
                query='test',
                skill_name='skill',
                confidence=0.9,
                source='keyword'
            )
            assert mock_log.call_args[1]['metadata']['source'] == 'keyword'

            # Test memory source
            tracer.trace_lookup(
                query='test',
                skill_name='skill',
                confidence=0.7,
                source='memory'
            )
            assert mock_log.call_args[1]['metadata']['source'] == 'memory'

    def test_trace_lookup_no_match(self, tracer):
        """trace_lookup should handle no match case."""
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_lookup(
                query='unknown task',
                skill_name=None,
                confidence=0.0,
                source='none'
            )

            call_args = mock_log.call_args[1]
            assert call_args['metadata']['skill_name'] is None
            assert call_args['metadata']['confidence'] == 0.0
            assert call_args['metadata']['source'] == 'none'

    def test_trace_lookup_includes_timestamp(self, tracer):
        """trace_lookup should include timestamp."""
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_lookup(
                query='test',
                skill_name='skill',
                confidence=0.8,
                source='keyword'
            )

            call_args = mock_log.call_args[1]
            assert 'timestamp' in call_args['metadata']

    def test_trace_lookup_links_to_session(self, tracer):
        """trace_lookup should link to the parent session."""
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_lookup(
                query='test',
                skill_name='skill',
                confidence=0.9,
                source='keyword'
            )

            call_args = mock_log.call_args[1]
            assert call_args['parent_span_id'] == 'test-session-123'


# =============================================================================
# JIT Generation Tracing Tests (Phase 20)
# =============================================================================


class TestTraceJitGeneration:
    """Test tracing JIT skill generation."""

    @pytest.fixture
    def tracer(self):
        """Create a test tracer."""
        from scripts.agentica_patterns.skill_tracing import SkillTracer
        return SkillTracer(session_id='test-session-456')

    def test_trace_jit_generation_creates_span(self, tracer):
        """trace_jit_generation should create a Braintrust span."""
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_jit_generation(
                original_prompt='implement webhook handler',
                questions_asked=['What auth method?'],
                answers_received=['JWT'],
                generated_skill_name='webhook-handler',
                generation_time_ms=1500
            )

            mock_log.assert_called_once()
            call_args = mock_log.call_args[1]
            assert call_args['span_type'] == 'jit_generation'

    def test_trace_jit_generation_includes_prompt(self, tracer):
        """trace_jit_generation should include original prompt."""
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_jit_generation(
                original_prompt='debug API timeout',
                questions_asked=[],
                answers_received=[],
                generated_skill_name='api-timeout-debug',
                generation_time_ms=1000
            )

            call_args = mock_log.call_args[1]
            assert call_args['metadata']['original_prompt'] == 'debug API timeout'

    def test_trace_jit_generation_includes_questions(self, tracer):
        """trace_jit_generation should include questions asked."""
        questions = [
            'What is the goal?',
            'Which tools should be used?',
            'What test coverage is needed?'
        ]
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_jit_generation(
                original_prompt='implement feature',
                questions_asked=questions,
                answers_received=['Build X', 'Bash, Read', 'Unit tests'],
                generated_skill_name='feature-skill',
                generation_time_ms=2000
            )

            call_args = mock_log.call_args[1]
            assert call_args['metadata']['questions_asked'] == questions
            assert len(call_args['metadata']['questions_asked']) == 3

    def test_trace_jit_generation_includes_answers(self, tracer):
        """trace_jit_generation should include answers received."""
        answers = ['JWT authentication', 'Full TDD', 'Auto-detect']
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_jit_generation(
                original_prompt='implement auth',
                questions_asked=['Auth method?', 'Test coverage?', 'Target files?'],
                answers_received=answers,
                generated_skill_name='auth-impl',
                generation_time_ms=1800
            )

            call_args = mock_log.call_args[1]
            assert call_args['metadata']['answers_received'] == answers

    def test_trace_jit_generation_includes_skill_name(self, tracer):
        """trace_jit_generation should include generated skill name."""
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_jit_generation(
                original_prompt='implement rate limiting',
                questions_asked=[],
                answers_received=[],
                generated_skill_name='rate-limiting-middleware',
                generation_time_ms=900
            )

            call_args = mock_log.call_args[1]
            assert call_args['metadata']['generated_skill_name'] == 'rate-limiting-middleware'

    def test_trace_jit_generation_includes_timing(self, tracer):
        """trace_jit_generation should include generation time."""
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_jit_generation(
                original_prompt='test',
                questions_asked=[],
                answers_received=[],
                generated_skill_name='test-skill',
                generation_time_ms=2500
            )

            call_args = mock_log.call_args[1]
            assert call_args['metadata']['generation_time_ms'] == 2500

    def test_trace_jit_generation_includes_research(self, tracer):
        """trace_jit_generation should include research performed."""
        research = [
            {'source': 'nia', 'query': 'webhook best practices'},
            {'source': 'codebase', 'query': 'existing webhook patterns'}
        ]
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_jit_generation(
                original_prompt='implement webhook',
                questions_asked=[],
                answers_received=[],
                generated_skill_name='webhook-skill',
                generation_time_ms=3000,
                research_performed=research
            )

            call_args = mock_log.call_args[1]
            assert 'research_performed' in call_args['metadata']
            assert len(call_args['metadata']['research_performed']) == 2

    def test_trace_jit_generation_links_to_session(self, tracer):
        """trace_jit_generation should link to parent session."""
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_jit_generation(
                original_prompt='test',
                questions_asked=[],
                answers_received=[],
                generated_skill_name='test',
                generation_time_ms=100
            )

            call_args = mock_log.call_args[1]
            assert call_args['parent_span_id'] == 'test-session-456'

    def test_trace_jit_generation_uses_defaults_flag(self, tracer):
        """trace_jit_generation should track when defaults were used."""
        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_jit_generation(
                original_prompt='quick task',
                questions_asked=['What is the goal?'],
                answers_received=['use defaults'],
                generated_skill_name='quick-task',
                generation_time_ms=500,
                used_defaults=True
            )

            call_args = mock_log.call_args[1]
            assert call_args['metadata']['used_defaults'] is True


# =============================================================================
# Tracer Availability Tests
# =============================================================================


class TestTracerAvailability:
    """Test tracer availability and graceful degradation."""

    def test_is_available_returns_bool(self):
        """is_available should return boolean."""
        from scripts.agentica_patterns.skill_tracing import SkillTracer

        tracer = SkillTracer(session_id='test')
        result = tracer.is_available()
        assert isinstance(result, bool)

    def test_is_available_checks_api_key(self):
        """is_available should check for BRAINTRUST_API_KEY."""
        from scripts.agentica_patterns.skill_tracing import SkillTracer

        with patch.dict('os.environ', {'BRAINTRUST_API_KEY': 'test-key'}):
            tracer = SkillTracer(session_id='test')
            assert tracer.is_available() is True

        with patch.dict('os.environ', {}, clear=True):
            tracer = SkillTracer(session_id='test')
            assert tracer.is_available() is False

    def test_trace_lookup_graceful_when_unavailable(self):
        """trace_lookup should not crash when Braintrust unavailable."""
        from scripts.agentica_patterns.skill_tracing import SkillTracer

        with patch.dict('os.environ', {}, clear=True):
            tracer = SkillTracer(session_id='test')

            # Should not raise even if tracing unavailable
            tracer.trace_lookup(
                query='test',
                skill_name='test-skill',
                confidence=0.9,
                source='keyword'
            )

    def test_trace_jit_graceful_when_unavailable(self):
        """trace_jit_generation should not crash when unavailable."""
        from scripts.agentica_patterns.skill_tracing import SkillTracer

        with patch.dict('os.environ', {}, clear=True):
            tracer = SkillTracer(session_id='test')

            # Should not raise even if tracing unavailable
            tracer.trace_jit_generation(
                original_prompt='test',
                questions_asked=[],
                answers_received=[],
                generated_skill_name='test',
                generation_time_ms=100
            )


# =============================================================================
# Trace Data Structure Tests
# =============================================================================


class TestTraceDataStructure:
    """Test trace data structure and serialization."""

    def test_trace_data_is_json_serializable(self):
        """Trace data should be JSON serializable."""
        from scripts.agentica_patterns.skill_tracing import SkillTracer

        tracer = SkillTracer(session_id='test')

        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_lookup(
                query='test query',
                skill_name='test-skill',
                confidence=0.85,
                source='keyword'
            )

            call_args = mock_log.call_args[1]
            # Should not raise
            json.dumps(call_args['metadata'])

    def test_trace_includes_version_info(self):
        """Trace should include tracer version info."""
        from scripts.agentica_patterns.skill_tracing import SkillTracer

        tracer = SkillTracer(session_id='test')

        with patch.object(tracer, '_log_span') as mock_log:
            tracer.trace_lookup(
                query='test',
                skill_name='skill',
                confidence=0.9,
                source='keyword'
            )

            call_args = mock_log.call_args[1]
            assert 'tracer_version' in call_args['metadata']


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_trace_skill_lookup_exists(self):
        """Module should have trace_skill_lookup function."""
        from scripts.agentica_patterns.skill_tracing import trace_skill_lookup

        assert callable(trace_skill_lookup)

    def test_trace_skill_generation_exists(self):
        """Module should have trace_skill_generation function."""
        from scripts.agentica_patterns.skill_tracing import trace_skill_generation

        assert callable(trace_skill_generation)

    def test_get_tracer_singleton(self):
        """get_tracer should return singleton instance."""
        from scripts.agentica_patterns.skill_tracing import get_tracer

        tracer1 = get_tracer('session-1')
        tracer2 = get_tracer('session-1')

        # Same session should return same tracer
        assert tracer1 is tracer2

        # Different session should return different tracer
        tracer3 = get_tracer('session-2')
        assert tracer1 is not tracer3
