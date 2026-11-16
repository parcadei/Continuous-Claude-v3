"""Tests for Math Skills Generator - TDD Phase 1a/1b/2a/2b.

Red Phase: These tests are written BEFORE implementation.
All tests should FAIL initially.

Plan reference: thoughts/shared/plans/2025-12-30-math-skills-generator.md

Phase 1a Tests: CLI interface
Phase 1b Tests: TIER_TOPICS data structure
Phase 2a Tests: Ragie query function
Phase 2b Tests: Chunk extraction helper
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


# =============================================================================
# Phase 1a: CLI Tests
# =============================================================================


class TestCLI:
    """Test command-line interface for generate_math_skills.py."""

    SCRIPT_PATH = Path("scripts/generate_math_skills.py")

    def run_script(self, args: list[str], check: bool = False) -> subprocess.CompletedProcess:
        """Helper to run the script with args."""
        cmd = [sys.executable, str(self.SCRIPT_PATH)] + args
        return subprocess.run(cmd, capture_output=True, text=True, check=check)

    def test_cli_help_displays(self):
        """Script should display help with --help flag."""
        result = self.run_script(["--help"])

        # Should exit successfully
        assert result.returncode == 0, f"Help failed: {result.stderr}"

        # Help should mention key options
        assert "--tier" in result.stdout, "Help should mention --tier option"
        assert "--dry-run" in result.stdout, "Help should mention --dry-run option"
        assert "--category" in result.stdout, "Help should mention --category option"

    def test_cli_requires_tier(self):
        """Script should error without --tier argument."""
        result = self.run_script([])

        # Should fail
        assert result.returncode != 0, "Should fail without --tier"

        # Error should mention tier is required
        assert "tier" in result.stderr.lower() or "required" in result.stderr.lower(), \
            f"Error should mention tier is required: {result.stderr}"

    def test_cli_accepts_valid_tier_1(self):
        """Script should accept --tier 1."""
        result = self.run_script(["--tier", "1", "--dry-run"])

        # Should not fail due to invalid tier
        # (might fail for other reasons, but not tier validation)
        assert "invalid choice" not in result.stderr.lower(), \
            f"Should accept tier 1: {result.stderr}"

    def test_cli_accepts_valid_tier_5(self):
        """Script should accept --tier 5."""
        result = self.run_script(["--tier", "5", "--dry-run"])

        # Should not fail due to invalid tier
        assert "invalid choice" not in result.stderr.lower(), \
            f"Should accept tier 5: {result.stderr}"

    def test_cli_rejects_tier_0(self):
        """Script should reject --tier 0."""
        result = self.run_script(["--tier", "0", "--dry-run"])

        # Should fail with invalid choice
        assert result.returncode != 0, "Should reject tier 0"
        assert "invalid" in result.stderr.lower() or "choice" in result.stderr.lower(), \
            f"Should indicate invalid choice: {result.stderr}"

    def test_cli_rejects_tier_6(self):
        """Script should reject --tier 6."""
        result = self.run_script(["--tier", "6", "--dry-run"])

        # Should fail with invalid choice
        assert result.returncode != 0, "Should reject tier 6"
        assert "invalid" in result.stderr.lower() or "choice" in result.stderr.lower(), \
            f"Should indicate invalid choice: {result.stderr}"

    def test_cli_accepts_dry_run(self):
        """Script should accept --dry-run flag."""
        result = self.run_script(["--tier", "1", "--dry-run"])

        # Should run (may fail for other reasons, but --dry-run should be recognized)
        assert "unrecognized" not in result.stderr.lower(), \
            f"Should accept --dry-run: {result.stderr}"

    def test_cli_accepts_category_filter(self):
        """Script should accept --category option."""
        result = self.run_script(["--tier", "1", "--category", "real-analysis", "--dry-run"])

        # Should run (may fail for other reasons, but --category should be recognized)
        assert "unrecognized" not in result.stderr.lower(), \
            f"Should accept --category: {result.stderr}"


# =============================================================================
# Phase 1b: TIER_TOPICS Data Structure Tests
# =============================================================================


class TestTierTopics:
    """Test TIER_TOPICS data structure in generate_math_skills.py."""

    def test_tier_topics_has_tier_1(self):
        """TIER_TOPICS should have tier 1 defined."""
        from scripts.generate_math_skills import TIER_TOPICS

        assert 1 in TIER_TOPICS, "TIER_TOPICS should have tier 1"

    def test_tier_topics_tier_1_is_dict(self):
        """Tier 1 should be a dict of category -> topics."""
        from scripts.generate_math_skills import TIER_TOPICS

        assert isinstance(TIER_TOPICS[1], dict), "Tier 1 should be a dict"

    def test_tier_1_has_real_analysis(self):
        """Tier 1 should have real-analysis category."""
        from scripts.generate_math_skills import TIER_TOPICS

        assert "real-analysis" in TIER_TOPICS[1], \
            f"Tier 1 should have real-analysis, got: {list(TIER_TOPICS[1].keys())}"

    def test_tier_1_has_linear_algebra(self):
        """Tier 1 should have linear-algebra category."""
        from scripts.generate_math_skills import TIER_TOPICS

        assert "linear-algebra" in TIER_TOPICS[1], \
            f"Tier 1 should have linear-algebra, got: {list(TIER_TOPICS[1].keys())}"

    def test_real_analysis_has_limits(self):
        """Real analysis should have 'limits' topic."""
        from scripts.generate_math_skills import TIER_TOPICS

        topics = TIER_TOPICS[1]["real-analysis"]
        assert "limits" in topics, f"Should have limits, got: {topics}"

    def test_real_analysis_has_continuity(self):
        """Real analysis should have 'continuity' topic."""
        from scripts.generate_math_skills import TIER_TOPICS

        topics = TIER_TOPICS[1]["real-analysis"]
        assert "continuity" in topics, f"Should have continuity, got: {topics}"

    def test_real_analysis_has_convergence(self):
        """Real analysis should have 'convergence' topic."""
        from scripts.generate_math_skills import TIER_TOPICS

        topics = TIER_TOPICS[1]["real-analysis"]
        assert "convergence" in topics, f"Should have convergence, got: {topics}"

    def test_linear_algebra_has_matrices(self):
        """Linear algebra should have 'matrices' topic."""
        from scripts.generate_math_skills import TIER_TOPICS

        topics = TIER_TOPICS[1]["linear-algebra"]
        assert "matrices" in topics, f"Should have matrices, got: {topics}"

    def test_linear_algebra_has_eigenvalues(self):
        """Linear algebra should have 'eigenvalues' topic."""
        from scripts.generate_math_skills import TIER_TOPICS

        topics = TIER_TOPICS[1]["linear-algebra"]
        assert "eigenvalues" in topics, f"Should have eigenvalues, got: {topics}"

    def test_linear_algebra_has_vector_spaces(self):
        """Linear algebra should have 'vector-spaces' topic."""
        from scripts.generate_math_skills import TIER_TOPICS

        topics = TIER_TOPICS[1]["linear-algebra"]
        assert "vector-spaces" in topics, f"Should have vector-spaces, got: {topics}"

    def test_tier_1_has_six_topics_total(self):
        """Tier 1 should have exactly 6 topics (3 real-analysis + 3 linear-algebra)."""
        from scripts.generate_math_skills import TIER_TOPICS

        total = 0
        for category, topics in TIER_TOPICS[1].items():
            total += len(topics)

        assert total == 6, f"Tier 1 should have 6 topics total, got {total}"


# =============================================================================
# Phase 2a: Ragie Query Function Tests
# =============================================================================


class TestQueryRagieForTopic:
    """Test query_ragie_for_topic function for Phase 2a."""

    def test_query_ragie_for_topic_returns_list(self, monkeypatch):
        """query_ragie_for_topic should return a list of chunks."""
        from scripts.generate_math_skills import query_ragie_for_topic

        # Mock httpx.post to return a valid response
        mock_response = Mock()
        mock_response.json.return_value = {
            "scored_chunks": [
                {"text": "Limit definition...", "score": 0.95},
                {"text": "Epsilon-delta...", "score": 0.88},
            ]
        }
        mock_response.raise_for_status = Mock()

        monkeypatch.setenv("RAGIE_API_KEY", "test-key")

        with patch("scripts.generate_math_skills.httpx.post", return_value=mock_response):
            result = query_ragie_for_topic("limits", "real-analysis")

        assert isinstance(result, list), f"Should return list, got {type(result)}"
        assert len(result) == 2, f"Should return 2 chunks, got {len(result)}"

    def test_query_ragie_for_topic_calls_correct_endpoint(self, monkeypatch):
        """query_ragie_for_topic should call /retrievals endpoint."""
        from scripts.generate_math_skills import query_ragie_for_topic

        mock_response = Mock()
        mock_response.json.return_value = {"scored_chunks": []}
        mock_response.raise_for_status = Mock()

        monkeypatch.setenv("RAGIE_API_KEY", "test-key")

        with patch("scripts.generate_math_skills.httpx.post", return_value=mock_response) as mock_post:
            query_ragie_for_topic("limits", "real-analysis")

            # Verify correct URL called
            call_args = mock_post.call_args
            assert call_args is not None, "httpx.post should have been called"
            url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url", "")
            assert "retrievals" in url, f"Should call /retrievals endpoint, got: {url}"

    def test_query_ragie_for_topic_uses_partition(self, monkeypatch):
        """query_ragie_for_topic should use partition=math-textbooks."""
        from scripts.generate_math_skills import query_ragie_for_topic

        mock_response = Mock()
        mock_response.json.return_value = {"scored_chunks": []}
        mock_response.raise_for_status = Mock()

        monkeypatch.setenv("RAGIE_API_KEY", "test-key")

        with patch("scripts.generate_math_skills.httpx.post", return_value=mock_response) as mock_post:
            query_ragie_for_topic("limits", "real-analysis")

            # Verify partition in payload
            call_args = mock_post.call_args
            payload = call_args.kwargs.get("json", {})
            assert payload.get("partition") == "math-textbooks", \
                f"Should use partition=math-textbooks, got: {payload.get('partition')}"

    def test_query_ragie_for_topic_uses_rerank(self, monkeypatch):
        """query_ragie_for_topic should use rerank=True."""
        from scripts.generate_math_skills import query_ragie_for_topic

        mock_response = Mock()
        mock_response.json.return_value = {"scored_chunks": []}
        mock_response.raise_for_status = Mock()

        monkeypatch.setenv("RAGIE_API_KEY", "test-key")

        with patch("scripts.generate_math_skills.httpx.post", return_value=mock_response) as mock_post:
            query_ragie_for_topic("limits", "real-analysis")

            # Verify rerank in payload
            call_args = mock_post.call_args
            payload = call_args.kwargs.get("json", {})
            assert payload.get("rerank") is True, \
                f"Should use rerank=True, got: {payload.get('rerank')}"

    def test_query_ragie_for_topic_handles_missing_api_key(self, monkeypatch):
        """query_ragie_for_topic should raise RuntimeError if RAGIE_API_KEY not set."""
        from scripts.generate_math_skills import query_ragie_for_topic

        # Ensure RAGIE_API_KEY is not in environment
        monkeypatch.delenv("RAGIE_API_KEY", raising=False)

        with pytest.raises(RuntimeError) as exc_info:
            query_ragie_for_topic("limits", "real-analysis")

        assert "RAGIE_API_KEY" in str(exc_info.value), \
            f"Error should mention RAGIE_API_KEY, got: {exc_info.value}"

    def test_query_ragie_for_topic_constructs_query(self, monkeypatch):
        """query_ragie_for_topic should construct query including topic and category."""
        from scripts.generate_math_skills import query_ragie_for_topic

        mock_response = Mock()
        mock_response.json.return_value = {"scored_chunks": []}
        mock_response.raise_for_status = Mock()

        monkeypatch.setenv("RAGIE_API_KEY", "test-key")

        with patch("scripts.generate_math_skills.httpx.post", return_value=mock_response) as mock_post:
            query_ragie_for_topic("eigenvalues", "linear-algebra")

            # Verify query includes topic and category
            call_args = mock_post.call_args
            payload = call_args.kwargs.get("json", {})
            query = payload.get("query", "")
            assert "eigenvalues" in query.lower(), \
                f"Query should include topic 'eigenvalues', got: {query}"
            assert "linear" in query.lower() or "algebra" in query.lower(), \
                f"Query should include category 'linear algebra', got: {query}"


# =============================================================================
# Phase 2b: Chunk Extraction Tests
# =============================================================================


class TestExtractTechniquesFromChunks:
    """Test extract_techniques_from_chunks function for Phase 2b."""

    def test_extract_techniques_from_chunks_returns_list(self):
        """extract_techniques_from_chunks should return a list."""
        from scripts.generate_math_skills import extract_techniques_from_chunks

        chunks = [
            {"text": "The epsilon-delta definition of a limit..."},
            {"text": "Apply the squeeze theorem when..."},
        ]

        result = extract_techniques_from_chunks(chunks)

        assert isinstance(result, list), f"Should return list, got {type(result)}"

    def test_extract_techniques_from_chunks_limits_to_five(self):
        """extract_techniques_from_chunks should return at most 5 techniques."""
        from scripts.generate_math_skills import extract_techniques_from_chunks

        # Create 10 chunks
        chunks = [{"text": f"Technique {i} description..."} for i in range(10)]

        result = extract_techniques_from_chunks(chunks)

        assert len(result) <= 5, f"Should return at most 5 techniques, got {len(result)}"

    def test_extract_techniques_from_chunks_handles_empty(self):
        """extract_techniques_from_chunks should handle empty list."""
        from scripts.generate_math_skills import extract_techniques_from_chunks

        result = extract_techniques_from_chunks([])

        assert result == [], f"Should return empty list, got {result}"

    def test_extract_techniques_from_chunks_truncates_text(self):
        """extract_techniques_from_chunks should truncate text to 500 chars."""
        from scripts.generate_math_skills import extract_techniques_from_chunks

        # Create chunk with very long realistic text (1000+ chars)
        # Must have complete sentences with capitals and periods, and >50% alphabetic
        long_text = (
            "The epsilon-delta definition of a limit is the rigorous mathematical foundation "
            "for understanding how functions behave near specific points. "
            "This technique allows mathematicians to prove that a function approaches a particular value "
            "as the input variable approaches some point. "
            "The method involves choosing an arbitrarily small positive number epsilon, "
            "then finding a corresponding delta that ensures the output stays within epsilon of the limit. "
            "This approach is fundamental to calculus and real analysis. "
            "Understanding epsilon-delta proofs requires careful manipulation of inequalities and "
            "a deep grasp of the relationship between input and output variables. "
            "Many students find this technique challenging at first, but with practice it becomes intuitive. "
            "The squeeze theorem complements this by providing an alternative approach when direct computation fails. "
        )
        chunks = [{"text": long_text}]

        result = extract_techniques_from_chunks(chunks)

        assert len(result) == 1, "Should return 1 technique"
        assert len(result[0]) <= 500, \
            f"Text should be truncated to 500 chars, got {len(result[0])}"


# =============================================================================
# Phase 3a: MathSkillSpec Dataclass Tests
# =============================================================================


class TestMathSkillSpec:
    """Test MathSkillSpec dataclass for Phase 3a."""

    def test_math_skill_spec_has_required_fields(self):
        """MathSkillSpec should have all required fields."""
        from scripts.generate_math_skills import MathSkillSpec

        spec = MathSkillSpec(
            name="limits",
            category="real-analysis",
            tier=1,
            description="Epsilon-delta proofs and limit computation",
            when_to_use="When evaluating limits of functions",
            techniques=["epsilon-delta definition", "squeeze theorem"],
            decision_tree="1. Direct substitution\n2. If indeterminate, try factoring...",
            tool_commands={"sympy": "uv run python scripts/sympy_compute.py limit ..."},
        )

        # Verify all fields accessible
        assert spec.name == "limits"
        assert spec.category == "real-analysis"
        assert spec.tier == 1
        assert spec.description == "Epsilon-delta proofs and limit computation"
        assert spec.when_to_use == "When evaluating limits of functions"
        assert spec.techniques == ["epsilon-delta definition", "squeeze theorem"]
        assert "Direct substitution" in spec.decision_tree
        assert "sympy" in spec.tool_commands

    def test_math_skill_spec_tier_is_int(self):
        """MathSkillSpec tier field should be an integer."""
        from scripts.generate_math_skills import MathSkillSpec

        spec = MathSkillSpec(
            name="limits",
            category="real-analysis",
            tier=1,
            description="Test",
            when_to_use="Test",
            techniques=[],
            decision_tree="",
            tool_commands={},
        )

        assert isinstance(spec.tier, int), f"tier should be int, got {type(spec.tier)}"

    def test_math_skill_spec_techniques_is_list(self):
        """MathSkillSpec techniques field should be a list of strings."""
        from scripts.generate_math_skills import MathSkillSpec

        techniques_list = ["epsilon-delta", "squeeze theorem", "L'Hopital"]
        spec = MathSkillSpec(
            name="limits",
            category="real-analysis",
            tier=1,
            description="Test",
            when_to_use="Test",
            techniques=techniques_list,
            decision_tree="",
            tool_commands={},
        )

        assert isinstance(spec.techniques, list), \
            f"techniques should be list, got {type(spec.techniques)}"
        for technique in spec.techniques:
            assert isinstance(technique, str), \
                f"Each technique should be str, got {type(technique)}"

    def test_math_skill_spec_triggers_default(self):
        """MathSkillSpec triggers should have default with keywords and intentPatterns."""
        from scripts.generate_math_skills import MathSkillSpec

        # Create spec WITHOUT explicitly setting triggers
        spec = MathSkillSpec(
            name="limits",
            category="real-analysis",
            tier=1,
            description="Test",
            when_to_use="Test",
            techniques=[],
            decision_tree="",
            tool_commands={},
        )

        # Should have triggers with default structure
        assert hasattr(spec, "triggers"), "MathSkillSpec should have triggers field"
        assert isinstance(spec.triggers, dict), \
            f"triggers should be dict, got {type(spec.triggers)}"
        assert "keywords" in spec.triggers, \
            f"triggers should have 'keywords' key, got: {list(spec.triggers.keys())}"
        assert "intentPatterns" in spec.triggers, \
            f"triggers should have 'intentPatterns' key, got: {list(spec.triggers.keys())}"


# =============================================================================
# Phase 3b: render_math_skill Function Tests
# =============================================================================


class TestRenderMathSkill:
    """Test render_math_skill function for Phase 3b."""

    def _create_sample_spec(self):
        """Create a sample MathSkillSpec for testing."""
        from scripts.generate_math_skills import MathSkillSpec

        return MathSkillSpec(
            name="limits",
            category="real-analysis",
            tier=1,
            description="Epsilon-delta proofs and limit computation",
            when_to_use="Use when evaluating limits of functions or proving continuity",
            techniques=["epsilon-delta definition", "squeeze theorem", "L'Hopital's rule"],
            decision_tree="1. Direct substitution\n2. If indeterminate, try factoring",
            tool_commands={
                "sympy": "uv run python scripts/sympy_compute.py limit \"sin(x)/x\" --var x --at 0",
                "z3": "uv run python scripts/z3_solve.py prove \"limit_bound\"",
            },
        )

    def test_render_math_skill_returns_string(self):
        """render_math_skill should return a string."""
        from scripts.generate_math_skills import render_math_skill

        spec = self._create_sample_spec()
        result = render_math_skill(spec)

        assert isinstance(result, str), f"Should return string, got {type(result)}"
        assert len(result) > 0, "Should return non-empty string"

    def test_render_math_skill_has_yaml_frontmatter(self):
        """render_math_skill should start with YAML frontmatter (---)."""
        from scripts.generate_math_skills import render_math_skill

        spec = self._create_sample_spec()
        result = render_math_skill(spec)

        assert result.startswith("---"), \
            f"Should start with YAML frontmatter '---', got: {result[:50]}"

        # Should have closing --- for frontmatter
        lines = result.split("\n")
        closing_idx = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                closing_idx = i
                break
        assert closing_idx is not None, \
            "Should have closing '---' for YAML frontmatter"

    def test_render_math_skill_has_name_in_frontmatter(self):
        """render_math_skill should have name: in YAML frontmatter."""
        from scripts.generate_math_skills import render_math_skill

        spec = self._create_sample_spec()
        result = render_math_skill(spec)

        # Extract frontmatter (between first and second ---)
        lines = result.split("\n")
        frontmatter_lines = []
        in_frontmatter = False
        for line in lines:
            if line.strip() == "---":
                if in_frontmatter:
                    break
                in_frontmatter = True
                continue
            if in_frontmatter:
                frontmatter_lines.append(line)

        frontmatter = "\n".join(frontmatter_lines)
        assert "name:" in frontmatter, \
            f"Frontmatter should contain 'name:', got:\n{frontmatter}"
        assert spec.name in frontmatter, \
            f"Frontmatter should contain the skill name '{spec.name}', got:\n{frontmatter}"

    def test_render_math_skill_has_when_to_use_section(self):
        """render_math_skill should have ## When to Use section."""
        from scripts.generate_math_skills import render_math_skill

        spec = self._create_sample_spec()
        result = render_math_skill(spec)

        assert "## When to Use" in result, \
            f"Should contain '## When to Use' section, got:\n{result}"

    def test_render_math_skill_has_decision_tree_section(self):
        """render_math_skill should have ## Decision Tree section."""
        from scripts.generate_math_skills import render_math_skill

        spec = self._create_sample_spec()
        result = render_math_skill(spec)

        assert "## Decision Tree" in result, \
            f"Should contain '## Decision Tree' section, got:\n{result}"

    def test_render_math_skill_has_tool_commands_section(self):
        """render_math_skill should have ## Tool Commands section."""
        from scripts.generate_math_skills import render_math_skill

        spec = self._create_sample_spec()
        result = render_math_skill(spec)

        assert "## Tool Commands" in result, \
            f"Should contain '## Tool Commands' section, got:\n{result}"

    def test_render_math_skill_no_techniques_section(self):
        """render_math_skill should NOT have Key Techniques (removed - Decision Tree sufficient)."""
        from scripts.generate_math_skills import render_math_skill

        spec = self._create_sample_spec()
        result = render_math_skill(spec)

        # Key Techniques intentionally removed - RAG chunks were noisy
        assert "## Key Techniques" not in result, \
            "Key Techniques section should be removed"


# =============================================================================
# Phase 5a: Skill Synthesis Tests
# =============================================================================


class TestSynthesizeSkill:
    """Test synthesize_skill function for Phase 5a.

    Plan reference: Phase 5a in thoughts/shared/plans/2025-12-30-math-skills-generator.md

    synthesize_skill should:
    - Return a MathSkillSpec instance
    - Set name from topic parameter
    - Set category from category parameter
    - Set tier from tier parameter
    - Extract techniques from Ragie chunks
    - Use DECISION_TREES dict for decision_tree field
    - Use TOOL_COMMANDS dict for tool_commands field
    - Generate triggers containing topic keywords
    """

    def test_synthesize_skill_returns_math_skill_spec(self):
        """synthesize_skill should return a MathSkillSpec instance."""
        from scripts.generate_math_skills import MathSkillSpec, synthesize_skill

        chunks = [{"text": "Epsilon-delta definition of a limit..."}]
        result = synthesize_skill("limits", "real-analysis", 1, chunks)

        assert isinstance(result, MathSkillSpec), \
            f"Should return MathSkillSpec, got {type(result)}"

    def test_synthesize_skill_sets_name_from_topic(self):
        """synthesize_skill should set name to match topic parameter."""
        from scripts.generate_math_skills import synthesize_skill

        chunks = [{"text": "Eigenvalue decomposition..."}]
        result = synthesize_skill("eigenvalues", "linear-algebra", 1, chunks)

        assert result.name == "eigenvalues", \
            f"Name should be 'eigenvalues', got '{result.name}'"

    def test_synthesize_skill_sets_category(self):
        """synthesize_skill should set category to match category parameter."""
        from scripts.generate_math_skills import synthesize_skill

        chunks = [{"text": "Matrix multiplication..."}]
        result = synthesize_skill("matrices", "linear-algebra", 1, chunks)

        assert result.category == "linear-algebra", \
            f"Category should be 'linear-algebra', got '{result.category}'"

    def test_synthesize_skill_sets_tier(self):
        """synthesize_skill should set tier to match tier parameter."""
        from scripts.generate_math_skills import synthesize_skill

        chunks = [{"text": "Continuity at a point..."}]
        result = synthesize_skill("continuity", "real-analysis", 1, chunks)

        assert result.tier == 1, f"Tier should be 1, got {result.tier}"

    def test_synthesize_skill_tier_2(self):
        """synthesize_skill should correctly set tier for tier 2."""
        from scripts.generate_math_skills import synthesize_skill

        chunks = [{"text": "Group theory fundamentals..."}]
        result = synthesize_skill("groups", "abstract-algebra", 2, chunks)

        assert result.tier == 2, f"Tier should be 2, got {result.tier}"

    def test_synthesize_skill_extracts_techniques(self):
        """synthesize_skill should extract techniques from Ragie chunks."""
        from scripts.generate_math_skills import synthesize_skill

        # Use realistic chunks with complete sentences meeting sanitization requirements:
        # >30 chars, >50% alphabetic, <5 math symbols, must be complete sentences
        chunks = [
            {
                "text": "The epsilon-delta definition is foundational to rigorous calculus. "
                        "It provides a way to formalize the intuitive notion of limits and continuity. "
                        "Understanding this technique is essential for proof-based mathematics."
            },
            {
                "text": "L'Hopital's rule is useful for evaluating indeterminate forms. "
                        "When direct substitution fails and you encounter forms like zero over zero, "
                        "this rule allows you to take derivatives and try again."
            },
            {
                "text": "The squeeze theorem provides an alternative method for finding limits. "
                        "This technique works by bounding a function between two functions whose limits are equal. "
                        "It is particularly useful for trigonometric and oscillating functions."
            },
        ]
        result = synthesize_skill("limits", "real-analysis", 1, chunks)

        # Should have techniques extracted
        assert len(result.techniques) > 0, "Should have extracted techniques"
        assert len(result.techniques) <= 5, "Should have at most 5 techniques"

    def test_synthesize_skill_uses_decision_tree_template(self):
        """synthesize_skill should use DECISION_TREES dict for decision_tree."""
        from scripts.generate_math_skills import DECISION_TREES, synthesize_skill

        chunks = [{"text": "Limit computation strategies..."}]
        result = synthesize_skill("limits", "real-analysis", 1, chunks)

        # If limits is in DECISION_TREES, the skill should use that template
        if "limits" in DECISION_TREES:
            expected_tree = DECISION_TREES["limits"]
            assert result.decision_tree == expected_tree, \
                f"Should use DECISION_TREES['limits']"
        else:
            # If not defined, should have a fallback
            assert "limits" in result.decision_tree.lower() or "TODO" in result.decision_tree, \
                "Decision tree should reference topic or indicate TODO"

    def test_synthesize_skill_uses_tool_commands_template(self):
        """synthesize_skill should use TOOL_COMMANDS dict for tool_commands."""
        from scripts.generate_math_skills import TOOL_COMMANDS, synthesize_skill

        chunks = [{"text": "Eigenvalue computation methods..."}]
        result = synthesize_skill("eigenvalues", "linear-algebra", 1, chunks)

        # If eigenvalues is in TOOL_COMMANDS, the skill should use that
        if "eigenvalues" in TOOL_COMMANDS:
            expected_commands = TOOL_COMMANDS["eigenvalues"]
            assert result.tool_commands == expected_commands, \
                f"Should use TOOL_COMMANDS['eigenvalues']"
        else:
            # Should have fallback commands
            assert len(result.tool_commands) > 0, \
                "Should have fallback tool commands"

    def test_synthesize_skill_generates_triggers(self):
        """synthesize_skill should generate triggers containing keywords."""
        from scripts.generate_math_skills import synthesize_skill

        chunks = [{"text": "Convergence of sequences and series..."}]
        result = synthesize_skill("convergence", "real-analysis", 1, chunks)

        # Triggers should exist
        assert "keywords" in result.triggers, "Triggers should have 'keywords'"
        assert "intentPatterns" in result.triggers, "Triggers should have 'intentPatterns'"

        # Keywords should include topic
        keywords = result.triggers["keywords"]
        assert "convergence" in keywords, \
            f"Keywords should include topic 'convergence', got: {keywords}"

    def test_synthesize_skill_generates_description(self):
        """synthesize_skill should generate a description."""
        from scripts.generate_math_skills import synthesize_skill

        chunks = [{"text": "Matrix operations and transformations..."}]
        result = synthesize_skill("matrices", "linear-algebra", 1, chunks)

        assert result.description is not None and result.description != "", \
            "Description should not be empty"
        assert len(result.description) <= 100, \
            f"Description should be <= 100 chars, got {len(result.description)}"

    def test_synthesize_skill_generates_when_to_use(self):
        """synthesize_skill should generate when_to_use text."""
        from scripts.generate_math_skills import synthesize_skill

        chunks = [{"text": "Vector space axioms..."}]
        result = synthesize_skill("vector-spaces", "linear-algebra", 1, chunks)

        assert result.when_to_use is not None and result.when_to_use != "", \
            "when_to_use should not be empty"
        # Should reference the topic
        assert "vector" in result.when_to_use.lower() or "space" in result.when_to_use.lower(), \
            f"when_to_use should reference topic, got: {result.when_to_use}"

    def test_synthesize_skill_handles_empty_chunks(self):
        """synthesize_skill should handle empty chunks gracefully."""
        from scripts.generate_math_skills import MathSkillSpec, synthesize_skill

        result = synthesize_skill("limits", "real-analysis", 1, [])

        # Should still return a valid spec
        assert isinstance(result, MathSkillSpec), "Should return MathSkillSpec"
        assert result.name == "limits", "Name should still be set"
        # Techniques might be empty, but should not crash
        assert isinstance(result.techniques, list), "Techniques should be a list"


# =============================================================================
# Phase 5b: File Writing Tests
# =============================================================================


class TestWriteSkill:
    """Test write_skill function for Phase 5b.

    Plan reference: Phase 5b in thoughts/shared/plans/2025-12-30-math-skills-generator.md

    write_skill should:
    - Create directory .claude/skills/math/{category}/{topic}/
    - Write SKILL.md file
    - Dry run mode should not create files
    - Return Path to skill file
    """

    def _create_test_spec(self):
        """Helper to create a test MathSkillSpec."""
        from scripts.generate_math_skills import MathSkillSpec

        return MathSkillSpec(
            name="test-topic",
            category="test-category",
            tier=1,
            description="Test description for skill",
            when_to_use="Use when testing",
            techniques=["technique 1", "technique 2"],
            decision_tree="1. Step one\n2. Step two",
            tool_commands={"sympy": "uv run python scripts/test.py"},
            triggers={"keywords": ["test"], "intentPatterns": ["test.*pattern"]},
        )

    def test_write_skill_creates_directory(self, tmp_path, monkeypatch):
        """write_skill should create directory .claude/skills/math/{category}/{topic}/."""
        from scripts.generate_math_skills import write_skill

        # Change to tmp_path so skill is written there
        monkeypatch.chdir(tmp_path)

        spec = self._create_test_spec()
        write_skill(spec, dry_run=False)

        expected_dir = tmp_path / ".claude" / "skills" / "math" / "test-category" / "test-topic"
        assert expected_dir.exists(), f"Directory should exist: {expected_dir}"
        assert expected_dir.is_dir(), f"Should be a directory: {expected_dir}"

    def test_write_skill_writes_file(self, tmp_path, monkeypatch):
        """write_skill should write SKILL.md file."""
        from scripts.generate_math_skills import write_skill

        monkeypatch.chdir(tmp_path)

        spec = self._create_test_spec()
        write_skill(spec, dry_run=False)

        expected_file = tmp_path / ".claude" / "skills" / "math" / "test-category" / "test-topic" / "SKILL.md"
        assert expected_file.exists(), f"SKILL.md should exist: {expected_file}"
        assert expected_file.is_file(), f"Should be a file: {expected_file}"

        # Verify content is not empty
        content = expected_file.read_text()
        assert len(content) > 0, "SKILL.md should not be empty"

    def test_write_skill_dry_run_no_write(self, tmp_path, monkeypatch):
        """write_skill with dry_run=True should not create files."""
        from scripts.generate_math_skills import write_skill

        monkeypatch.chdir(tmp_path)

        spec = self._create_test_spec()
        write_skill(spec, dry_run=True)

        expected_dir = tmp_path / ".claude" / "skills" / "math" / "test-category" / "test-topic"
        assert not expected_dir.exists(), \
            f"Directory should NOT exist in dry-run mode: {expected_dir}"

    def test_write_skill_returns_path(self, tmp_path, monkeypatch):
        """write_skill should return Path to skill file."""
        from scripts.generate_math_skills import write_skill

        monkeypatch.chdir(tmp_path)

        spec = self._create_test_spec()
        result = write_skill(spec, dry_run=False)

        assert isinstance(result, Path), f"Should return Path, got {type(result)}"
        assert result.name == "SKILL.md", f"Path should end with SKILL.md, got {result.name}"

    def test_write_skill_dry_run_returns_path(self, tmp_path, monkeypatch):
        """write_skill with dry_run=True should still return the Path."""
        from scripts.generate_math_skills import write_skill

        monkeypatch.chdir(tmp_path)

        spec = self._create_test_spec()
        result = write_skill(spec, dry_run=True)

        assert isinstance(result, Path), f"Should return Path even in dry-run, got {type(result)}"
        assert "test-category" in str(result), "Path should include category"
        assert "test-topic" in str(result), "Path should include topic name"

    def test_write_skill_writes_yaml_frontmatter(self, tmp_path, monkeypatch):
        """write_skill should write YAML frontmatter to SKILL.md."""
        from scripts.generate_math_skills import write_skill

        monkeypatch.chdir(tmp_path)

        spec = self._create_test_spec()
        write_skill(spec, dry_run=False)

        expected_file = tmp_path / ".claude" / "skills" / "math" / "test-category" / "test-topic" / "SKILL.md"
        content = expected_file.read_text()

        # Should start with YAML frontmatter
        assert content.startswith("---"), "SKILL.md should start with YAML frontmatter"
        # Should have closing YAML delimiter
        lines = content.split("\n")
        # Find second --- (closing delimiter)
        dash_count = 0
        for line in lines:
            if line.strip() == "---":
                dash_count += 1
        assert dash_count >= 2, "SKILL.md should have opening and closing YAML delimiters"

    def test_write_skill_includes_name_in_frontmatter(self, tmp_path, monkeypatch):
        """write_skill should include name in YAML frontmatter."""
        from scripts.generate_math_skills import write_skill

        monkeypatch.chdir(tmp_path)

        spec = self._create_test_spec()
        write_skill(spec, dry_run=False)

        expected_file = tmp_path / ".claude" / "skills" / "math" / "test-category" / "test-topic" / "SKILL.md"
        content = expected_file.read_text()

        assert "name: test-topic" in content, \
            f"SKILL.md should include name in frontmatter, got:\n{content[:200]}"

    def test_write_skill_includes_decision_tree_section(self, tmp_path, monkeypatch):
        """write_skill should include Decision Tree section."""
        from scripts.generate_math_skills import write_skill

        monkeypatch.chdir(tmp_path)

        spec = self._create_test_spec()
        write_skill(spec, dry_run=False)

        expected_file = tmp_path / ".claude" / "skills" / "math" / "test-category" / "test-topic" / "SKILL.md"
        content = expected_file.read_text()

        assert "## Decision Tree" in content, \
            f"SKILL.md should include Decision Tree section"

    def test_write_skill_includes_tool_commands_section(self, tmp_path, monkeypatch):
        """write_skill should include Tool Commands section."""
        from scripts.generate_math_skills import write_skill

        monkeypatch.chdir(tmp_path)

        spec = self._create_test_spec()
        write_skill(spec, dry_run=False)

        expected_file = tmp_path / ".claude" / "skills" / "math" / "test-category" / "test-topic" / "SKILL.md"
        content = expected_file.read_text()

        assert "## Tool Commands" in content, \
            f"SKILL.md should include Tool Commands section"

    def test_write_skill_overwrites_existing(self, tmp_path, monkeypatch):
        """write_skill should overwrite existing SKILL.md."""
        from scripts.generate_math_skills import write_skill

        monkeypatch.chdir(tmp_path)

        # Create directory and initial file
        skill_dir = tmp_path / ".claude" / "skills" / "math" / "test-category" / "test-topic"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("OLD CONTENT")

        # Write new skill
        spec = self._create_test_spec()
        write_skill(spec, dry_run=False)

        # Should have new content
        content = skill_file.read_text()
        assert "OLD CONTENT" not in content, "Should overwrite old content"
        assert "---" in content, "Should have YAML frontmatter"


# =============================================================================
# Phase 6a-6b: generate_tier Function Tests
# =============================================================================


class TestGenerateTier:
    """Test generate_tier function for Phase 6a-6b.

    Plan reference: Phase 6a-6b in thoughts/shared/plans/2025-12-30-math-skills-generator.md

    generate_tier should:
    - Return a list of Path objects
    - Generate 6 skills for tier 1 (3 real-analysis + 3 linear-algebra)
    - Respect category_filter parameter
    - Raise ValueError for invalid tier
    - Dry run mode should not create files
    """

    def test_generate_tier_returns_list_of_paths(self, tmp_path, monkeypatch):
        """generate_tier should return a list of Path objects."""
        import asyncio
        from scripts.generate_math_skills import generate_tier

        monkeypatch.chdir(tmp_path)
        # Mock Ragie call to avoid external dependency
        monkeypatch.setenv("RAGIE_API_KEY", "test-key")

        with patch("scripts.generate_math_skills.query_ragie_for_topic", return_value=[]):
            result = asyncio.run(generate_tier(1, dry_run=True, base_path=tmp_path / ".claude" / "skills"))

        assert isinstance(result, list), f"Should return list, got {type(result)}"
        for path in result:
            assert isinstance(path, Path), f"Each item should be Path, got {type(path)}"

    def test_generate_tier_tier_1_has_six_paths(self, tmp_path, monkeypatch):
        """generate_tier for tier 1 should return 6 paths (3 real-analysis + 3 linear-algebra)."""
        import asyncio
        from scripts.generate_math_skills import generate_tier

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("RAGIE_API_KEY", "test-key")

        with patch("scripts.generate_math_skills.query_ragie_for_topic", return_value=[]):
            result = asyncio.run(generate_tier(1, dry_run=True, base_path=tmp_path / ".claude" / "skills"))

        assert len(result) == 6, f"Tier 1 should generate 6 skills, got {len(result)}"

    def test_generate_tier_respects_category_filter(self, tmp_path, monkeypatch):
        """generate_tier should only generate skills for filtered category."""
        import asyncio
        from scripts.generate_math_skills import generate_tier

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("RAGIE_API_KEY", "test-key")

        with patch("scripts.generate_math_skills.query_ragie_for_topic", return_value=[]):
            result = asyncio.run(generate_tier(
                1,
                category_filter="real-analysis",
                dry_run=True,
                base_path=tmp_path / ".claude" / "skills"
            ))

        # real-analysis has 3 topics
        assert len(result) == 3, f"Should generate 3 skills for real-analysis, got {len(result)}"
        # All paths should be in real-analysis
        for path in result:
            assert "real-analysis" in str(path), f"Path should be in real-analysis: {path}"

    def test_generate_tier_invalid_tier_raises(self, tmp_path, monkeypatch):
        """generate_tier should raise ValueError for undefined tier."""
        import asyncio
        from scripts.generate_math_skills import generate_tier

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("RAGIE_API_KEY", "test-key")

        # Tier 99 is not defined
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(generate_tier(99, dry_run=True, base_path=tmp_path / ".claude" / "skills"))

        assert "99" in str(exc_info.value) or "not defined" in str(exc_info.value).lower(), \
            f"Error should mention tier not defined, got: {exc_info.value}"

    def test_generate_tier_dry_run_no_files(self, tmp_path, monkeypatch):
        """generate_tier with dry_run=True should not create any files."""
        import asyncio
        from scripts.generate_math_skills import generate_tier

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("RAGIE_API_KEY", "test-key")

        base_path = tmp_path / ".claude" / "skills"

        with patch("scripts.generate_math_skills.query_ragie_for_topic", return_value=[]):
            asyncio.run(generate_tier(1, dry_run=True, base_path=base_path))

        # Check no directories were created
        if base_path.exists():
            math_dir = base_path / "math"
            assert not math_dir.exists(), \
                f"math directory should NOT exist in dry-run mode: {list(base_path.iterdir())}"

    def test_generate_tier_invalid_category_raises(self, tmp_path, monkeypatch):
        """generate_tier should raise ValueError for invalid category in tier."""
        import asyncio
        from scripts.generate_math_skills import generate_tier

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("RAGIE_API_KEY", "test-key")

        # "fake-category" is not in tier 1
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(generate_tier(
                1,
                category_filter="fake-category",
                dry_run=True,
                base_path=tmp_path / ".claude" / "skills"
            ))

        assert "fake-category" in str(exc_info.value).lower() or "not in tier" in str(exc_info.value).lower(), \
            f"Error should mention category not in tier, got: {exc_info.value}"

    def test_generate_tier_creates_files_when_not_dry_run(self, tmp_path, monkeypatch):
        """generate_tier should create actual files when dry_run=False."""
        import asyncio
        from scripts.generate_math_skills import generate_tier

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("RAGIE_API_KEY", "test-key")

        base_path = tmp_path / ".claude" / "skills"

        with patch("scripts.generate_math_skills.query_ragie_for_topic", return_value=[]):
            result = asyncio.run(generate_tier(
                1,
                category_filter="real-analysis",
                dry_run=False,
                base_path=base_path
            ))

        # Should create 3 SKILL.md files
        for path in result:
            assert path.exists(), f"SKILL.md should exist: {path}"
            assert path.is_file(), f"Should be a file: {path}"

    def test_generate_tier_handles_ragie_errors_gracefully(self, tmp_path, monkeypatch):
        """generate_tier should continue even if Ragie query fails."""
        import asyncio
        from scripts.generate_math_skills import generate_tier

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("RAGIE_API_KEY", "test-key")

        base_path = tmp_path / ".claude" / "skills"

        # Mock Ragie to raise an exception
        def mock_ragie_error(topic, category, top_k=10):
            raise RuntimeError("Ragie API error")

        with patch("scripts.generate_math_skills.query_ragie_for_topic", side_effect=mock_ragie_error):
            # Should not raise - should handle gracefully
            result = asyncio.run(generate_tier(
                1,
                category_filter="real-analysis",
                dry_run=True,
                base_path=base_path
            ))

        # Should still return 3 paths even with Ragie errors
        assert len(result) == 3, f"Should still generate 3 skills, got {len(result)}"


# =============================================================================
# YAML Sanitization Tests
# =============================================================================


class TestSanitizeForYaml:
    """Test sanitize_for_yaml function for YAML frontmatter safety."""

    def test_sanitize_removes_newlines(self):
        """sanitize_for_yaml should remove newlines and collapse whitespace."""
        from scripts.generate_math_skills import sanitize_for_yaml
        result = sanitize_for_yaml("line1\nline2\nline3")
        assert '\n' not in result
        assert 'line1 line2 line3' == result

    def test_sanitize_truncates_long_text(self):
        """sanitize_for_yaml should truncate text longer than 80 chars."""
        from scripts.generate_math_skills import sanitize_for_yaml
        long_text = "x" * 100
        result = sanitize_for_yaml(long_text)
        assert len(result) <= 80
        assert result.endswith("...")

    def test_sanitize_replaces_quotes(self):
        """sanitize_for_yaml should replace double quotes with single quotes."""
        from scripts.generate_math_skills import sanitize_for_yaml
        result = sanitize_for_yaml('text with "quotes"')
        assert '"' not in result

    def test_sanitize_replaces_colons(self):
        """sanitize_for_yaml should replace colons to avoid YAML parsing issues."""
        from scripts.generate_math_skills import sanitize_for_yaml
        result = sanitize_for_yaml('key: value here')
        assert ':' not in result

    def test_sanitize_collapses_multiple_spaces(self):
        """sanitize_for_yaml should collapse multiple whitespace to single space."""
        from scripts.generate_math_skills import sanitize_for_yaml
        result = sanitize_for_yaml('word1    word2\t\tword3')
        assert result == 'word1 word2 word3'

    def test_sanitize_short_text_unchanged(self):
        """sanitize_for_yaml should not truncate text under 80 chars."""
        from scripts.generate_math_skills import sanitize_for_yaml
        short_text = "short text"
        result = sanitize_for_yaml(short_text)
        assert result == short_text
        assert not result.endswith("...")
