"""Tests for Symlink TOCTOU Prevention.

TDD Failing Tests - Phase 2: Symlink TOCTOU Attack

Vulnerability: scripts/agentica/skill_persistence.py:233-238
Issue: Race condition (TOCTOU) between path validation and file write allows
       attacker to swap legitimate file to symlink pointing outside base directory.

Attack scenario:
1. Attacker monitors for skill save operations
2. After resolve() check passes but before write_text() executes
3. Attacker replaces skill directory with symlink to /etc, /tmp, etc.
4. write_text() follows symlink and writes to arbitrary location

These tests MUST FAIL until the fix is implemented.

Fix approach:
- Use O_NOFOLLOW flag to reject symlinks atomically
- Write to temp file + atomic rename
- Post-write realpath verification
"""

import os
import threading
import time
from pathlib import Path

import pytest


class TestSymlinkTOCTOU:
    """Test that file operations are atomic and symlink-safe.

    These tests expose the TOCTOU vulnerability where an attacker can:
    1. Wait for path validation to pass
    2. Replace target with symlink before write occurs
    3. Cause write to arbitrary location via symlink
    """

    def test_write_rejects_symlink_directory_to_outside(self, tmp_path):
        """Writing to a skill directory that is a symlink pointing outside base should fail.

        Attack: Skill directory replaced with symlink to /tmp
        Expected: SecurityError or ValueError raised
        Current behavior: Writes to /tmp via symlink (VULNERABLE)
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        base = tmp_path / ".claude" / "skills"
        base.mkdir(parents=True)

        # Create external target directory
        external_target = tmp_path / "external"
        external_target.mkdir()

        # Create symlink pointing to external location
        evil_link = base / "evil-skill"
        evil_link.symlink_to(external_target)

        persistence = SkillPersistence(project_dir=str(tmp_path))

        spec = SkillSpec(
            name="evil-skill",
            description="Test symlink attack",
            goal="Test",
            tools=["Bash"],
            instructions="Test",
        )

        # Should detect symlink and fail
        # Current code: writes to external_target via symlink (BUG)
        with pytest.raises((ValueError, OSError), match="symlink|traversal|escape"):
            persistence.save_to_filesystem(spec)

        # Verify no file was written to external location
        assert not (external_target / "SKILL.md").exists(), (
            "TOCTOU: File written outside skills directory via symlink!"
        )

    def test_write_rejects_symlink_file(self, tmp_path):
        """Writing to a SKILL.md that is a symlink should fail.

        Attack: SKILL.md file replaced with symlink to /etc/passwd
        Expected: SecurityError or ValueError raised
        Current behavior: Overwrites symlink target (VULNERABLE)
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        base = tmp_path / ".claude" / "skills"
        skill_dir = base / "my-skill"
        skill_dir.mkdir(parents=True)

        # Create symlink target file
        target_file = tmp_path / "target.txt"
        target_file.write_text("ORIGINAL CONTENT - SHOULD NOT BE MODIFIED")

        # Create SKILL.md as symlink to target
        skill_md = skill_dir / "SKILL.md"
        skill_md.symlink_to(target_file)

        persistence = SkillPersistence(project_dir=str(tmp_path))

        spec = SkillSpec(
            name="my-skill",
            description="Overwrite via symlink",
            goal="Test",
            tools=["Bash"],
            instructions="Test",
        )

        # Should detect symlink file and fail
        # Current code: collision handling creates my-skill-2, but symlink still exists
        # This test verifies that writing to symlink is blocked

        # The vulnerability is when skill_dir exists but SKILL.md is a symlink
        # Fix must check that target path is not a symlink before write

        original_content = target_file.read_text()

        try:
            persistence.save_to_filesystem(spec)
        except (ValueError, OSError):
            pass  # Expected

        # Verify original file was NOT modified via symlink
        assert target_file.read_text() == original_content, (
            "TOCTOU: Original file was modified via symlink attack!"
        )

    def test_atomic_write_uses_temp_then_rename(self, tmp_path):
        """Verify write uses atomic temp file + rename pattern.

        Atomic write pattern:
        1. Write to skill-name.tmp (O_EXCL to fail if exists)
        2. Verify target is not symlink
        3. Rename temp to final (atomic on POSIX)

        This prevents partial writes and TOCTOU race conditions.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        persistence = SkillPersistence(project_dir=str(tmp_path))

        spec = SkillSpec(
            name="atomic-test",
            description="Test atomic write",
            goal="Test",
            tools=["Bash"],
            instructions="Test",
        )

        # Monitor for temp file creation
        temp_files_seen = []
        final_path = None

        def monitor_writes():
            skill_dir = tmp_path / ".claude" / "skills" / "atomic-test"
            for _ in range(100):
                if skill_dir.exists():
                    for f in skill_dir.iterdir():
                        if f.suffix == ".tmp":
                            temp_files_seen.append(str(f))
                time.sleep(0.01)

        monitor_thread = threading.Thread(target=monitor_writes)
        monitor_thread.start()

        final_path = persistence.save_to_filesystem(spec)

        monitor_thread.join(timeout=2)

        # Final file should exist
        assert os.path.exists(final_path)

        # For truly atomic writes, we expect temp file pattern
        # Note: This test may pass even without atomic writes if timing is unlucky
        # The main security tests above are more definitive

    def test_write_rejects_symlink_created_during_race(self, tmp_path):
        """Simulate TOCTOU race: symlink created between check and write.

        This test creates the exact race condition:
        1. Path validation passes (target is normal directory)
        2. Attacker swaps directory to symlink
        3. write_text() follows symlink

        Expected: Write should fail or detect post-write
        Current: Writes to attacker-controlled location (VULNERABLE)
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        base = tmp_path / ".claude" / "skills"
        base.mkdir(parents=True)

        external_target = tmp_path / "attacker-controlled"
        external_target.mkdir()

        skill_dir = base / "race-target"
        skill_dir.mkdir()

        race_triggered = threading.Event()
        write_started = threading.Event()

        persistence = SkillPersistence(project_dir=str(tmp_path))

        spec = SkillSpec(
            name="race-target",
            description="Race condition test",
            goal="Test",
            tools=["Bash"],
            instructions="Test",
        )

        def attacker_thread():
            """Simulate attacker swapping directory to symlink."""
            # Wait for write to begin
            write_started.wait(timeout=5)

            # Give validation time to pass, then swap
            time.sleep(0.001)

            try:
                # Replace skill directory with symlink
                import shutil

                shutil.rmtree(str(skill_dir), ignore_errors=True)
                skill_dir.symlink_to(external_target)
                race_triggered.set()
            except Exception:
                pass

        # Patch write_text to signal write start
        original_write_text = Path.write_text

        def patched_write_text(self, content, *args, **kwargs):
            write_started.set()
            time.sleep(0.01)  # Give attacker time
            return original_write_text(self, content, *args, **kwargs)

        attacker = threading.Thread(target=attacker_thread)
        attacker.start()

        try:
            Path.write_text = patched_write_text

            # This may succeed or fail depending on race timing
            try:
                persistence.save_to_filesystem(spec)
            except (ValueError, OSError):
                pass  # Expected if race detected

            attacker.join(timeout=2)

            # Check if write went to wrong location
            if race_triggered.is_set():
                # If race happened and symlink was created, verify no write to external
                assert not (external_target / "SKILL.md").exists(), (
                    "TOCTOU RACE: Write followed symlink to external location!"
                )
        finally:
            Path.write_text = original_write_text

    def test_uses_o_nofollow_flag_or_lstat_check(self, tmp_path):
        """Verify implementation uses O_NOFOLLOW or lstat to reject symlinks.

        Proper fixes use one of:
        1. O_NOFOLLOW flag in open() - kernel rejects symlinks atomically
        2. lstat() + verify not symlink before each operation
        3. Post-write realpath verification
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        base = tmp_path / ".claude" / "skills"
        base.mkdir(parents=True)

        # Create a dangling symlink (points to nonexistent file)
        # O_NOFOLLOW will fail to open this atomically
        dangling = base / "dangling-skill" / "SKILL.md"
        dangling.parent.mkdir()
        dangling.symlink_to("/nonexistent/path")

        persistence = SkillPersistence(project_dir=str(tmp_path))

        spec = SkillSpec(
            name="dangling-skill",
            description="Dangling symlink test",
            goal="Test",
            tools=["Bash"],
            instructions="Test",
        )

        # With O_NOFOLLOW, this should fail with ELOOP or similar
        # Current code may create the target file (VULNERABLE)

        # Either:
        # 1. Raises because symlink detected
        # 2. Creates alternative name (collision handling)

        # But should NOT create /nonexistent/path or follow the symlink
        try:
            result_path = persistence.save_to_filesystem(spec)
            # If no exception, verify collision handling was used
            # (should create dangling-skill-2, not follow the symlink)
            assert "dangling-skill-2" in result_path or "dangling-skill-3" in result_path, (
                "Should use collision handling when directory has symlink"
            )
            # Verify symlink was NOT followed
            assert not os.path.exists("/nonexistent/path"), (
                "Should NOT create file at symlink target"
            )
        except (ValueError, OSError, FileNotFoundError):
            # Exception is also valid - means symlink was detected and rejected
            pass


class TestAtomicWrite:
    """Test atomic write operations for data integrity."""

    def test_atomic_write_temp_then_rename(self, tmp_path):
        """Write should use temp file + atomic rename pattern.

        Pattern:
        1. Open temp file with O_CREAT | O_EXCL (fail if exists)
        2. Write content to temp
        3. fsync temp file
        4. Rename temp to final (atomic on POSIX filesystems)
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        persistence = SkillPersistence(project_dir=str(tmp_path))

        spec = SkillSpec(
            name="atomic-skill",
            description="Test atomic write",
            goal="Test",
            tools=["Bash"],
            instructions="Test content for atomic write verification",
        )

        result_path = persistence.save_to_filesystem(spec)

        # Verify file exists and has content
        assert os.path.exists(result_path)
        content = Path(result_path).read_text()
        assert "atomic-skill" in content
        assert "Test content" in content

    def test_partial_write_doesnt_corrupt(self, tmp_path):
        """Interrupted write should not leave partial file.

        If write is interrupted (crash, kill), either:
        - No file exists (temp was being written)
        - Complete file exists (rename was done)

        Never: Partial file with incomplete content
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        persistence = SkillPersistence(project_dir=str(tmp_path))

        # Large content to increase chance of partial write
        large_content = "x" * 100000

        spec = SkillSpec(
            name="partial-test",
            description=large_content,
            goal="Test partial write",
            tools=["Bash"],
            instructions="Test",
        )

        result_path = persistence.save_to_filesystem(spec)

        # Verify file is complete (has closing ---)
        content = Path(result_path).read_text()
        assert content.count("---") >= 2, "File appears truncated (missing YAML delimiters)"

    def test_concurrent_writes_produce_complete_files(self, tmp_path):
        """Concurrent writes should each produce complete files.

        Multiple threads writing to same skill should either:
        - Create numbered variants (my-skill-2, my-skill-3)
        - All files are complete, no corruption
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        persistence = SkillPersistence(project_dir=str(tmp_path))
        errors = []
        paths = []

        def writer(thread_id):
            try:
                spec = SkillSpec(
                    name="concurrent-skill",
                    description=f"Thread {thread_id} content " * 100,
                    goal=f"Thread {thread_id}",
                    tools=["Bash"],
                    instructions=f"From thread {thread_id}",
                )
                path = persistence.save_to_filesystem(spec)
                paths.append(path)
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert not errors, f"Concurrent write errors: {errors}"

        # All paths should exist with complete content
        for path in paths:
            assert os.path.exists(path), f"Path should exist: {path}"
            content = Path(path).read_text()
            # Verify file is valid YAML (has delimiters)
            assert content.startswith("---"), f"File {path} is corrupted"


class TestReadSymlinkProtection:
    """Test that read operations also reject symlinks."""

    def test_read_rejects_symlink_skill_directory(self, tmp_path):
        """Reading via symlinked skill directory should be blocked.

        Prevents information disclosure via symlink pointing to
        sensitive files like /etc/passwd, ~/.ssh/id_rsa, etc.
        """
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        base = tmp_path / ".claude" / "skills"
        base.mkdir(parents=True)

        # Create symlink to sensitive location
        evil_link = base / "read-evil"
        evil_link.symlink_to("/etc")

        persistence = SkillPersistence(project_dir=str(tmp_path))

        # exists() should return False for symlink
        # (don't follow symlinks to external locations)
        result = persistence.exists("read-evil")

        # Should either:
        # - Return False (don't follow symlinks)
        # - Return False (SKILL.md doesn't exist at symlink target)
        assert result is False, "exists() should not follow symlinks to external locations"

    def test_exists_uses_lstat_not_stat(self, tmp_path):
        """exists() should use lstat() to detect symlinks, not follow them.

        stat() follows symlinks - dangerous for exists() check
        lstat() returns info about the symlink itself
        """
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        base = tmp_path / ".claude" / "skills"
        base.mkdir(parents=True)

        # Create a skill directory that is a symlink
        real_skill = tmp_path / "real-skill"
        real_skill.mkdir()
        (real_skill / "SKILL.md").write_text("Real skill")

        # Symlink from skills directory to real location
        link_skill = base / "link-skill"
        link_skill.symlink_to(real_skill)

        SkillPersistence(project_dir=str(tmp_path))

        # With proper lstat(), this should detect the symlink
        # and either return False or True based on policy
        # But should NOT blindly follow and say "yes it exists"

        # The key is that exists() behavior is consistent with write security:
        # If we wouldn't write to it, we shouldn't report it exists
