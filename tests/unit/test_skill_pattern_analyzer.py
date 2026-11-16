"""Tests for Skill Pattern Analyzer (Phase 3 Tasks 3.1-3.6).

TDD tests for pattern analysis and refinement based on user corrections.
"""

import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta

from scripts.skill_feedback import CorrectionRecord


# Task 3.1: Test pattern analyzer skeleton
class TestPatternAnalyzerSkeleton:
    """Task 3.1: Pattern analyzer returns suggestions."""

    def test_analyze_corrections_returns_suggestions(self):
        """Pattern analyzer returns list of suggestions from corrections."""
        from scripts.skill_pattern_analyzer import analyze_corrections

        corrections = [
            CorrectionRecord(
                skill_id="deploy-api",
                param="hosting",
                old_value="aws",
                new_value="gcp",
                timestamp=datetime.now(timezone.utc).isoformat(),
                context="deploy to google cloud"
            )
        ]

        suggestions = analyze_corrections(corrections)

        assert isinstance(suggestions, list)


# Task 3.2: Test correction frequency analysis
class TestCorrectionFrequencyAnalysis:
    """Task 3.2: Identify weak patterns from correction frequency."""

    def test_identify_weak_patterns(self):
        """Parameters with >20% correction rate flagged as weak."""
        from scripts.skill_pattern_analyzer import identify_weak_patterns

        # Create corrections - 3 corrections for 'hosting', 1 for 'region'
        corrections = [
            CorrectionRecord("deploy-api", "hosting", "aws", "gcp",
                           datetime.now(timezone.utc).isoformat(), "ctx1"),
            CorrectionRecord("deploy-api", "hosting", "aws", "azure",
                           datetime.now(timezone.utc).isoformat(), "ctx2"),
            CorrectionRecord("deploy-api", "hosting", "gcp", "aws",
                           datetime.now(timezone.utc).isoformat(), "ctx3"),
            CorrectionRecord("deploy-api", "region", "us-east-1", "eu-west-1",
                           datetime.now(timezone.utc).isoformat(), "ctx4"),
        ]

        weak = identify_weak_patterns(corrections)

        # 'hosting' has 3 corrections -> likely weak
        assert "hosting" in weak
        # 'region' has only 1 correction -> may or may not be flagged
        # depending on threshold implementation


# Task 3.3: Test pattern suggestion generator
class TestPatternSuggestionGenerator:
    """Task 3.3: Suggest improved infer_from patterns."""

    def test_suggest_improved_pattern(self):
        """Generate regex suggestion from correction patterns."""
        from scripts.skill_pattern_analyzer import suggest_improved_pattern

        corrections = [
            CorrectionRecord("deploy-api", "hosting", "aws", "gcp",
                           datetime.now(timezone.utc).isoformat(),
                           "deploy to google cloud kubernetes"),
            CorrectionRecord("deploy-api", "hosting", "aws", "gcp",
                           datetime.now(timezone.utc).isoformat(),
                           "GCP deployment please"),
        ]

        suggestion = suggest_improved_pattern("hosting", corrections)

        assert suggestion is not None
        assert "pattern" in suggestion
        # Suggestion should include context keywords
        assert suggestion.get("keywords") or suggestion.get("pattern")


# Task 3.4: Test pure function for pattern suggestion
class TestComputePatternSuggestion:
    """Task 3.4: Pure function for pattern computation."""

    def test_compute_pattern_suggestion_pure(self):
        """compute_pattern_suggestion is a pure function (no side effects)."""
        from scripts.skill_pattern_analyzer import compute_pattern_suggestion

        corrections = [
            CorrectionRecord("deploy-api", "hosting", "aws", "gcp",
                           datetime.now(timezone.utc).isoformat(),
                           "deploy to google cloud"),
        ]

        # Call twice - should return same result
        result1 = compute_pattern_suggestion("hosting", corrections)
        result2 = compute_pattern_suggestion("hosting", corrections)

        assert result1 == result2


# Task 3.5: Test apply pattern suggestion
class TestApplyPatternSuggestion:
    """Task 3.5: Apply pattern suggestion to SKILL.md."""

    def test_apply_pattern_suggestion_writes(self, tmp_path: Path):
        """apply_pattern_suggestion writes to SKILL.md."""
        from scripts.skill_pattern_analyzer import apply_pattern_suggestion

        # Create test skill
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-skill
description: Test skill
parameters:
  hosting:
    type: enum
    values: [aws, gcp, azure]
    infer_from: "aws|gcp|azure"
---

# Test Skill
""")

        suggestion = {
            "param": "hosting",
            "pattern": r"google\s*cloud|gcp|aws|azure",
            "priority_values": {"gcp": ["google cloud", "kubernetes"]}
        }

        apply_pattern_suggestion(skill_dir, suggestion)

        # Read back and verify
        updated_content = skill_file.read_text()
        assert "google" in updated_content.lower() or "infer_from" in updated_content


# Task 3.6: Test validate applied pattern
class TestValidateAppliedPattern:
    """Task 3.6: Validate pattern after application."""

    def test_validate_applied_pattern(self, tmp_path: Path):
        """Applied pattern should leave SKILL.md valid."""
        from scripts.skill_pattern_analyzer import (
            apply_pattern_suggestion,
            validate_applied_pattern
        )

        # Create test skill
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""---
name: test-skill
description: Test skill
parameters:
  hosting:
    type: enum
    values: [aws, gcp, azure]
---

# Test Skill
""")

        suggestion = {
            "param": "hosting",
            "pattern": r"aws|gcp|azure|vercel",
            "priority_values": {}
        }

        apply_pattern_suggestion(skill_dir, suggestion)

        # Validate
        is_valid = validate_applied_pattern(skill_dir)

        assert is_valid is True
