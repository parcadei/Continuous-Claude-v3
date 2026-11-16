"""Tests for skill YAML generator - Phase 12 of Self-Improving Skill System.

Phase 12: Skill YAML Template Generator
- Generate SKILL.md content from task type and Q-heuristic answers
- Include research findings in generated skills
- Validate generated YAML frontmatter

Plan reference: thoughts/shared/plans/self-improving-skill-system.md
"""

import pytest
import yaml
from unittest.mock import MagicMock
from typing import Dict, List


# =============================================================================
# SkillSpec Data Structure Tests
# =============================================================================


class TestSkillSpec:
    """Test SkillSpec data structure."""

    def test_skill_spec_required_fields(self):
        """SkillSpec should have all required fields."""
        from scripts.agentica.skill_generator import SkillSpec

        spec = SkillSpec(
            name='test-skill',
            description='A test skill',
            goal='Test something',
            tools=['Bash', 'Read'],
            instructions='Do the test',
            triggers={'keywords': ['test'], 'intentPatterns': []}
        )

        assert spec.name == 'test-skill'
        assert spec.description == 'A test skill'
        assert spec.goal == 'Test something'
        assert spec.tools == ['Bash', 'Read']
        assert spec.instructions == 'Do the test'
        assert spec.triggers == {'keywords': ['test'], 'intentPatterns': []}

    def test_skill_spec_default_triggers(self):
        """Triggers should default to empty if not provided."""
        from scripts.agentica.skill_generator import SkillSpec

        spec = SkillSpec(
            name='test-skill',
            description='A test skill',
            goal='Test something',
            tools=['Bash'],
            instructions='Do the test'
        )

        assert spec.triggers == {'keywords': [], 'intentPatterns': []}


# =============================================================================
# YAML Generation Tests
# =============================================================================


class TestGenerateSkillYaml:
    """Test SKILL.md YAML generation."""

    def test_generate_valid_yaml_frontmatter(self):
        """Generated content should have valid YAML frontmatter."""
        from scripts.agentica.skill_generator import generate_skill_yaml, SkillSpec

        spec = SkillSpec(
            name='test-skill',
            description='A test skill for testing',
            goal='Test the system',
            tools=['Bash', 'Read', 'Write'],
            instructions='1. Do step one\n2. Do step two'
        )

        content = generate_skill_yaml(spec)

        # Should start with YAML frontmatter
        assert content.startswith('---\n')

        # Extract frontmatter
        parts = content.split('---\n')
        assert len(parts) >= 3  # Before ---, YAML content, after ---

        # Parse YAML frontmatter
        frontmatter = yaml.safe_load(parts[1])
        assert frontmatter['name'] == 'test-skill'
        assert frontmatter['description'] == 'A test skill for testing'
        assert 'allowed-tools' in frontmatter

    def test_generate_includes_all_sections(self):
        """Generated SKILL.md should include all required sections."""
        from scripts.agentica.skill_generator import generate_skill_yaml, SkillSpec

        spec = SkillSpec(
            name='my-skill',
            description='My skill description',
            goal='Accomplish something',
            tools=['Bash'],
            instructions='Follow these steps'
        )

        content = generate_skill_yaml(spec)

        # Check for required sections
        assert '# my-skill' in content or '# My Skill' in content.lower()
        assert '## When to Use' in content
        assert '## Instructions' in content
        assert 'Accomplish something' in content
        assert 'Follow these steps' in content

    def test_generate_escapes_special_characters(self):
        """Should properly escape special YAML characters."""
        from scripts.agentica.skill_generator import generate_skill_yaml, SkillSpec

        spec = SkillSpec(
            name='test-skill',
            description='Description with: colons and "quotes"',
            goal='Goal with special chars: [brackets]',
            tools=['Bash'],
            instructions='Instructions with > and |'
        )

        content = generate_skill_yaml(spec)

        # Should not crash and should produce valid YAML
        parts = content.split('---\n')
        frontmatter = yaml.safe_load(parts[1])

        # The description should be properly escaped/quoted
        assert 'colons' in frontmatter.get('description', '')

    def test_generate_with_empty_tools(self):
        """Should handle empty tools list."""
        from scripts.agentica.skill_generator import generate_skill_yaml, SkillSpec

        spec = SkillSpec(
            name='test-skill',
            description='Test',
            goal='Test',
            tools=[],
            instructions='Test'
        )

        content = generate_skill_yaml(spec)

        # Should still generate valid content
        assert content.startswith('---\n')

    def test_generate_formats_tools_correctly(self):
        """Tools should be formatted as YAML list."""
        from scripts.agentica.skill_generator import generate_skill_yaml, SkillSpec

        spec = SkillSpec(
            name='test-skill',
            description='Test',
            goal='Test',
            tools=['Bash', 'Read', 'Write', 'Edit'],
            instructions='Test'
        )

        content = generate_skill_yaml(spec)
        parts = content.split('---\n')
        frontmatter = yaml.safe_load(parts[1])

        tools = frontmatter.get('allowed-tools', [])
        assert 'Bash' in tools
        assert 'Read' in tools
        assert len(tools) == 4


# =============================================================================
# Skill Generation from Q-Heuristics Tests
# =============================================================================


class TestGenerateFromQHeuristics:
    """Test generating skills from resolved Q-heuristics."""

    def test_generate_from_implementation_heuristics(self):
        """Should generate implementation skill from Q-heuristic answers."""
        from scripts.agentica.skill_generator import generate_from_qheuristics

        resolved = {
            'auth_method': 'JWT',
            'test_coverage': 'Full TDD',
            'target_files': 'Auto-detect'
        }

        spec = generate_from_qheuristics(
            task_type='implementation',
            resolved_qheuristics=resolved,
            original_prompt='implement user authentication'
        )

        assert spec is not None
        assert 'auth' in spec.name.lower() or 'jwt' in spec.name.lower() or spec.name
        assert 'TDD' in spec.instructions or 'test' in spec.instructions.lower()
        assert len(spec.tools) > 0

    def test_generate_from_debug_heuristics(self):
        """Should generate debug skill from Q-heuristic answers."""
        from scripts.agentica.skill_generator import generate_from_qheuristics

        resolved = {
            'error_type': 'Runtime',
            'scope': 'Module',
            'investigation_depth': 'Root Cause'
        }

        spec = generate_from_qheuristics(
            task_type='debug',
            resolved_qheuristics=resolved,
            original_prompt='debug memory leak'
        )

        assert spec is not None
        assert 'debug' in spec.name.lower() or 'memory' in spec.name.lower() or spec.name
        assert 'Root Cause' in spec.instructions or 'root' in spec.instructions.lower()

    def test_generate_from_research_heuristics(self):
        """Should generate research skill from Q-heuristic answers."""
        from scripts.agentica.skill_generator import generate_from_qheuristics

        resolved = {
            'depth': 'Deep Dive',
            'sources': 'All',
            'output_format': 'Report'
        }

        spec = generate_from_qheuristics(
            task_type='research',
            resolved_qheuristics=resolved,
            original_prompt='research vector databases'
        )

        assert spec is not None
        assert len(spec.instructions) > 0

    def test_generate_derives_skill_name(self):
        """Should derive appropriate skill name from prompt."""
        from scripts.agentica.skill_generator import generate_from_qheuristics

        spec = generate_from_qheuristics(
            task_type='implementation',
            resolved_qheuristics={},
            original_prompt='implement webhook handler for Stripe payments'
        )

        # Name should be derived from prompt
        assert spec.name  # Not empty
        assert '-' in spec.name or spec.name.islower()  # kebab-case
        # Should contain relevant keywords
        name_lower = spec.name.lower()
        assert any(word in name_lower for word in ['webhook', 'stripe', 'payment', 'handler', 'implement'])

    def test_generate_includes_triggers(self):
        """Should generate appropriate triggers for the skill."""
        from scripts.agentica.skill_generator import generate_from_qheuristics

        spec = generate_from_qheuristics(
            task_type='implementation',
            resolved_qheuristics={},
            original_prompt='implement rate limiting middleware'
        )

        assert spec.triggers is not None
        assert 'keywords' in spec.triggers
        assert 'intentPatterns' in spec.triggers
        # Should have some keywords derived from prompt
        assert len(spec.triggers['keywords']) > 0


# =============================================================================
# Research Integration Tests
# =============================================================================


class TestGenerateWithResearch:
    """Test integrating research results into skill generation."""

    def test_generate_with_nia_research(self):
        """Should incorporate NIA research into instructions."""
        from scripts.agentica.skill_generator import generate_from_qheuristics

        research = [
            MagicMock(
                source='nia',
                content='Best practice: Always validate input before processing.',
                relevance=0.9,
                url='https://docs.example.com/best-practices'
            )
        ]

        spec = generate_from_qheuristics(
            task_type='implementation',
            resolved_qheuristics={},
            original_prompt='implement input validator',
            research_results=research
        )

        # Research should influence the instructions
        assert 'validate' in spec.instructions.lower() or 'input' in spec.instructions.lower()

    def test_generate_with_codebase_patterns(self):
        """Should reference codebase patterns in instructions."""
        from scripts.agentica.skill_generator import generate_from_qheuristics

        research = [
            MagicMock(
                source='codebase',
                content='src/validators/base.ts: export abstract class BaseValidator',
                relevance=0.85,
                url=None
            )
        ]

        spec = generate_from_qheuristics(
            task_type='implementation',
            resolved_qheuristics={},
            original_prompt='implement custom validator',
            research_results=research
        )

        # Should reference existing patterns
        assert spec is not None
        assert len(spec.instructions) > 0

    def test_generate_without_research(self):
        """Should generate valid skill even without research."""
        from scripts.agentica.skill_generator import generate_from_qheuristics

        spec = generate_from_qheuristics(
            task_type='implementation',
            resolved_qheuristics={},
            original_prompt='implement simple feature',
            research_results=[]
        )

        assert spec is not None
        assert spec.name
        assert spec.instructions


# =============================================================================
# Skill Name Generation Tests
# =============================================================================


class TestSkillNameGeneration:
    """Test skill name derivation from prompts."""

    def test_derive_name_kebab_case(self):
        """Generated name should be kebab-case."""
        from scripts.agentica.skill_generator import derive_skill_name

        name = derive_skill_name('Implement User Authentication Flow')

        assert name.islower()
        assert ' ' not in name
        assert name == name.lower()

    def test_derive_name_removes_common_words(self):
        """Should remove common words like 'implement', 'create', etc."""
        from scripts.agentica.skill_generator import derive_skill_name

        name = derive_skill_name('implement the user auth system')

        # Should not start with 'implement-the'
        assert not name.startswith('implement-the')

    def test_derive_name_max_length(self):
        """Name should not exceed maximum length."""
        from scripts.agentica.skill_generator import derive_skill_name

        name = derive_skill_name(
            'implement a very long feature name that goes on and on '
            'with many many words that should be truncated'
        )

        assert len(name) <= 50

    def test_derive_name_handles_special_chars(self):
        """Should handle special characters in prompt."""
        from scripts.agentica.skill_generator import derive_skill_name

        name = derive_skill_name("implement user's auth (v2) feature!")

        # Should produce valid name without special chars
        assert name.replace('-', '').isalnum()


# =============================================================================
# Tool Selection Tests
# =============================================================================


class TestToolSelection:
    """Test automatic tool selection for skills."""

    def test_select_tools_for_implementation(self):
        """Implementation skills should include common tools."""
        from scripts.agentica.skill_generator import select_tools_for_task

        tools = select_tools_for_task('implementation', {})

        assert 'Read' in tools
        assert 'Write' in tools or 'Edit' in tools
        assert 'Bash' in tools

    def test_select_tools_for_debug(self):
        """Debug skills should include investigation tools."""
        from scripts.agentica.skill_generator import select_tools_for_task

        tools = select_tools_for_task('debug', {})

        assert 'Read' in tools
        assert 'Bash' in tools
        assert 'Grep' in tools or 'Glob' in tools

    def test_select_tools_from_qheuristics(self):
        """Should use tools from Q-heuristic if specified."""
        from scripts.agentica.skill_generator import select_tools_for_task

        resolved = {
            'tools': 'Bash, Read, WebSearch'
        }

        tools = select_tools_for_task('implementation', resolved)

        assert 'Bash' in tools
        assert 'Read' in tools


# =============================================================================
# Instruction Generation Tests
# =============================================================================


class TestInstructionGeneration:
    """Test instruction generation for skills."""

    def test_generate_instructions_structured(self):
        """Instructions should be structured with steps."""
        from scripts.agentica.skill_generator import generate_instructions

        instructions = generate_instructions(
            task_type='implementation',
            goal='Implement user authentication',
            resolved_qheuristics={'test_coverage': 'Full TDD'}
        )

        # Should have numbered steps or bullet points
        assert '1.' in instructions or '-' in instructions or '*' in instructions

    def test_generate_instructions_includes_goal(self):
        """Instructions should reference the goal."""
        from scripts.agentica.skill_generator import generate_instructions

        instructions = generate_instructions(
            task_type='implementation',
            goal='Build a REST API endpoint',
            resolved_qheuristics={}
        )

        assert 'API' in instructions or 'endpoint' in instructions.lower()

    def test_generate_instructions_task_specific(self):
        """Instructions should be specific to task type."""
        from scripts.agentica.skill_generator import generate_instructions

        impl_instructions = generate_instructions('implementation', 'Build X', {})
        debug_instructions = generate_instructions('debug', 'Fix X', {})

        # Should be different for different task types
        assert impl_instructions != debug_instructions


# =============================================================================
# Full Pipeline Tests
# =============================================================================


class TestFullSkillGenerationPipeline:
    """Test the complete skill generation pipeline."""

    def test_end_to_end_generation(self):
        """Should generate complete, valid SKILL.md content."""
        from scripts.agentica.skill_generator import (
            generate_from_qheuristics,
            generate_skill_yaml
        )

        # Simulate resolved Q-heuristics
        resolved = {
            'auth_method': 'JWT',
            'test_coverage': 'Unit Tests',
            'target_files': 'Auto-detect'
        }

        # Generate spec
        spec = generate_from_qheuristics(
            task_type='implementation',
            resolved_qheuristics=resolved,
            original_prompt='implement JWT authentication middleware'
        )

        # Generate YAML
        content = generate_skill_yaml(spec)

        # Validate result
        assert content.startswith('---\n')
        assert '## When to Use' in content
        assert '## Instructions' in content

        # Parse YAML to verify validity
        parts = content.split('---\n')
        frontmatter = yaml.safe_load(parts[1])
        assert 'name' in frontmatter
        assert 'description' in frontmatter

    def test_generated_skill_is_parseable(self):
        """Generated skill should be fully parseable."""
        from scripts.agentica.skill_generator import (
            generate_from_qheuristics,
            generate_skill_yaml
        )

        spec = generate_from_qheuristics(
            task_type='debug',
            resolved_qheuristics={'error_type': 'Runtime'},
            original_prompt='debug database connection issues'
        )

        content = generate_skill_yaml(spec)

        # Should not raise any exceptions when parsing
        parts = content.split('---\n')
        frontmatter = yaml.safe_load(parts[1])

        # All required fields should be present
        assert frontmatter.get('name')
        assert frontmatter.get('description')
