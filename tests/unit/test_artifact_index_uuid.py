"""Tests for UUID-suffixed handoff path parsing in artifact_index.py."""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from artifact_index import parse_handoff


class TestUUIDPathParsing:
    """Test session name and UUID extraction from handoff paths."""

    def test_parse_uuid_suffixed_path(self, tmp_path):
        """Should extract session name and UUID from suffixed directory."""
        # Create: handoffs/auth-refactor-550e8400/current.md
        handoff_dir = tmp_path / "thoughts" / "shared" / "handoffs" / "auth-refactor-550e8400"
        handoff_dir.mkdir(parents=True)
        handoff_file = handoff_dir / "current.md"
        handoff_file.write_text("## What Was Done\nFixed auth\n")

        result = parse_handoff(handoff_file)
        
        assert result["session_name"] == "auth-refactor"
        assert result["session_uuid"] == "550e8400"

    def test_parse_legacy_path(self, tmp_path):
        """Should handle legacy directory without UUID suffix."""
        # Create: handoffs/auth-refactor/current.md
        handoff_dir = tmp_path / "thoughts" / "shared" / "handoffs" / "auth-refactor"
        handoff_dir.mkdir(parents=True)
        handoff_file = handoff_dir / "current.md"
        handoff_file.write_text("## What Was Done\nLegacy handoff\n")

        result = parse_handoff(handoff_file)
        
        assert result["session_name"] == "auth-refactor"
        assert result["session_uuid"] is None

    def test_parse_multiple_hyphens(self, tmp_path):
        """Should handle session names with multiple hyphens."""
        # Create: handoffs/my-cool-feature-v2-abcd1234/current.md
        handoff_dir = tmp_path / "thoughts" / "shared" / "handoffs" / "my-cool-feature-v2-abcd1234"
        handoff_dir.mkdir(parents=True)
        handoff_file = handoff_dir / "current.md"
        handoff_file.write_text("## What Was Done\nMulti-hyphen test\n")

        result = parse_handoff(handoff_file)
        
        assert result["session_name"] == "my-cool-feature-v2"
        assert result["session_uuid"] == "abcd1234"

    def test_non_hex_suffix_not_parsed_as_uuid(self, tmp_path):
        """Should not parse non-hex suffix as UUID."""
        # "v2" is not 8 hex chars
        handoff_dir = tmp_path / "thoughts" / "shared" / "handoffs" / "my-feature-v2"
        handoff_dir.mkdir(parents=True)
        handoff_file = handoff_dir / "current.md"
        handoff_file.write_text("## What Was Done\nNon-hex suffix\n")

        result = parse_handoff(handoff_file)
        
        assert result["session_name"] == "my-feature-v2"
        assert result["session_uuid"] is None

    def test_short_suffix_not_parsed_as_uuid(self, tmp_path):
        """Should require exactly 8 hex chars for UUID."""
        # "abc123" is only 6 chars
        handoff_dir = tmp_path / "thoughts" / "shared" / "handoffs" / "my-feature-abc123"
        handoff_dir.mkdir(parents=True)
        handoff_file = handoff_dir / "current.md"
        handoff_file.write_text("## What Was Done\nShort suffix\n")

        result = parse_handoff(handoff_file)
        
        assert result["session_name"] == "my-feature-abc123"
        assert result["session_uuid"] is None

    def test_uppercase_uuid_normalized(self, tmp_path):
        """Should normalize uppercase UUID to lowercase."""
        handoff_dir = tmp_path / "thoughts" / "shared" / "handoffs" / "auth-ABCD1234"
        handoff_dir.mkdir(parents=True)
        handoff_file = handoff_dir / "current.md"
        handoff_file.write_text("## What Was Done\nUppercase UUID\n")

        result = parse_handoff(handoff_file)
        
        assert result["session_name"] == "auth"
        assert result["session_uuid"] == "abcd1234"  # Lowercase
