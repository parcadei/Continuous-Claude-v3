"""Tests for Skill Feedback Capture (Phase 2 Tasks 2.12-2.14).

TDD approach: Tests written FIRST, then implementation.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import pytest


# =============================================================================
# Task 2.12: Capture Correction Stores Data
# =============================================================================


def test_capture_correction_stores_data():
    """Task 2.12: capture_correction() stores data in memory."""
    from scripts.skill_feedback import capture_correction, CorrectionRecord

    correction = capture_correction(
        skill_id="deploy-api",
        param="hosting",
        old_value="aws",
        new_value="gcp",
        context="Deploy to GCP instead"
    )

    assert isinstance(correction, CorrectionRecord)
    assert correction.skill_id == "deploy-api"
    assert correction.param == "hosting"
    assert correction.old_value == "aws"
    assert correction.new_value == "gcp"
    assert correction.context == "Deploy to GCP instead"


# =============================================================================
# Task 2.13: Correction Record Schema
# =============================================================================


def test_correction_record_schema():
    """Task 2.13: CorrectionRecord has all required fields."""
    from scripts.skill_feedback import CorrectionRecord

    record = CorrectionRecord(
        skill_id="deploy-api",
        param="hosting",
        old_value="aws",
        new_value="gcp",
        context="user prompt",
        timestamp="2025-12-30T10:00:00Z"
    )

    # Verify all required fields
    assert hasattr(record, 'skill_id')
    assert hasattr(record, 'param')
    assert hasattr(record, 'old_value')
    assert hasattr(record, 'new_value')
    assert hasattr(record, 'timestamp')
    assert hasattr(record, 'context')


def test_correction_record_to_dict():
    """Task 2.13b: CorrectionRecord can be serialized to dict."""
    from scripts.skill_feedback import CorrectionRecord

    record = CorrectionRecord(
        skill_id="test",
        param="p",
        old_value="a",
        new_value="b",
        context="ctx",
        timestamp="2025-12-30T10:00:00Z"
    )

    d = record.to_dict()
    assert isinstance(d, dict)
    assert d["skill_id"] == "test"
    assert d["param"] == "p"


def test_correction_record_auto_timestamp():
    """Task 2.13c: CorrectionRecord generates timestamp if not provided."""
    from scripts.skill_feedback import capture_correction

    correction = capture_correction(
        skill_id="test",
        param="p",
        old_value="a",
        new_value="b"
    )

    # Should have auto-generated timestamp
    assert correction.timestamp is not None
    # Should be parseable as ISO format
    datetime.fromisoformat(correction.timestamp.replace('Z', '+00:00'))


# =============================================================================
# Task 2.14: Correction File Persistence
# =============================================================================


def test_correction_persisted_to_file():
    """Task 2.14: Corrections are persisted to .jsonl file."""
    from scripts.skill_feedback import capture_correction, persist_correction, load_corrections

    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp) / ".claude" / "cache" / "skill-corrections"

        with patch('scripts.skill_feedback.get_corrections_dir', return_value=cache_dir):
            correction = capture_correction(
                skill_id="deploy-api",
                param="hosting",
                old_value="aws",
                new_value="gcp"
            )

            persist_correction(correction)

            # Verify file exists
            expected_file = cache_dir / "deploy-api.jsonl"
            assert expected_file.exists()

            # Verify content
            lines = expected_file.read_text().strip().split('\n')
            assert len(lines) == 1

            record = json.loads(lines[0])
            assert record["skill_id"] == "deploy-api"
            assert record["param"] == "hosting"


def test_corrections_appended_to_file():
    """Task 2.14b: Multiple corrections append to same file."""
    from scripts.skill_feedback import capture_correction, persist_correction

    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp) / ".claude" / "cache" / "skill-corrections"

        with patch('scripts.skill_feedback.get_corrections_dir', return_value=cache_dir):
            # Persist two corrections
            c1 = capture_correction(
                skill_id="deploy-api",
                param="hosting",
                old_value="aws",
                new_value="gcp"
            )
            persist_correction(c1)

            c2 = capture_correction(
                skill_id="deploy-api",
                param="auth",
                old_value="jwt",
                new_value="oauth"
            )
            persist_correction(c2)

            # Verify both are in file
            expected_file = cache_dir / "deploy-api.jsonl"
            lines = expected_file.read_text().strip().split('\n')
            assert len(lines) == 2


def test_load_corrections_for_skill():
    """Task 2.14c: Can load all corrections for a skill."""
    from scripts.skill_feedback import capture_correction, persist_correction, load_corrections

    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp) / ".claude" / "cache" / "skill-corrections"

        with patch('scripts.skill_feedback.get_corrections_dir', return_value=cache_dir):
            c1 = capture_correction(
                skill_id="deploy-api",
                param="hosting",
                old_value="aws",
                new_value="gcp"
            )
            persist_correction(c1)

            c2 = capture_correction(
                skill_id="deploy-api",
                param="auth",
                old_value="jwt",
                new_value="oauth"
            )
            persist_correction(c2)

            # Load corrections
            corrections = load_corrections("deploy-api")
            assert len(corrections) == 2
            assert corrections[0].param == "hosting"
            assert corrections[1].param == "auth"


def test_load_corrections_empty():
    """Task 2.14d: Loading corrections for non-existent skill returns empty list."""
    from scripts.skill_feedback import load_corrections

    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp) / ".claude" / "cache" / "skill-corrections"

        with patch('scripts.skill_feedback.get_corrections_dir', return_value=cache_dir):
            corrections = load_corrections("nonexistent-skill")
            assert corrections == []
