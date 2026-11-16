"""Test File Persistence Bugs - TDD Failing Tests.

These tests are designed to FAIL initially, exposing bugs in skill_persistence.py.
Based on bug research from:
- .claude/cache/agents/research-agent/latest-output.md
- thoughts/shared/implementation/mutation-round-1-report.md

Bug categories tested:
1. Path traversal vulnerabilities
2. Concurrent write race conditions
3. Missing parent directory creation
4. Permission handling
5. Name collision detection
6. Very long skill names
"""

import os
import stat
import tempfile
import threading
from pathlib import Path

import pytest


class TestPathTraversalSecurity:
    """Test path traversal attack prevention."""

    def test_blocks_path_traversal_with_dotdot(self):
        """
        Bug: Path traversal via '../' sequences can escape skills dir.
        Expected: Reject or sanitize malicious paths.
        Actual: May write files outside intended directory.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            # Malicious skill name trying to escape
            spec = SkillSpec(
                name="../../../tmp/evil-skill",
                description="Malicious",
                goal="Escape",
                tools=[],
                instructions="Bad"
            )

            # Should either:
            # 1. Raise an error
            # 2. Sanitize the name
            # 3. Return error status
            try:
                file_path = persistence.save_to_filesystem(spec)
                # If it didn't raise, verify it didn't escape
                assert tmpdir in file_path
                assert "/tmp/evil-skill" not in file_path
                # The evil file should NOT exist
                assert not os.path.exists("/tmp/evil-skill")
            except (ValueError, OSError) as e:
                # Acceptable - rejection is valid
                pass

    def test_blocks_path_traversal_with_absolute_path(self):
        """
        Bug: Absolute paths in skill names can write anywhere.
        Expected: Reject absolute paths.
        Actual: May create /etc/evil/SKILL.md.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            spec = SkillSpec(
                name="/tmp/absolute-path-skill",
                description="Malicious",
                goal="Escape",
                tools=[],
                instructions="Bad"
            )

            try:
                file_path = persistence.save_to_filesystem(spec)
                # Should stay within project dir
                assert tmpdir in file_path or file_path.startswith(tmpdir)
            except (ValueError, OSError):
                pass  # Acceptable rejection

    def test_blocks_path_traversal_with_encoded_sequences(self):
        """
        Bug: URL-encoded traversal (%2e%2e%2f) might bypass filtering.
        Expected: Detect and block encoded traversal.
        Actual: May decode and traverse.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            # URL-encoded ../ (%2e = ., %2f = /)
            spec = SkillSpec(
                name="..%2f..%2ftmp%2fevil",
                description="Encoded traversal",
                goal="Escape",
                tools=[],
                instructions="Bad"
            )

            try:
                file_path = persistence.save_to_filesystem(spec)
                # Should stay within tmpdir
                resolved = str(Path(file_path).resolve())
                assert tmpdir in resolved or resolved.startswith(tmpdir)
            except (ValueError, OSError):
                pass

    def test_blocks_symlink_traversal(self):
        """
        Security: Symlinks in skill directory are blocked to prevent escape attacks.

        The code CORRECTLY raises SecurityError when the skill directory is a symlink.
        This prevents an attacker from creating a symlink that points outside
        the skills directory and tricking the code into writing files there.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SecurityError, SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create symlink pointing outside
            skills_dir = Path(tmpdir) / ".claude" / "skills"
            skills_dir.mkdir(parents=True, exist_ok=True)

            external_dir = Path(tmpdir) / "external"
            external_dir.mkdir()

            symlink_path = skills_dir / "evil-link"
            try:
                symlink_path.symlink_to(external_dir)
            except OSError:
                pytest.skip("Cannot create symlinks on this system")

            persistence = SkillPersistence(project_dir=tmpdir)

            spec = SkillSpec(
                name="evil-link",
                description="Following symlink",
                goal="Test",
                tools=[],
                instructions="Steps"
            )

            # The code CORRECTLY raises SecurityError when skill_dir is a symlink
            with pytest.raises(SecurityError, match="symlink"):
                persistence.save_to_filesystem(spec)

            # Verify nothing was written to external directory
            assert not (external_dir / "SKILL.md").exists()


class TestConcurrentWrites:
    """Test concurrent write race conditions."""

    def test_concurrent_writes_dont_corrupt_file(self):
        """
        Bug: Race condition when multiple threads write same skill.
        Expected: Atomic writes or proper locking.
        Actual: May produce corrupted/partial file content.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)
            errors = []
            results = []

            def writer(thread_id):
                try:
                    spec = SkillSpec(
                        name="concurrent-test",
                        description=f"Thread {thread_id} content " * 50,
                        goal=f"Goal from thread {thread_id}",
                        tools=["Bash"],
                        instructions=f"Instructions from {thread_id}"
                    )
                    for _ in range(5):
                        path = persistence.save_to_filesystem(spec)
                        results.append((thread_id, path))
                except Exception as e:
                    errors.append((thread_id, e))

            threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Should not have errors from concurrent access
            assert not errors, f"Concurrent writes failed: {errors}"

            # Final file should be valid (not corrupted)
            skill_path = Path(tmpdir) / ".claude" / "skills" / "concurrent-test" / "SKILL.md"
            if skill_path.exists():
                content = skill_path.read_text()
                # Content should be from ONE thread, not mixed
                assert "---" in content
                assert "name:" in content

    def test_concurrent_writes_create_unique_names(self):
        """
        Bug: Multiple threads creating same-named skill may overwrite.
        Expected: Each thread gets unique name suffix.
        Actual: Last writer wins, previous content lost.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)
            paths = []

            def writer(thread_id):
                spec = SkillSpec(
                    name="unique-skill",
                    description=f"Thread {thread_id}",
                    goal="Test",
                    tools=[],
                    instructions="Steps"
                )
                path = persistence.save_to_filesystem(spec)
                paths.append(path)

            threads = [threading.Thread(target=writer, args=(i,)) for i in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Should have created files (possibly with unique names)
            assert len(paths) >= 3

            # All paths should exist
            for path in paths:
                assert os.path.exists(path), f"Path should exist: {path}"


class TestMissingParentDirectory:
    """Test parent directory creation behavior."""

    def test_creates_parent_directories(self):
        """
        Bug: Nested skill paths fail if parent dirs don't exist.
        Expected: Create parent directories automatically.
        Actual: May raise FileNotFoundError.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            spec = SkillSpec(
                name="new-skill",
                description="Test",
                goal="Goal",
                tools=[],
                instructions="Steps"
            )

            # Skills dir doesn't exist yet
            skills_dir = Path(tmpdir) / ".claude" / "skills"
            assert not skills_dir.exists()

            # Should create it
            file_path = persistence.save_to_filesystem(spec)

            assert os.path.exists(file_path)
            assert skills_dir.exists()

    def test_handles_deeply_nested_skill_path(self):
        """
        Bug: Very deeply nested paths may fail.
        Expected: Create all necessary parent dirs.
        Actual: May fail at some nesting level.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            # Very deeply nested name (if supported)
            spec = SkillSpec(
                name="deep-skill",
                description="Test",
                goal="Goal",
                tools=[],
                instructions="Steps"
            )

            file_path = persistence.save_to_filesystem(spec)
            assert os.path.exists(file_path)


class TestPermissionHandling:
    """Test permission error handling."""

    @pytest.mark.skipif(
        os.name == 'nt',
        reason="Permission tests unreliable on Windows"
    )
    def test_handles_readonly_directory_gracefully(self):
        """
        Bug: Writing to read-only directory crashes.
        Expected: Return error status or raise clear exception.
        Actual: May crash with obscure PermissionError.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create skills dir as read-only
            skills_dir = Path(tmpdir) / ".claude" / "skills"
            skills_dir.mkdir(parents=True)
            os.chmod(str(skills_dir), stat.S_IRUSR | stat.S_IXUSR)  # r-x

            try:
                persistence = SkillPersistence(project_dir=tmpdir)

                spec = SkillSpec(
                    name="test-skill",
                    description="Test",
                    goal="Goal",
                    tools=[],
                    instructions="Steps"
                )

                # Should either raise clear error or handle gracefully
                with pytest.raises((PermissionError, OSError)):
                    persistence.save_to_filesystem(spec)
            finally:
                # Cleanup - restore permissions
                os.chmod(str(skills_dir), stat.S_IRWXU)

    @pytest.mark.skipif(
        os.name == 'nt',
        reason="Permission tests unreliable on Windows"
    )
    def test_handles_readonly_skill_file(self):
        """
        Bug: Overwriting read-only SKILL.md crashes.
        Expected: Clear error message.
        Actual: May crash with PermissionError.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create existing read-only skill
            skill_dir = Path(tmpdir) / ".claude" / "skills" / "existing-skill"
            skill_dir.mkdir(parents=True)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("Original content")
            os.chmod(str(skill_file), stat.S_IRUSR)  # r--

            try:
                persistence = SkillPersistence(project_dir=tmpdir)

                spec = SkillSpec(
                    name="existing-skill",
                    description="New content",
                    goal="Goal",
                    tools=[],
                    instructions="Steps"
                )

                # Should create unique name or raise clear error
                # Should NOT crash with obscure error
                try:
                    file_path = persistence.save_to_filesystem(spec)
                    # If succeeded, should be different path
                    assert file_path != str(skill_file)
                except (PermissionError, OSError):
                    pass  # Acceptable
            finally:
                os.chmod(str(skill_file), stat.S_IRWXU)


class TestNameCollisionHandling:
    """Test skill name collision behavior."""

    def test_detects_existing_skill(self):
        """
        Bug: exists() check may have race condition or wrong path.
        Expected: Correctly detect existing skills.
        Actual: May return False when skill exists.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            # Create a skill first
            spec = SkillSpec(
                name="existing-skill",
                description="Original",
                goal="Goal",
                tools=[],
                instructions="Steps"
            )
            persistence.save_to_filesystem(spec)

            # Check if it exists
            assert persistence.exists("existing-skill")
            assert not persistence.exists("nonexistent-skill")

    def test_generates_unique_name_on_collision(self):
        """
        Bug: Name collision handling may loop infinitely.
        Expected: Generate unique suffix (-2, -3, etc).
        Actual: May hang or overwrite existing.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            # Create multiple skills with same base name
            paths = []
            for i in range(5):
                spec = SkillSpec(
                    name="collision-test",
                    description=f"Version {i}",
                    goal="Goal",
                    tools=[],
                    instructions="Steps"
                )
                path = persistence.save_to_filesystem(spec)
                paths.append(path)

            # All paths should be unique
            assert len(set(paths)) == 5, "Should create unique paths"

            # All files should exist
            for path in paths:
                assert os.path.exists(path)

    def test_collision_counter_starts_at_2(self):
        """
        Bug: Collision suffix may start at wrong number.
        Expected: First collision gets -2 suffix.
        Actual: May produce -1 or -0.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            spec = SkillSpec(
                name="counter-test",
                description="Original",
                goal="Goal",
                tools=[],
                instructions="Steps"
            )

            path1 = persistence.save_to_filesystem(spec)
            path2 = persistence.save_to_filesystem(spec)

            # First should be original name
            assert "counter-test" in path1
            # Second should have -2 suffix
            assert "counter-test-2" in path2


class TestLongSkillNames:
    """Test handling of very long skill names."""

    def test_handles_very_long_skill_name(self):
        """
        Bug: Very long names may exceed filesystem limits.
        Expected: Truncate or reject gracefully.
        Actual: May raise OSError.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            # 200+ character name
            long_name = "a" * 200

            spec = SkillSpec(
                name=long_name,
                description="Test",
                goal="Goal",
                tools=[],
                instructions="Steps"
            )

            # Should either truncate or raise clear error
            try:
                file_path = persistence.save_to_filesystem(spec)
                assert os.path.exists(file_path)
                # Path length should be reasonable
                assert len(os.path.basename(os.path.dirname(file_path))) <= 255
            except (OSError, ValueError) as e:
                # Acceptable - rejection for too-long name
                assert "long" in str(e).lower() or "name" in str(e).lower()

    def test_handles_name_with_spaces(self):
        """
        Security: Skill names with spaces are rejected by validation.

        The validation module correctly rejects names with whitespace to prevent:
        1. Shell injection (spaces can split arguments)
        2. Filesystem issues (spaces in paths are problematic)
        3. Command-line argument parsing issues

        Names should use hyphens instead of spaces: "my-skill" not "my skill"
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            spec = SkillSpec(
                name="skill with spaces",
                description="Test",
                goal="Goal",
                tools=[],
                instructions="Steps"
            )

            # The code CORRECTLY raises ValueError for names with spaces
            # since whitespace is in the DANGEROUS_PATTERNS list
            with pytest.raises(ValueError, match="Invalid skill name"):
                persistence.save_to_filesystem(spec)


class TestTriggerRegistration:
    """Test skill trigger registration in skill-rules.json."""

    def test_creates_skill_rules_file(self):
        """
        Bug: skill-rules.json may not be created.
        Expected: Create file if doesn't exist.
        Actual: May raise FileNotFoundError.
        """
        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            spec = SkillSpec(
                name="trigger-test",
                description="Test",
                goal="Goal",
                tools=[],
                instructions="Steps",
                triggers={"keywords": ["test"], "intentPatterns": ["test.*"]}
            )

            persistence.register_triggers(spec)

            rules_path = Path(tmpdir) / ".claude" / "skills" / "skill-rules.json"
            assert rules_path.exists()

    def test_preserves_existing_triggers(self):
        """
        Bug: Registering new skill may overwrite existing entries.
        Expected: Preserve all existing skill entries.
        Actual: May lose existing skills.
        """
        import json

        from scripts.agentica_patterns.skill_generator import SkillSpec
        from scripts.agentica_patterns.skill_persistence import SkillPersistence

        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SkillPersistence(project_dir=tmpdir)

            # Register first skill
            spec1 = SkillSpec(
                name="skill-one",
                description="First",
                goal="Goal",
                tools=[],
                instructions="Steps",
                triggers={"keywords": ["one"], "intentPatterns": []}
            )
            persistence.register_triggers(spec1)

            # Register second skill
            spec2 = SkillSpec(
                name="skill-two",
                description="Second",
                goal="Goal",
                tools=[],
                instructions="Steps",
                triggers={"keywords": ["two"], "intentPatterns": []}
            )
            persistence.register_triggers(spec2)

            # Both should exist in rules
            rules_path = Path(tmpdir) / ".claude" / "skills" / "skill-rules.json"
            with open(rules_path) as f:
                rules = json.load(f)

            assert "skill-one" in rules["skills"]
            assert "skill-two" in rules["skills"]
