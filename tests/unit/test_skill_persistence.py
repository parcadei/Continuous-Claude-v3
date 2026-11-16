"""Tests for skill persistence - Phases 13-15 of Self-Improving Skill System.

Phase 13: Memory Storage - Save generated skills to memory for retrieval
Phase 14: Filesystem Storage - Write SKILL.md to .claude/skills/
Phase 15: Trigger Registration - Add skill to skill-rules.json

Plan reference: thoughts/shared/plans/self-improving-skill-system.md
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# SkillPersistence Interface Tests (Phase 13)
# =============================================================================


class TestSkillPersistenceInterface:
    """Test the SkillPersistence class interface."""

    def test_skill_persistence_class_exists(self):
        """SkillPersistence class should exist."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        assert SkillPersistence is not None

    def test_skill_persistence_has_save_to_memory(self):
        """SkillPersistence should have save_to_memory method."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        persistence = SkillPersistence(project_dir='/tmp/test')
        assert hasattr(persistence, 'save_to_memory')
        assert callable(persistence.save_to_memory)

    def test_skill_persistence_has_save_to_filesystem(self):
        """SkillPersistence should have save_to_filesystem method."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        persistence = SkillPersistence(project_dir='/tmp/test')
        assert hasattr(persistence, 'save_to_filesystem')
        assert callable(persistence.save_to_filesystem)

    def test_skill_persistence_has_exists(self):
        """SkillPersistence should have exists method."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        persistence = SkillPersistence(project_dir='/tmp/test')
        assert hasattr(persistence, 'exists')
        assert callable(persistence.exists)

    def test_skill_persistence_has_register_triggers(self):
        """SkillPersistence should have register_triggers method."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        persistence = SkillPersistence(project_dir='/tmp/test')
        assert hasattr(persistence, 'register_triggers')
        assert callable(persistence.register_triggers)


# =============================================================================
# Memory Storage Tests (Phase 13)
# =============================================================================


class TestSaveToMemory:
    """Test saving skills to memory."""

    @pytest.fixture
    def skill_spec(self):
        """Create a test SkillSpec."""
        from scripts.agentica_patterns.skill_generator import SkillSpec

        return SkillSpec(
            name='test-skill',
            description='A test skill for testing',
            goal='Test the system',
            tools=['Bash', 'Read'],
            instructions='1. Do step one\n2. Do step two',
            triggers={'keywords': ['test'], 'intentPatterns': ['test.*pattern']}
        )

    @pytest.mark.asyncio
    async def test_save_to_memory_returns_memory_id(self, skill_spec):
        """save_to_memory should return a memory ID on success."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            # Mock the memory client
            with patch.object(persistence, '_memory_client') as mock_client:
                mock_client.store.return_value = 'mem_12345'

                memory_id = await persistence.save_to_memory(skill_spec)

                assert memory_id is not None
                assert isinstance(memory_id, str)
                assert len(memory_id) > 0

    @pytest.mark.asyncio
    async def test_save_to_memory_stores_skill_content(self, skill_spec):
        """save_to_memory should store the skill YAML content."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            with patch.object(persistence, '_memory_client') as mock_client:
                mock_client.store.return_value = 'mem_12345'

                await persistence.save_to_memory(skill_spec)

                # Verify store was called with skill content
                mock_client.store.assert_called_once()
                call_args = mock_client.store.call_args
                stored_content = call_args[0][0]

                # Should contain skill YAML
                assert 'test-skill' in stored_content
                assert 'A test skill for testing' in stored_content

    @pytest.mark.asyncio
    async def test_save_to_memory_includes_metadata(self, skill_spec):
        """save_to_memory should include proper metadata."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            with patch.object(persistence, '_memory_client') as mock_client:
                mock_client.store.return_value = 'mem_12345'

                await persistence.save_to_memory(skill_spec)

                call_args = mock_client.store.call_args
                fallback = call_args[0][1] if len(call_args[0]) > 1 else {}
                metadata = call_args[1].get('metadata', fallback)

                # Should have skill-specific metadata
                assert 'type' in metadata
                assert metadata['type'] == 'skill'
                assert 'name' in metadata
                assert metadata['name'] == 'test-skill'

    @pytest.mark.asyncio
    async def test_save_to_memory_handles_failure_gracefully(self, skill_spec):
        """save_to_memory should return None on failure."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            with patch.object(persistence, '_memory_client') as mock_client:
                mock_client.store.return_value = None  # Simulates failure

                memory_id = await persistence.save_to_memory(skill_spec)

                # Should return None, not crash
                assert memory_id is None


# =============================================================================
# Filesystem Storage Tests (Phase 14)
# =============================================================================


class TestSaveToFilesystem:
    """Test saving skills to filesystem."""

    @pytest.fixture
    def skill_spec(self):
        """Create a test SkillSpec."""
        from scripts.agentica_patterns.skill_generator import SkillSpec

        return SkillSpec(
            name='test-skill',
            description='A test skill for testing',
            goal='Test the system',
            tools=['Bash', 'Read'],
            instructions='1. Do step one\n2. Do step two',
            triggers={'keywords': ['test'], 'intentPatterns': ['test.*pattern']}
        )

    def test_save_to_filesystem_creates_skill_directory(self, skill_spec):
        """save_to_filesystem should create the skill directory."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            persistence.save_to_filesystem(skill_spec)

            skill_dir = Path(tmpdir) / '.claude' / 'skills' / 'test-skill'
            assert skill_dir.exists()
            assert skill_dir.is_dir()

    def test_save_to_filesystem_writes_skill_md(self, skill_spec):
        """save_to_filesystem should write SKILL.md file."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            persistence.save_to_filesystem(skill_spec)

            skill_file = Path(tmpdir) / '.claude' / 'skills' / 'test-skill' / 'SKILL.md'
            assert skill_file.exists()
            assert skill_file.is_file()

    def test_save_to_filesystem_returns_file_path(self, skill_spec):
        """save_to_filesystem should return the created file path."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            file_path = persistence.save_to_filesystem(skill_spec)

            assert file_path is not None
            assert file_path.endswith('SKILL.md')
            assert Path(file_path).exists()

    def test_save_to_filesystem_writes_valid_content(self, skill_spec):
        """save_to_filesystem should write valid SKILL.md content."""
        import yaml

        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            file_path = persistence.save_to_filesystem(skill_spec)

            with open(file_path) as f:
                content = f.read()

            # Should have YAML frontmatter
            assert content.startswith('---\n')

            # Parse frontmatter
            parts = content.split('---\n')
            frontmatter = yaml.safe_load(parts[1])

            assert frontmatter['name'] == 'test-skill'
            assert frontmatter['description'] == 'A test skill for testing'

    def test_save_to_filesystem_handles_name_collision(self):
        """save_to_filesystem should handle name collisions."""
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            # Create first skill
            skill1 = SkillSpec(
                name='my-skill',
                description='First skill',
                goal='First goal',
                tools=['Bash'],
                instructions='First instructions'
            )
            path1 = persistence.save_to_filesystem(skill1)

            # Create second skill with same name
            skill2 = SkillSpec(
                name='my-skill',
                description='Second skill',
                goal='Second goal',
                tools=['Bash'],
                instructions='Second instructions'
            )
            path2 = persistence.save_to_filesystem(skill2)

            # Both should exist, second with number suffix
            assert Path(path1).exists()
            assert Path(path2).exists()
            assert path1 != path2

            # Second path should have number suffix
            assert 'my-skill-2' in path2 or 'my-skill-1' in path2

    def test_save_to_filesystem_handles_multiple_collisions(self):
        """save_to_filesystem should handle multiple name collisions."""
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            paths = []
            for i in range(5):
                skill = SkillSpec(
                    name='duplicate-skill',
                    description=f'Skill {i}',
                    goal=f'Goal {i}',
                    tools=['Bash'],
                    instructions=f'Instructions {i}'
                )
                path = persistence.save_to_filesystem(skill)
                paths.append(path)

            # All paths should be unique
            assert len(set(paths)) == 5

            # All files should exist
            for path in paths:
                assert Path(path).exists()


# =============================================================================
# Trigger Registration Tests (Phase 15)
# =============================================================================


class TestRegisterTriggers:
    """Test skill trigger registration."""

    @pytest.fixture
    def skill_spec(self):
        """Create a test SkillSpec with triggers."""
        from scripts.agentica_patterns.skill_generator import SkillSpec

        return SkillSpec(
            name='my-new-skill',
            description='A new skill',
            goal='Do something new',
            tools=['Bash', 'Read'],
            instructions='Follow these steps',
            triggers={
                'keywords': ['new', 'skill', 'something'],
                'intentPatterns': ['do.*something.*new']
            }
        )

    def test_register_triggers_creates_skill_rules_if_missing(self, skill_spec):
        """register_triggers should create skill-rules.json if it doesn't exist."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            # Ensure skills directory exists but no skill-rules.json
            skills_dir = Path(tmpdir) / '.claude' / 'skills'
            skills_dir.mkdir(parents=True, exist_ok=True)

            persistence.register_triggers(skill_spec)

            rules_path = skills_dir / 'skill-rules.json'
            assert rules_path.exists()

    def test_register_triggers_adds_skill_entry(self, skill_spec):
        """register_triggers should add the skill to skill-rules.json."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            # Create initial skill-rules.json
            skills_dir = Path(tmpdir) / '.claude' / 'skills'
            skills_dir.mkdir(parents=True, exist_ok=True)
            rules_path = skills_dir / 'skill-rules.json'

            initial_rules = {
                'version': '1.0',
                'skills': {
                    'existing-skill': {
                        'type': 'domain',
                        'enforcement': 'suggest',
                        'priority': 'high',
                        'promptTriggers': {'keywords': ['existing']}
                    }
                }
            }
            with open(rules_path, 'w') as f:
                json.dump(initial_rules, f)

            persistence.register_triggers(skill_spec)

            # Read updated rules
            with open(rules_path) as f:
                updated_rules = json.load(f)

            # Should have both skills
            assert 'existing-skill' in updated_rules['skills']
            assert 'my-new-skill' in updated_rules['skills']

    def test_register_triggers_includes_keywords(self, skill_spec):
        """register_triggers should include skill keywords."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            skills_dir = Path(tmpdir) / '.claude' / 'skills'
            skills_dir.mkdir(parents=True, exist_ok=True)

            persistence.register_triggers(skill_spec)

            rules_path = skills_dir / 'skill-rules.json'
            with open(rules_path) as f:
                rules = json.load(f)

            skill_entry = rules['skills']['my-new-skill']
            assert 'promptTriggers' in skill_entry
            assert 'keywords' in skill_entry['promptTriggers']
            assert 'new' in skill_entry['promptTriggers']['keywords']
            assert 'skill' in skill_entry['promptTriggers']['keywords']

    def test_register_triggers_includes_intent_patterns(self, skill_spec):
        """register_triggers should include intent patterns."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            skills_dir = Path(tmpdir) / '.claude' / 'skills'
            skills_dir.mkdir(parents=True, exist_ok=True)

            persistence.register_triggers(skill_spec)

            rules_path = skills_dir / 'skill-rules.json'
            with open(rules_path) as f:
                rules = json.load(f)

            skill_entry = rules['skills']['my-new-skill']
            assert 'intentPatterns' in skill_entry['promptTriggers']
            assert 'do.*something.*new' in skill_entry['promptTriggers']['intentPatterns']

    def test_register_triggers_sets_default_priority(self, skill_spec):
        """register_triggers should set low priority for JIT skills."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            skills_dir = Path(tmpdir) / '.claude' / 'skills'
            skills_dir.mkdir(parents=True, exist_ok=True)

            persistence.register_triggers(skill_spec)

            rules_path = skills_dir / 'skill-rules.json'
            with open(rules_path) as f:
                rules = json.load(f)

            skill_entry = rules['skills']['my-new-skill']
            # JIT skills should start at low or medium priority
            assert skill_entry.get('priority') in ['low', 'medium']

    def test_register_triggers_preserves_existing_skills(self, skill_spec):
        """register_triggers should not modify existing skill entries."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            skills_dir = Path(tmpdir) / '.claude' / 'skills'
            skills_dir.mkdir(parents=True, exist_ok=True)
            rules_path = skills_dir / 'skill-rules.json'

            initial_rules = {
                'version': '1.0',
                'skills': {
                    'important-skill': {
                        'type': 'domain',
                        'enforcement': 'block',
                        'priority': 'critical',
                        'promptTriggers': {'keywords': ['important']}
                    }
                }
            }
            with open(rules_path, 'w') as f:
                json.dump(initial_rules, f)

            persistence.register_triggers(skill_spec)

            with open(rules_path) as f:
                updated_rules = json.load(f)

            # Existing skill should be unchanged
            existing = updated_rules['skills']['important-skill']
            assert existing['enforcement'] == 'block'
            assert existing['priority'] == 'critical'

    def test_register_triggers_valid_json_output(self, skill_spec):
        """register_triggers should write valid, formatted JSON."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            skills_dir = Path(tmpdir) / '.claude' / 'skills'
            skills_dir.mkdir(parents=True, exist_ok=True)

            persistence.register_triggers(skill_spec)

            rules_path = skills_dir / 'skill-rules.json'

            # Should be valid JSON
            with open(rules_path) as f:
                content = f.read()

            # Should not crash
            json.loads(content)

            # Should be properly indented
            assert '\n' in content
            assert '  ' in content  # Has indentation


# =============================================================================
# Exists Check Tests
# =============================================================================


class TestExists:
    """Test skill existence checking."""

    def test_exists_returns_true_for_existing_skill(self):
        """exists should return True when skill directory exists."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            # Create skill directory
            skill_dir = Path(tmpdir) / '.claude' / 'skills' / 'my-skill'
            skill_dir.mkdir(parents=True)
            (skill_dir / 'SKILL.md').touch()

            assert persistence.exists('my-skill') is True

    def test_exists_returns_false_for_missing_skill(self):
        """exists should return False when skill doesn't exist."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            assert persistence.exists('nonexistent-skill') is False

    def test_exists_returns_false_for_empty_directory(self):
        """exists should return False when skill directory is empty."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            # Create empty skill directory (no SKILL.md)
            skill_dir = Path(tmpdir) / '.claude' / 'skills' / 'my-skill'
            skill_dir.mkdir(parents=True)

            assert persistence.exists('my-skill') is False


# =============================================================================
# Full Persistence Pipeline Tests
# =============================================================================


class TestFullPersistencePipeline:
    """Test the complete skill persistence pipeline."""

    @pytest.fixture
    def skill_spec(self):
        """Create a test SkillSpec."""
        from scripts.agentica_patterns.skill_generator import SkillSpec

        return SkillSpec(
            name='complete-skill',
            description='A complete skill for E2E testing',
            goal='Test the entire persistence pipeline',
            tools=['Bash', 'Read', 'Write'],
            instructions='1. Do this\n2. Then that',
            triggers={
                'keywords': ['complete', 'test', 'e2e'],
                'intentPatterns': ['test.*complete']
            }
        )

    @pytest.mark.asyncio
    async def test_save_skill_full_pipeline(self, skill_spec):
        """Should persist skill to both memory and filesystem."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            # Mock memory client
            with patch.object(persistence, '_memory_client') as mock_client:
                mock_client.store.return_value = 'mem_e2e_123'

                # Save to memory
                memory_id = await persistence.save_to_memory(skill_spec)

                # Save to filesystem
                file_path = persistence.save_to_filesystem(skill_spec)

                # Register triggers
                persistence.register_triggers(skill_spec)

                # Verify all components worked
                assert memory_id == 'mem_e2e_123'
                assert Path(file_path).exists()

                # Check skill-rules.json
                rules_path = Path(tmpdir) / '.claude' / 'skills' / 'skill-rules.json'
                with open(rules_path) as f:
                    rules = json.load(f)

                assert 'complete-skill' in rules['skills']

    def test_save_and_check_exists(self, skill_spec):
        """After saving, exists() should return True."""
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            # Initially doesn't exist
            assert persistence.exists('complete-skill') is False

            # Save skill
            persistence.save_to_filesystem(skill_spec)

            # Now exists
            assert persistence.exists('complete-skill') is True


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_save_skill_function_exists(self):
        """Module should have save_skill convenience function."""
        from scripts.agentica_patterns.skill_persistence import save_skill

        assert callable(save_skill)

    @pytest.mark.asyncio
    async def test_save_skill_saves_to_both_locations(self):
        """save_skill should save to memory and filesystem."""
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import save_skill

        spec = SkillSpec(
            name='convenience-skill',
            description='Test convenience function',
            goal='Test',
            tools=['Bash'],
            instructions='Do it'
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('scripts.agentica_patterns.skill_persistence.SkillPersistence') as mock_cls:
                mock_instance = MagicMock()
                mock_instance.save_to_memory = AsyncMock(return_value='mem_123')
                skill_path = f'{tmpdir}/.claude/skills/convenience-skill/SKILL.md'
                mock_instance.save_to_filesystem.return_value = skill_path
                mock_instance.register_triggers.return_value = None
                mock_cls.return_value = mock_instance

                result = await save_skill(spec, project_dir=tmpdir)

                # Should have called all three methods
                mock_instance.save_to_memory.assert_called_once_with(spec)
                mock_instance.save_to_filesystem.assert_called_once_with(spec)
                mock_instance.register_triggers.assert_called_once_with(spec)

                # Should return result dict
                assert 'memory_id' in result
                assert 'file_path' in result
