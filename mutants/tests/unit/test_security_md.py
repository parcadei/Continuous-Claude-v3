"""Tests for SECURITY.md documentation."""
import os
import pytest


class TestSecurityDoc:
    """Tests for SECURITY.md existence and content."""

    def test_security_md_exists(self):
        """SECURITY.md exists at project root."""
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        security_path = os.path.join(project_root, "SECURITY.md")
        assert os.path.exists(security_path), f"SECURITY.md not found at {security_path}"

    def test_security_md_has_threat_model(self):
        """SECURITY.md contains threat model section."""
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        security_path = os.path.join(project_root, "SECURITY.md")
        with open(security_path) as f:
            content = f.read()
        assert "## Threat Model" in content or "# Threat Model" in content

    def test_security_md_has_known_limitations(self):
        """SECURITY.md documents known limitations."""
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        security_path = os.path.join(project_root, "SECURITY.md")
        with open(security_path) as f:
            content = f.read()
        assert "limitation" in content.lower() or "NOT Protected" in content

    def test_security_md_has_red_lines(self):
        """SECURITY.md defines red lines / what not to do."""
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        security_path = os.path.join(project_root, "SECURITY.md")
        with open(security_path) as f:
            content = f.read()
        assert "Red Line" in content or "NEVER" in content or "Never" in content

    def test_security_md_has_path_validation_docs(self):
        """SECURITY.md documents path validation."""
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        security_path = os.path.join(project_root, "SECURITY.md")
        with open(security_path) as f:
            content = f.read()
        assert "path" in content.lower()
        assert "traversal" in content.lower() or "canonicalize" in content.lower()
