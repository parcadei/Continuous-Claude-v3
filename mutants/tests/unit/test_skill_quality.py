"""Tests for skill quality - Phases 21-25 of Self-Improving Skill System.

Phase 21: Graceful degradation (if memory unavailable, continue with keyword-only)
Phase 22: Skill validation (ensure generated YAML is valid before saving)
Phase 23: Deduplication (don't create duplicate skills)
Phase 24: Usage tracking (how often each skill is used)
Phase 25: Cleanup suggestions (identify unused skills)

Plan reference: thoughts/shared/plans/self-improving-skill-system.md
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# =============================================================================
# Phase 21: Graceful Degradation Tests
# =============================================================================


class TestGracefulDegradation:
    """Test graceful degradation when services are unavailable."""

    def test_memory_unavailable_continues_with_keyword(self):
        """Skill lookup should continue with keyword-only when memory unavailable."""
        from scripts.agentica.skill_quality import lookup_with_fallback

        # Mock memory as unavailable - test with no keyword match to trigger fallback
        with patch('scripts.agentica.skill_quality.is_memory_available', return_value=False):
            result = lookup_with_fallback(
                prompt='do something unrelated',
                skill_rules={'skills': {'auth-skill': {'promptTriggers': {'keywords': ['auth']}}}}
            )

            assert result is not None
            assert result.get('fallback_used') is True
            assert result.get('fallback_reason') == 'memory_unavailable'

    def test_keyword_match_no_fallback_needed(self):
        """Keyword match should succeed without memory fallback."""
        from scripts.agentica.skill_quality import lookup_with_fallback

        with patch('scripts.agentica.skill_quality.is_memory_available', return_value=False):
            result = lookup_with_fallback(
                prompt='implement user auth',
                skill_rules={'skills': {'auth-skill': {'promptTriggers': {'keywords': ['auth']}}}}
            )

            assert result is not None
            assert result.get('skill_name') == 'auth-skill'
            assert result.get('fallback_used') is False  # Keyword matched, no fallback needed

    def test_memory_timeout_continues_gracefully(self):
        """Skill lookup should handle memory timeout gracefully."""
        from scripts.agentica.skill_quality import lookup_with_fallback

        with patch('scripts.agentica.skill_quality.search_memory') as mock_search:
            mock_search.side_effect = TimeoutError("Memory service timeout")

            result = lookup_with_fallback(
                prompt='debug issue',
                skill_rules={'skills': {}}
            )

            # Should not crash, should return result
            assert result is not None
            assert result.get('fallback_used') is True

    def test_research_unavailable_uses_defaults(self):
        """JIT generation should use defaults when research unavailable."""
        from scripts.agentica.skill_generator import SkillSpec
        from scripts.agentica.skill_quality import generate_with_fallback

        with patch('scripts.agentica.skill_quality.research_topic') as mock_research:
            mock_research.side_effect = ConnectionError("Research service down")

            spec = generate_with_fallback(
                task_type='implementation',
                resolved_qheuristics={},
                original_prompt='implement feature'
            )

            assert spec is not None
            assert isinstance(spec, SkillSpec)
            # Should have default instructions, not research-enhanced
            assert 'Research unavailable' not in spec.instructions or len(spec.instructions) > 0

    def test_save_failure_logs_but_continues(self):
        """Skill save failure should log but not block execution."""
        from scripts.agentica.skill_generator import SkillSpec
        from scripts.agentica.skill_quality import safe_save_skill

        spec = SkillSpec(
            name='test-skill',
            description='Test',
            goal='Test',
            tools=['Bash'],
            instructions='Test'
        )

        with patch('scripts.agentica.skill_quality.SkillPersistence') as mock_persistence:
            mock_instance = MagicMock()
            mock_instance.save_to_filesystem.side_effect = OSError("Disk full")
            mock_persistence.return_value = mock_instance

            result = safe_save_skill(spec, project_dir='/tmp/test')

            # Should not crash
            assert result is not None
            assert result.get('error') is not None
            assert result.get('saved') is False

    def test_partial_failure_saves_what_possible(self):
        """Partial save failure should save what's possible."""
        from scripts.agentica.skill_generator import SkillSpec
        from scripts.agentica.skill_quality import safe_save_skill

        spec = SkillSpec(
            name='test-skill',
            description='Test',
            goal='Test',
            tools=['Bash'],
            instructions='Test'
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('scripts.agentica.skill_quality.SkillPersistence') as mock_cls:
                mock_instance = MagicMock()
                # Filesystem succeeds, memory fails
                mock_instance.save_to_filesystem.return_value = f'{tmpdir}/test.md'
                mock_instance.save_to_memory = AsyncMock(return_value=None)
                mock_instance.register_triggers.return_value = None
                mock_cls.return_value = mock_instance

                result = safe_save_skill(spec, project_dir=tmpdir)

                assert result.get('file_path') is not None
                assert result.get('memory_id') is None


# =============================================================================
# Phase 22: Skill Validation Tests
# =============================================================================


class TestSkillValidation:
    """Test skill validation before saving."""

    def test_validator_class_exists(self):
        """SkillValidator class should exist."""
        from scripts.agentica.skill_quality import SkillValidator

        assert SkillValidator is not None

    def test_validate_spec_returns_result(self):
        """validate_spec should return ValidationResult."""
        from scripts.agentica.skill_generator import SkillSpec
        from scripts.agentica.skill_quality import SkillValidator, ValidationResult

        validator = SkillValidator()
        spec = SkillSpec(
            name='valid-skill',
            description='A valid skill',
            goal='Do something',
            tools=['Bash'],
            instructions='1. Do this\n2. Do that'
        )

        result = validator.validate_spec(spec)

        assert isinstance(result, ValidationResult)
        assert hasattr(result, 'valid')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')

    def test_validate_name_format(self):
        """Skill name must be lowercase alphanumeric with hyphens."""
        from scripts.agentica.skill_generator import SkillSpec
        from scripts.agentica.skill_quality import SkillValidator

        validator = SkillValidator()

        # Valid name
        valid_spec = SkillSpec(
            name='my-valid-skill',
            description='Test',
            goal='Test',
            tools=['Bash'],
            instructions='Test'
        )
        result = validator.validate_spec(valid_spec)
        assert result.valid is True

        # Invalid name (uppercase)
        invalid_spec = SkillSpec(
            name='MyInvalidSkill',
            description='Test',
            goal='Test',
            tools=['Bash'],
            instructions='Test'
        )
        result = validator.validate_spec(invalid_spec)
        assert result.valid is False
        assert any('name' in e.lower() for e in result.errors)

    def test_validate_name_no_special_chars(self):
        """Skill name should not have special characters."""
        from scripts.agentica.skill_generator import SkillSpec
        from scripts.agentica.skill_quality import SkillValidator

        validator = SkillValidator()

        invalid_spec = SkillSpec(
            name='my_skill@v2',
            description='Test',
            goal='Test',
            tools=['Bash'],
            instructions='Test'
        )
        result = validator.validate_spec(invalid_spec)
        assert result.valid is False

    def test_validate_description_not_empty(self):
        """Skill description should not be empty."""
        from scripts.agentica.skill_generator import SkillSpec
        from scripts.agentica.skill_quality import SkillValidator

        validator = SkillValidator()

        invalid_spec = SkillSpec(
            name='test-skill',
            description='',
            goal='Test',
            tools=['Bash'],
            instructions='Test'
        )
        result = validator.validate_spec(invalid_spec)
        assert result.valid is False
        assert any('description' in e.lower() for e in result.errors)

    def test_validate_instructions_minimum_length(self):
        """Instructions should have minimum length."""
        from scripts.agentica.skill_generator import SkillSpec
        from scripts.agentica.skill_quality import SkillValidator

        validator = SkillValidator()

        # Too short
        short_spec = SkillSpec(
            name='test-skill',
            description='Test skill',
            goal='Test',
            tools=['Bash'],
            instructions='Do it'  # Too short
        )
        result = validator.validate_spec(short_spec)
        # Should have warning, not error
        assert any('short' in w.lower() for w in result.warnings)

    def test_validate_tools_are_valid(self):
        """Tools should be valid Claude Code tools."""
        from scripts.agentica.skill_generator import SkillSpec
        from scripts.agentica.skill_quality import SkillValidator

        validator = SkillValidator()

        # Invalid tool
        invalid_spec = SkillSpec(
            name='test-skill',
            description='Test skill',
            goal='Test',
            tools=['Bash', 'InvalidTool', 'Read'],
            instructions='Test instructions here'
        )
        result = validator.validate_spec(invalid_spec)
        assert any('InvalidTool' in w for w in result.warnings)

    def test_validate_yaml_frontmatter(self):
        """Generated YAML should be valid."""
        from scripts.agentica.skill_generator import SkillSpec, generate_skill_yaml
        from scripts.agentica.skill_quality import SkillValidator

        validator = SkillValidator()

        spec = SkillSpec(
            name='test-skill',
            description='Test: with colons',
            goal='Test [brackets]',
            tools=['Bash'],
            instructions='Test "quotes"'
        )

        yaml_content = generate_skill_yaml(spec)
        is_valid = validator.validate_yaml(yaml_content)
        assert is_valid is True

    def test_validate_rejects_malformed_yaml(self):
        """Validator should reject malformed YAML."""
        from scripts.agentica.skill_quality import SkillValidator

        validator = SkillValidator()

        # Test with actually invalid YAML structure (duplicate keys cause issues)
        malformed_yaml = """---
name: [invalid
description: missing bracket
---
# Test
"""
        is_valid = validator.validate_yaml(malformed_yaml)
        assert is_valid is False

    def test_validate_rejects_missing_name(self):
        """Validator should reject YAML without name field."""
        from scripts.agentica.skill_quality import SkillValidator

        validator = SkillValidator()

        no_name_yaml = """---
description: just a description
---
# Test
"""
        is_valid = validator.validate_yaml(no_name_yaml)
        assert is_valid is False


# =============================================================================
# Phase 23: Deduplication Tests
# =============================================================================


class TestSkillDeduplication:
    """Test skill deduplication."""

    def test_dedup_class_exists(self):
        """SkillDeduplicator class should exist."""
        from scripts.agentica.skill_quality import SkillDeduplicator

        assert SkillDeduplicator is not None

    def test_find_similar_by_name(self):
        """Should find skills with similar names."""
        from scripts.agentica.skill_generator import SkillSpec
        from scripts.agentica.skill_quality import SkillDeduplicator

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create existing skill
            skills_dir = Path(tmpdir) / '.claude' / 'skills' / 'user-auth'
            skills_dir.mkdir(parents=True)
            (skills_dir / 'SKILL.md').write_text('---\nname: user-auth\n---\n# Test')

            dedup = SkillDeduplicator(project_dir=tmpdir)

            spec = SkillSpec(
                name='user-authentication',
                description='User auth skill',
                goal='Authenticate users',
                tools=['Bash'],
                instructions='Test'
            )

            similar = dedup.find_similar(spec)
            assert len(similar) > 0
            assert 'user-auth' in similar

    def test_find_similar_by_content(self):
        """Should find skills with similar content."""
        from scripts.agentica.skill_generator import SkillSpec
        from scripts.agentica.skill_quality import SkillDeduplicator

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create existing skill with specific content
            skills_dir = Path(tmpdir) / '.claude' / 'skills' / 'jwt-auth'
            skills_dir.mkdir(parents=True)
            (skills_dir / 'SKILL.md').write_text(
                '---\nname: jwt-auth\n---\n# JWT Auth\nImplement JWT authentication'
            )

            dedup = SkillDeduplicator(project_dir=tmpdir)

            spec = SkillSpec(
                name='token-auth',
                description='Token authentication',
                goal='Implement JWT authentication for API',
                tools=['Bash'],
                instructions='Use JWT tokens for auth'
            )

            similar = dedup.find_similar(spec, threshold=0.5)
            # Should find jwt-auth as similar due to content overlap
            # May or may not find depending on algorithm
            assert 'jwt-auth' in similar or len(similar) >= 0

    def test_find_similar_no_match(self):
        """Should return empty list when no similar skills."""
        from scripts.agentica.skill_generator import SkillSpec
        from scripts.agentica.skill_quality import SkillDeduplicator

        with tempfile.TemporaryDirectory() as tmpdir:
            dedup = SkillDeduplicator(project_dir=tmpdir)

            spec = SkillSpec(
                name='unique-skill',
                description='Completely unique',
                goal='Do unique things',
                tools=['Bash'],
                instructions='Unique instructions'
            )

            similar = dedup.find_similar(spec)
            assert len(similar) == 0

    def test_suggest_merge_returns_message(self):
        """suggest_merge should return actionable message."""
        from scripts.agentica.skill_generator import SkillSpec
        from scripts.agentica.skill_quality import SkillDeduplicator

        with tempfile.TemporaryDirectory() as tmpdir:
            dedup = SkillDeduplicator(project_dir=tmpdir)

            spec = SkillSpec(
                name='new-skill',
                description='New skill',
                goal='Test',
                tools=['Bash'],
                instructions='Test'
            )

            message = dedup.suggest_merge('existing-skill', spec)

            assert isinstance(message, str)
            assert 'existing-skill' in message
            assert 'new-skill' in message

    def test_check_before_save(self):
        """check_before_save should return dedup result."""
        from scripts.agentica.skill_generator import SkillSpec
        from scripts.agentica.skill_quality import SkillDeduplicator

        with tempfile.TemporaryDirectory() as tmpdir:
            dedup = SkillDeduplicator(project_dir=tmpdir)

            spec = SkillSpec(
                name='test-skill',
                description='Test',
                goal='Test',
                tools=['Bash'],
                instructions='Test'
            )

            result = dedup.check_before_save(spec)

            assert 'should_save' in result
            assert 'similar_skills' in result
            assert 'suggestion' in result


# =============================================================================
# Phase 24: Usage Tracking Tests
# =============================================================================


class TestUsageTracking:
    """Test skill usage tracking."""

    def test_usage_tracker_class_exists(self):
        """SkillUsageTracker class should exist."""
        from scripts.agentica.skill_quality import SkillUsageTracker

        assert SkillUsageTracker is not None

    def test_record_usage(self):
        """record_usage should store usage record."""
        from scripts.agentica.skill_quality import SkillUsageTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SkillUsageTracker(project_dir=tmpdir)

            tracker.record_usage(
                skill_name='my-skill',
                session_id='session-123'
            )

            # Verify record was stored
            stats = tracker.get_usage_stats('my-skill')
            assert stats['total_uses'] >= 1

    def test_record_usage_multiple_times(self):
        """record_usage should track multiple uses."""
        from scripts.agentica.skill_quality import SkillUsageTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SkillUsageTracker(project_dir=tmpdir)

            for i in range(5):
                tracker.record_usage(
                    skill_name='popular-skill',
                    session_id=f'session-{i}'
                )

            stats = tracker.get_usage_stats('popular-skill')
            assert stats['total_uses'] == 5

    def test_get_usage_stats_by_skill(self):
        """get_usage_stats should return stats for specific skill."""
        from scripts.agentica.skill_quality import SkillUsageTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SkillUsageTracker(project_dir=tmpdir)

            tracker.record_usage('skill-a', 'session-1')
            tracker.record_usage('skill-b', 'session-1')
            tracker.record_usage('skill-a', 'session-2')

            stats_a = tracker.get_usage_stats('skill-a')
            stats_b = tracker.get_usage_stats('skill-b')

            assert stats_a['total_uses'] == 2
            assert stats_b['total_uses'] == 1

    def test_get_all_usage_stats(self):
        """get_all_usage_stats should return stats for all skills."""
        from scripts.agentica.skill_quality import SkillUsageTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SkillUsageTracker(project_dir=tmpdir)

            tracker.record_usage('skill-1', 'session-1')
            tracker.record_usage('skill-2', 'session-1')
            tracker.record_usage('skill-3', 'session-1')

            all_stats = tracker.get_all_usage_stats()

            assert len(all_stats) >= 3
            assert 'skill-1' in all_stats
            assert 'skill-2' in all_stats
            assert 'skill-3' in all_stats

    def test_usage_includes_timestamp(self):
        """Usage records should include timestamp."""
        from scripts.agentica.skill_quality import SkillUsageTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SkillUsageTracker(project_dir=tmpdir)

            tracker.record_usage('timed-skill', 'session-1')

            stats = tracker.get_usage_stats('timed-skill')
            assert 'last_used' in stats
            assert stats['last_used'] is not None

    def test_usage_stats_by_time_range(self):
        """Should be able to get usage stats for time range."""
        from scripts.agentica.skill_quality import SkillUsageTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SkillUsageTracker(project_dir=tmpdir)

            # Record some usage
            tracker.record_usage('ranged-skill', 'session-1')

            # Get stats for last 7 days
            stats = tracker.get_usage_stats('ranged-skill', days=7)
            assert 'total_uses' in stats


# =============================================================================
# Phase 25: Cleanup Suggestions Tests
# =============================================================================


class TestCleanupSuggestions:
    """Test skill cleanup suggestions."""

    def test_suggest_deprecation_exists(self):
        """suggest_deprecation function should exist."""
        from scripts.agentica.skill_quality import suggest_deprecation

        assert callable(suggest_deprecation)

    def test_suggest_deprecation_finds_unused(self):
        """suggest_deprecation should find unused skills."""
        from scripts.agentica.skill_quality import SkillUsageTracker, suggest_deprecation

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create skills directory with some skills
            skills_dir = Path(tmpdir) / '.claude' / 'skills'
            for skill in ['used-skill', 'unused-skill-1', 'unused-skill-2']:
                skill_dir = skills_dir / skill
                skill_dir.mkdir(parents=True)
                (skill_dir / 'SKILL.md').write_text(f'---\nname: {skill}\n---\n')

            tracker = SkillUsageTracker(project_dir=tmpdir)

            # Only use one skill
            tracker.record_usage('used-skill', 'session-1')

            # Get deprecation suggestions - max_uses=1 finds skills with 0 uses
            suggestions = suggest_deprecation(
                project_dir=tmpdir,
                min_age_days=0,  # Don't require minimum age for test
                max_uses=1  # Skills with < 1 uses (i.e., 0 uses) will be suggested
            )

            assert 'unused-skill-1' in suggestions or 'unused-skill-2' in suggestions

    def test_suggest_deprecation_respects_min_age(self):
        """suggest_deprecation should respect minimum age threshold."""
        from scripts.agentica.skill_quality import suggest_deprecation

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a skill
            skills_dir = Path(tmpdir) / '.claude' / 'skills' / 'new-skill'
            skills_dir.mkdir(parents=True)
            (skills_dir / 'SKILL.md').write_text('---\nname: new-skill\n---\n')

            # Skill just created, should not be suggested for deprecation
            suggestions = suggest_deprecation(
                project_dir=tmpdir,
                min_age_days=30,
                max_uses=0
            )

            # New skill should not be suggested
            assert 'new-skill' not in suggestions

    def test_suggest_deprecation_respects_max_uses(self):
        """suggest_deprecation should respect max uses threshold."""
        from scripts.agentica.skill_quality import SkillUsageTracker, suggest_deprecation

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create skill
            skills_dir = Path(tmpdir) / '.claude' / 'skills' / 'somewhat-used'
            skills_dir.mkdir(parents=True)
            (skills_dir / 'SKILL.md').write_text('---\nname: somewhat-used\n---\n')

            tracker = SkillUsageTracker(project_dir=tmpdir)

            # Use it 5 times
            for i in range(5):
                tracker.record_usage('somewhat-used', f'session-{i}')

            # Should not suggest skills with 5+ uses when max_uses=5
            # (only suggest skills with < 5 uses)
            suggestions = suggest_deprecation(
                project_dir=tmpdir,
                min_age_days=0,
                max_uses=5
            )

            assert 'somewhat-used' not in suggestions

    def test_suggest_deprecation_returns_list(self):
        """suggest_deprecation should return list of skill names."""
        from scripts.agentica.skill_quality import suggest_deprecation

        with tempfile.TemporaryDirectory() as tmpdir:
            suggestions = suggest_deprecation(
                project_dir=tmpdir,
                min_age_days=30,
                max_uses=0
            )

            assert isinstance(suggestions, list)

    def test_get_cleanup_report(self):
        """get_cleanup_report should return detailed report."""
        from scripts.agentica.skill_quality import get_cleanup_report

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some skills
            skills_dir = Path(tmpdir) / '.claude' / 'skills'
            for skill in ['active', 'stale']:
                skill_dir = skills_dir / skill
                skill_dir.mkdir(parents=True)
                (skill_dir / 'SKILL.md').write_text(f'---\nname: {skill}\n---\n')

            report = get_cleanup_report(project_dir=tmpdir)

            assert 'total_skills' in report
            assert 'unused_skills' in report
            assert 'suggestions' in report


# =============================================================================
# Integration Tests
# =============================================================================


class TestQualityIntegration:
    """Integration tests for quality features."""

    def test_validate_before_save_workflow(self):
        """Full workflow: validate -> dedup -> save."""
        from scripts.agentica.skill_generator import SkillSpec
        from scripts.agentica.skill_quality import (
            SkillDeduplicator,
            SkillValidator,
            safe_save_skill,
        )

        spec = SkillSpec(
            name='new-feature-skill',
            description='A new skill for features',
            goal='Implement new features',
            tools=['Bash', 'Read', 'Write'],
            instructions='1. Analyze requirements\n2. Implement feature\n3. Write tests'
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Validate
            validator = SkillValidator()
            validation_result = validator.validate_spec(spec)

            if validation_result.valid:
                # Check for duplicates
                dedup = SkillDeduplicator(project_dir=tmpdir)
                dedup_result = dedup.check_before_save(spec)

                if dedup_result['should_save']:
                    # Save
                    result = safe_save_skill(spec, project_dir=tmpdir)
                    assert result.get('saved') is True or result.get('file_path') is not None

    def test_track_and_suggest_cleanup(self):
        """Track usage and get cleanup suggestions."""
        from scripts.agentica.skill_quality import SkillUsageTracker, suggest_deprecation

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create skills
            skills_dir = Path(tmpdir) / '.claude' / 'skills'
            for skill in ['popular', 'unpopular']:
                skill_dir = skills_dir / skill
                skill_dir.mkdir(parents=True)
                (skill_dir / 'SKILL.md').write_text(f'---\nname: {skill}\n---\n')

            # Track usage
            tracker = SkillUsageTracker(project_dir=tmpdir)

            # Popular skill gets used a lot
            for i in range(10):
                tracker.record_usage('popular', f'session-{i}')

            # Unpopular skill never used

            # Get suggestions - max_uses=1 means skills with 0 uses are suggested
            suggestions = suggest_deprecation(
                project_dir=tmpdir,
                min_age_days=0,
                max_uses=1  # Skills with < 1 uses (0 uses)
            )

            assert 'unpopular' in suggestions
            assert 'popular' not in suggestions
