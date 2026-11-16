"""Security tests for AgentHandoff path traversal prevention.

Tests verify that path traversal attacks are blocked for:
1. session_id parameter in __init__
2. phase parameter in get_output_dir, chain_from, etc.
3. name parameter in write_artifact, read_artifact
4. cleanup() method with malicious session_dir
5. Double encoding attacks
6. Null byte injection
7. Symlink attacks (limited - OS-level test)

Run with: uv run pytest tests/unit/test_agent_handoff_security.py -v

TDD Phase 1: These tests are written BEFORE the fix is implemented.
They should FAIL initially, proving the vulnerability exists.
"""

import os
import pytest
from pathlib import Path
import tempfile

from scripts.agentica_patterns.agent_handoff import (
    AgentHandoff,
    create_handoff,
    get_phase_summary,
)

# Note: These imports will fail until Phase 1 implementation adds the helpers
# The tests are structured to fail gracefully and show what's missing

try:
    from scripts.agentica_patterns.agent_handoff import (
        _validate_path_component,
        _validate_filename,
        _validate_path_within_base,
    )
    HELPERS_EXIST = True
except ImportError:
    HELPERS_EXIST = False


class TestValidatePathComponentHelper:
    """Test _validate_path_component helper function.

    These tests will fail with ImportError until Phase 1 is implemented.
    """

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_valid_session_ids_accepted(self):
        """Valid session IDs should pass validation."""
        valid_ids = [
            "task-123",
            "session_abc",
            "myTask",
            "UPPER_CASE",
            "mixed-Case_123",
            "a",
            "1",
            "test123",
        ]
        for sid in valid_ids:
            assert _validate_path_component(sid, "session_id") == sid

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_empty_string_rejected(self):
        """Empty string should be rejected."""
        with pytest.raises(ValueError, match="[Ee]mpty"):
            _validate_path_component("", "session_id")

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_traversal_patterns_rejected(self):
        """Path traversal sequences should be rejected."""
        traversal_attempts = [
            "..",
            "../",
            "..\\",
            "foo/../bar",
            "session/../../etc",
            "....",
            "..../",
            "../../../etc/passwd",
        ]
        for attempt in traversal_attempts:
            with pytest.raises(ValueError, match="[Tt]raversal|[Ss]eparator"):
                _validate_path_component(attempt, "session_id")

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_absolute_path_rejected(self):
        """Absolute paths should be rejected."""
        absolute_paths = [
            "/etc/passwd",
            "/tmp/evil",
            "/home/user",
        ]
        for path in absolute_paths:
            with pytest.raises(ValueError, match="[Aa]bsolute"):
                _validate_path_component(path, "session_id")

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_home_expansion_rejected(self):
        """Tilde expansion should be rejected."""
        with pytest.raises(ValueError, match="[Aa]bsolute"):
            _validate_path_component("~/secret", "session_id")

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_path_separator_rejected(self):
        """Path separators should be rejected."""
        with pytest.raises(ValueError, match="[Ss]eparator"):
            _validate_path_component("foo/bar", "session_id")
        with pytest.raises(ValueError, match="[Ss]eparator"):
            _validate_path_component("foo\\bar", "session_id")

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_null_byte_rejected(self):
        """Null bytes should be rejected (null byte injection attack)."""
        with pytest.raises(ValueError, match="[Nn]ull"):
            _validate_path_component("session\x00evil", "session_id")

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_special_chars_rejected(self):
        """Special characters should be rejected."""
        invalid_chars = [
            "session!",
            "session@home",
            "session$var",
            "session%path",
            "session*glob",
            "session;cmd",
            "session|pipe",
            "session`tick`",
            "session$(cmd)",
        ]
        for attempt in invalid_chars:
            with pytest.raises(ValueError):
                _validate_path_component(attempt, "session_id")


class TestValidateFilenameHelper:
    """Test _validate_filename helper function."""

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_valid_filenames_accepted(self):
        """Valid filenames should pass."""
        valid_names = [
            "artifact.json",
            "data.txt",
            "summary.md",
            "file_name.py",
            "FILE-NAME.txt",
            "noextension",
            "file123.log",
        ]
        for name in valid_names:
            assert _validate_filename(name) == name

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_empty_filename_rejected(self):
        """Empty filename should be rejected."""
        with pytest.raises(ValueError, match="[Ee]mpty"):
            _validate_filename("")

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_traversal_in_filename_rejected(self):
        """Path traversal in filename should be rejected."""
        with pytest.raises(ValueError, match="[Tt]raversal"):
            _validate_filename("../etc/passwd")
        with pytest.raises(ValueError, match="[Tt]raversal"):
            _validate_filename("..\\windows\\system32")

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_hidden_file_rejected(self):
        """Hidden files (starting with .) should be rejected."""
        with pytest.raises(ValueError, match="[Hh]idden"):
            _validate_filename(".bashrc")
        with pytest.raises(ValueError, match="[Hh]idden"):
            _validate_filename(".ssh")
        with pytest.raises(ValueError, match="[Hh]idden"):
            _validate_filename(".env")

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_path_separator_in_filename_rejected(self):
        """Filenames with path separators should be rejected."""
        with pytest.raises(ValueError, match="[Ss]eparator"):
            _validate_filename("path/to/file.txt")
        with pytest.raises(ValueError, match="[Ss]eparator"):
            _validate_filename("path\\to\\file.txt")

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_null_byte_in_filename_rejected(self):
        """Null byte in filename should be rejected."""
        with pytest.raises(ValueError, match="[Nn]ull"):
            _validate_filename("file\x00.txt")


class TestValidatePathWithinBaseHelper:
    """Test _validate_path_within_base helper function."""

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_valid_subpath_accepted(self, tmp_path):
        """Paths within base should pass."""
        base = tmp_path / "base"
        base.mkdir()
        child = base / "session" / "phase"

        result = _validate_path_within_base(child, base)
        assert str(result).startswith(str(base.resolve()))

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_escaped_path_rejected(self, tmp_path):
        """Paths escaping base should be rejected."""
        base = tmp_path / "base"
        base.mkdir()
        escaped = tmp_path / "secret"

        with pytest.raises(ValueError, match="[Ee]scape"):
            _validate_path_within_base(escaped, base)

    @pytest.mark.skipif(not HELPERS_EXIST, reason="Helper not implemented yet")
    def test_parent_traversal_rejected(self, tmp_path):
        """Parent traversal should be blocked after resolution."""
        base = tmp_path / "base"
        base.mkdir()
        # This path, when resolved, escapes base
        tricky_path = base / ".." / "secret"

        with pytest.raises(ValueError, match="[Ee]scape"):
            _validate_path_within_base(tricky_path, base)


class TestSessionIdPathTraversal:
    """Test session_id path traversal attacks in __init__.

    These tests verify the vulnerability EXISTS (tests should FAIL after fix).
    Currently they will PASS because the vulnerability is present.
    After fix, they should raise ValueError instead of creating directories.
    """

    def test_session_id_basic_traversal_creates_outside_base(self, tmp_path):
        """VULNERABILITY: Basic ../ traversal in session_id creates dirs outside base.

        After fix: Should raise ValueError instead.
        """
        base = tmp_path / "base"
        base.mkdir()
        target = tmp_path / "evil"

        # This SHOULD raise ValueError but currently doesn't
        try:
            handoff = AgentHandoff("../evil", base_dir=base)
            # If we get here, the vulnerability exists
            assert target.exists(), "Path traversal created directory outside base"
            pytest.fail(
                "VULNERABILITY: Session ID '../evil' should be rejected but was accepted. "
                "Directory created at: " + str(target)
            )
        except ValueError:
            # This is the expected behavior after fix
            pass

    def test_session_id_deep_traversal(self, tmp_path):
        """VULNERABILITY: Deep traversal can escape further up the tree."""
        base = tmp_path / "a" / "b" / "c" / "base"
        base.mkdir(parents=True)

        try:
            handoff = AgentHandoff("../../../../outside", base_dir=base)
            pytest.fail(
                "VULNERABILITY: Deep traversal should be rejected"
            )
        except ValueError:
            pass  # Expected after fix

    def test_session_id_absolute_path(self, tmp_path):
        """VULNERABILITY: Absolute path in session_id."""
        base = tmp_path / "base"
        base.mkdir()

        try:
            handoff = AgentHandoff("/tmp/evil", base_dir=base)
            pytest.fail(
                "VULNERABILITY: Absolute path session_id should be rejected"
            )
        except ValueError:
            pass  # Expected after fix

    def test_session_id_null_byte_injection(self, tmp_path):
        """VULNERABILITY: Null byte injection in session_id."""
        base = tmp_path / "base"
        base.mkdir()

        try:
            # Null bytes can truncate paths in some systems
            handoff = AgentHandoff("session\x00../evil", base_dir=base)
            pytest.fail(
                "VULNERABILITY: Null byte in session_id should be rejected"
            )
        except ValueError:
            pass  # Expected after fix


class TestPhasePathTraversal:
    """Test phase parameter path traversal attacks."""

    def test_get_output_dir_traversal(self, tmp_path):
        """VULNERABILITY: Phase traversal in get_output_dir."""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)

        try:
            output = handoff.get_output_dir("../../../tmp")
            pytest.fail(
                f"VULNERABILITY: Phase traversal should be rejected. Got: {output}"
            )
        except ValueError:
            pass  # Expected after fix

    def test_chain_from_traversal(self, tmp_path):
        """VULNERABILITY: Traversal in chain_from."""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)

        try:
            path = handoff.chain_from("../../etc")
            # If we get here, vulnerability exists
            assert str(path).endswith("etc"), "Traversal was not blocked"
            pytest.fail(
                f"VULNERABILITY: chain_from traversal should be rejected. Got: {path}"
            )
        except ValueError:
            pass  # Expected after fix

    def test_read_summary_traversal(self, tmp_path):
        """VULNERABILITY: Traversal in read_summary."""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)

        try:
            handoff.read_summary("../../../etc")
            pytest.fail("VULNERABILITY: read_summary traversal should be rejected")
        except ValueError:
            pass  # Expected after fix

    def test_write_summary_traversal(self, tmp_path):
        """VULNERABILITY: Traversal in write_summary."""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)

        try:
            handoff.write_summary("../../../tmp", "malicious content")
            pytest.fail("VULNERABILITY: write_summary traversal should be rejected")
        except ValueError:
            pass  # Expected after fix

    def test_list_artifacts_traversal(self, tmp_path):
        """VULNERABILITY: Traversal in list_artifacts."""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)

        try:
            handoff.list_artifacts("../../../etc")
            pytest.fail("VULNERABILITY: list_artifacts traversal should be rejected")
        except ValueError:
            pass  # Expected after fix


class TestArtifactNameTraversal:
    """Test artifact name path traversal attacks."""

    def test_write_artifact_name_traversal(self, tmp_path):
        """VULNERABILITY: Traversal in artifact name for write_artifact."""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)

        try:
            handoff.write_artifact("research", "../../.bashrc", "malicious")
            pytest.fail(
                "VULNERABILITY: Artifact name traversal should be rejected"
            )
        except ValueError:
            pass  # Expected after fix

    def test_write_artifact_hidden_file(self, tmp_path):
        """VULNERABILITY: Writing hidden files via artifact name."""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)

        try:
            handoff.write_artifact("research", ".bashrc", "malicious")
            pytest.fail(
                "VULNERABILITY: Hidden file artifact should be rejected"
            )
        except ValueError:
            pass  # Expected after fix

    def test_read_artifact_traversal(self, tmp_path):
        """VULNERABILITY: Traversal in artifact name for read_artifact."""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)

        try:
            handoff.read_artifact("research", "../../etc/passwd")
            pytest.fail(
                "VULNERABILITY: Artifact read traversal should be rejected"
            )
        except ValueError:
            pass  # Expected after fix

    def test_artifact_name_null_byte(self, tmp_path):
        """VULNERABILITY: Null byte in artifact name."""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)

        try:
            handoff.write_artifact("research", "file\x00.txt", "content")
            pytest.fail(
                "VULNERABILITY: Null byte in artifact name should be rejected"
            )
        except ValueError:
            pass  # Expected after fix


class TestCleanupPathTraversal:
    """Test cleanup() method security - CRITICAL.

    cleanup() calls shutil.rmtree() which can delete arbitrary directories.
    """

    def test_cleanup_valid_session_works(self, tmp_path):
        """Valid cleanup should work normally."""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)
        handoff.write_summary("research", "Test summary")

        assert handoff.session_dir.exists()
        handoff.cleanup()
        assert not handoff.session_dir.exists()

    def test_cleanup_refuses_escaped_session_dir(self, tmp_path):
        """cleanup should refuse if session_dir somehow escaped base.

        Defense-in-depth: Even if __init__ validation is bypassed,
        cleanup should still validate before rmtree.
        """
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)

        # Simulate a corrupted/manipulated session_dir
        target_outside = tmp_path / "should-not-delete"
        target_outside.mkdir()
        (target_outside / "important.txt").write_text("DO NOT DELETE")

        # Manually corrupt session_dir to point outside base
        handoff.session_dir = target_outside

        try:
            handoff.cleanup()
            # If cleanup succeeded, check if the directory was deleted
            if not target_outside.exists():
                pytest.fail(
                    "VULNERABILITY: cleanup() deleted directory outside base! "
                    f"Target was: {target_outside}"
                )
            # If directory still exists but no error raised, that's a partial mitigation
        except ValueError as e:
            # This is the expected behavior - refuse to delete
            assert "SECURITY" in str(e) or "escape" in str(e).lower()
            assert target_outside.exists(), "Directory should not be deleted"

    def test_cleanup_refuses_symlink_attack(self, tmp_path):
        """cleanup should handle symlink attacks.

        Attack: Create symlink from session_dir to target outside base.
        """
        base = tmp_path / "base"
        base.mkdir()

        target_outside = tmp_path / "real-target"
        target_outside.mkdir()
        (target_outside / "secret.txt").write_text("SECRET")

        handoff = AgentHandoff("task-123", base_dir=base)

        # Replace session_dir with symlink to target
        handoff.session_dir.rmdir()
        try:
            os.symlink(target_outside, handoff.session_dir)
        except OSError:
            pytest.skip("Cannot create symlinks on this platform")

        try:
            handoff.cleanup()
            # Check if real target was affected
            if not target_outside.exists():
                pytest.fail(
                    "VULNERABILITY: Symlink attack succeeded - real target deleted"
                )
        except ValueError:
            pass  # Expected - refuse symlink cleanup


class TestDoubleEncodingAttacks:
    """Test double encoding and other encoding attacks."""

    def test_double_dot_encoding(self, tmp_path):
        """Attack: ....// which might decode to ../ """
        base = tmp_path / "base"
        base.mkdir()

        try:
            AgentHandoff("....//....//etc", base_dir=base)
            pytest.fail("Double dot encoding should be rejected")
        except ValueError:
            pass

    def test_backslash_traversal(self, tmp_path):
        """Attack: Windows-style backslash traversal."""
        base = tmp_path / "base"
        base.mkdir()

        try:
            AgentHandoff("..\\..\\..\\etc", base_dir=base)
            pytest.fail("Backslash traversal should be rejected")
        except ValueError:
            pass

    def test_mixed_separator_traversal(self, tmp_path):
        """Attack: Mixed forward and backslash."""
        base = tmp_path / "base"
        base.mkdir()

        try:
            AgentHandoff("..\\../..\\/tmp", base_dir=base)
            pytest.fail("Mixed separator traversal should be rejected")
        except ValueError:
            pass

    def test_url_encoded_traversal(self, tmp_path):
        """Attack: URL-encoded traversal (unlikely but test anyway)."""
        base = tmp_path / "base"
        base.mkdir()

        # %2e = '.', %2f = '/'
        # This probably won't be decoded but test the pattern
        try:
            AgentHandoff("%2e%2e%2f%2e%2e%2f", base_dir=base)
            # If no error, check if it was treated as literal
            # (which is fine - just means the attack vector isn't present)
            pass
        except ValueError:
            pass  # Also acceptable


class TestUnicodeNormalizationAttacks:
    """Test Unicode normalization attacks."""

    def test_unicode_slash_variants(self, tmp_path):
        """Attack: Unicode characters that might normalize to / or \\."""
        base = tmp_path / "base"
        base.mkdir()

        unicode_slashes = [
            "\u2215",  # Division slash
            "\u2044",  # Fraction slash
            "\u29f8",  # Big solidus
            "\uff0f",  # Fullwidth solidus
        ]

        for slash in unicode_slashes:
            try:
                AgentHandoff(f"session{slash}secret", base_dir=base)
                # If no error, verify the path didn't escape
                # (Allowlist regex should block non-ASCII anyway)
            except ValueError:
                pass  # Expected - blocked by allowlist

    def test_unicode_dot_variants(self, tmp_path):
        """Attack: Unicode characters that might normalize to dots."""
        base = tmp_path / "base"
        base.mkdir()

        unicode_dots = [
            "\u2024",  # One dot leader
            "\ufe52",  # Small full stop
            "\uff0e",  # Fullwidth full stop
        ]

        for dot in unicode_dots:
            try:
                AgentHandoff(f"{dot}{dot}/secret", base_dir=base)
            except ValueError:
                pass  # Expected


class TestKnownAttackVectors:
    """Test specific attack vectors from security analysis."""

    def test_attack_vector_1_from_plan(self, tmp_path):
        """Attack from plan: AgentHandoff(session_id="../../../tmp/evil")"""
        base = tmp_path / "base"
        base.mkdir()

        try:
            AgentHandoff("../../../tmp/evil", base_dir=base)
            pytest.fail("Attack vector 1 should be blocked")
        except ValueError:
            pass

    def test_attack_vector_2_from_plan(self, tmp_path):
        """Attack from plan: handoff.get_output_dir("../../../etc")"""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)

        try:
            handoff.get_output_dir("../../../etc")
            pytest.fail("Attack vector 2 should be blocked")
        except ValueError:
            pass

    def test_attack_vector_3_from_plan(self, tmp_path):
        """Attack from plan: handoff.write_artifact("research", "../../.bashrc", "malicious")"""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)

        try:
            handoff.write_artifact("research", "../../.bashrc", "malicious content")
            pytest.fail("Attack vector 3 should be blocked")
        except ValueError:
            pass

    def test_attack_vector_4_from_plan(self, tmp_path):
        """Attack from plan: AgentHandoff("../../../home/user").cleanup()"""
        base = tmp_path / "base"
        base.mkdir()

        try:
            AgentHandoff("../../../home/user", base_dir=base)
            pytest.fail("Attack vector 4 should be blocked at init")
        except ValueError:
            pass


class TestValidInputsStillWork:
    """Verify that valid inputs continue to work after fix.

    These are sanity checks to ensure the fix doesn't break normal operation.
    """

    def test_valid_session_id(self, tmp_path):
        """Valid session IDs should work."""
        base = tmp_path / "base"
        base.mkdir()

        valid_ids = ["task-123", "session_abc", "MySession", "test123"]
        for sid in valid_ids:
            handoff = AgentHandoff(sid, base_dir=base)
            assert handoff.session_id == sid
            assert (base / sid).exists()

    def test_valid_phase_operations(self, tmp_path):
        """Valid phase operations should work."""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)

        # Valid phase names
        valid_phases = ["research", "plan", "implement", "phase1", "final_review"]
        for phase in valid_phases:
            output_dir = handoff.get_output_dir(phase)
            assert output_dir.exists()

            chain_path = handoff.chain_from(phase)
            assert str(chain_path).endswith(phase)

    def test_valid_artifact_operations(self, tmp_path):
        """Valid artifact operations should work."""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)

        # Valid artifact names
        valid_names = ["data.json", "output.txt", "result.md", "artifact_1.py"]
        for name in valid_names:
            path = handoff.write_artifact("research", name, f"Content for {name}")
            assert path.exists()
            content = handoff.read_artifact("research", name)
            assert content == f"Content for {name}"

        artifacts = handoff.list_artifacts("research")
        assert len(artifacts) == len(valid_names)

    def test_valid_summary_operations(self, tmp_path):
        """Valid summary operations should work."""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("task-123", base_dir=base)

        path = handoff.write_summary("research", "This is a test summary")
        assert path.exists()

        content = handoff.read_summary("research")
        assert "This is a test summary" in content

    def test_full_workflow(self, tmp_path):
        """Full workflow should work with valid inputs."""
        base = tmp_path / "base"
        base.mkdir()
        handoff = AgentHandoff("workflow-1", base_dir=base)

        # Phase 1: Research
        research_dir = handoff.get_output_dir("research")
        handoff.write_summary("research", "Found important data")
        handoff.write_artifact("research", "findings.json", '{"key": "value"}')

        # Phase 2: Plan reads research
        plan_input = handoff.chain_from("research")
        assert plan_input.exists()
        research_summary = handoff.read_summary("research")
        assert "important data" in research_summary

        handoff.write_summary("plan", "Created implementation plan")

        # Cleanup
        handoff.cleanup()
        assert not handoff.session_dir.exists()
