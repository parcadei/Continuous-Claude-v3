#!/usr/bin/env python3
"""Unit tests for math_plot.py - Math visualization script.

Tests for:
- 2D function plotting (matplotlib)
- 3D surface plotting (plotly)
- LaTeX equation rendering
"""

import os
import pytest


class TestPlot2D:
    """Tests for 2D function plotting."""

    def test_plot_sin(self, tmp_path):
        """Test plotting sin(x) generates a valid PNG file."""
        from scripts.math_plot import plot_2d

        output = tmp_path / "sin.png"
        result = plot_2d("sin(x)", "x", -10, 10, str(output))

        assert result["success"] is True
        assert output.exists()
        assert output.stat().st_size > 0

    def test_plot_polynomial(self, tmp_path):
        """Test plotting a polynomial."""
        from scripts.math_plot import plot_2d

        output = tmp_path / "poly.png"
        result = plot_2d("x**2 - 2*x + 1", "x", -5, 5, str(output))

        assert result["success"] is True
        assert output.exists()

    def test_plot_with_custom_points(self, tmp_path):
        """Test plotting with custom number of points."""
        from scripts.math_plot import plot_2d

        output = tmp_path / "custom.png"
        result = plot_2d("cos(x)", "x", 0, 6.28, str(output), num_points=200)

        assert result["success"] is True
        assert output.exists()

    def test_plot_invalid_expr(self, tmp_path):
        """Test that invalid expressions return success=False."""
        from scripts.math_plot import plot_2d

        output = tmp_path / "invalid.png"
        result = plot_2d("invalid_func(x)", "x", -10, 10, str(output))

        assert result["success"] is False
        assert "error" in result

    def test_plot_with_title(self, tmp_path):
        """Test plotting with a custom title."""
        from scripts.math_plot import plot_2d

        output = tmp_path / "titled.png"
        result = plot_2d("exp(-x**2)", "x", -3, 3, str(output), title="Gaussian")

        assert result["success"] is True
        assert output.exists()

    def test_plot_trig_functions(self, tmp_path):
        """Test plotting trigonometric functions."""
        from scripts.math_plot import plot_2d

        output = tmp_path / "tan.png"
        # Avoid discontinuities by limiting range
        result = plot_2d("tan(x)", "x", -1.5, 1.5, str(output))

        assert result["success"] is True
        assert output.exists()


class TestPlot3D:
    """Tests for 3D surface plotting."""

    def test_plot_surface(self, tmp_path):
        """Test plotting a 3D surface generates a valid HTML file."""
        from scripts.math_plot import plot_3d

        output = tmp_path / "surface.html"
        result = plot_3d("x**2 + y**2", "x", "y", 5, str(output))

        assert result["success"] is True
        assert output.exists()
        assert output.stat().st_size > 0

    def test_plot_saddle(self, tmp_path):
        """Test plotting a saddle surface."""
        from scripts.math_plot import plot_3d

        output = tmp_path / "saddle.html"
        result = plot_3d("x**2 - y**2", "x", "y", 3, str(output))

        assert result["success"] is True
        assert output.exists()

    def test_plot_wave(self, tmp_path):
        """Test plotting a wave surface."""
        from scripts.math_plot import plot_3d

        output = tmp_path / "wave.html"
        result = plot_3d("sin(x) * cos(y)", "x", "y", 6.28, str(output))

        assert result["success"] is True
        assert output.exists()

    def test_plot_3d_invalid_expr(self, tmp_path):
        """Test that invalid 3D expressions return success=False."""
        from scripts.math_plot import plot_3d

        output = tmp_path / "invalid3d.html"
        result = plot_3d("undefined_func(x, y)", "x", "y", 5, str(output))

        assert result["success"] is False
        assert "error" in result

    def test_plot_3d_with_custom_resolution(self, tmp_path):
        """Test 3D plotting with custom grid resolution."""
        from scripts.math_plot import plot_3d

        output = tmp_path / "highres.html"
        result = plot_3d("x**2 + y**2", "x", "y", 5, str(output), resolution=100)

        assert result["success"] is True
        assert output.exists()

    def test_plot_3d_with_colorscale(self, tmp_path):
        """Test 3D plotting with custom colorscale."""
        from scripts.math_plot import plot_3d

        output = tmp_path / "colored.html"
        result = plot_3d(
            "sin(sqrt(x**2 + y**2))", "x", "y", 10, str(output),
            colorscale="Plasma"
        )

        assert result["success"] is True
        assert output.exists()


class TestRenderLatex:
    """Tests for LaTeX equation rendering."""

    def test_render_simple_equation(self, tmp_path):
        """Test rendering a simple LaTeX equation."""
        from scripts.math_plot import render_latex

        output = tmp_path / "eq.png"
        result = render_latex(r"E = mc^2", str(output))

        assert result["success"] is True
        assert output.exists()
        assert output.stat().st_size > 0

    def test_render_integral(self, tmp_path):
        """Test rendering an integral."""
        from scripts.math_plot import render_latex

        output = tmp_path / "integral.png"
        result = render_latex(r"\int e^{-x^2} dx", str(output))

        assert result["success"] is True
        assert output.exists()

    def test_render_complex_equation(self, tmp_path):
        """Test rendering a complex equation with multiple symbols."""
        from scripts.math_plot import render_latex

        output = tmp_path / "complex.png"
        latex = r"\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}"
        result = render_latex(latex, str(output))

        assert result["success"] is True
        assert output.exists()

    def test_render_with_custom_dpi(self, tmp_path):
        """Test rendering with custom DPI setting."""
        from scripts.math_plot import render_latex

        output = tmp_path / "highdpi.png"
        result = render_latex(r"x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}", str(output), dpi=300)

        assert result["success"] is True
        assert output.exists()

    def test_render_matrix(self, tmp_path):
        """Test rendering matrix-like notation in LaTeX.

        Note: matplotlib's mathtext does not support full LaTeX environments
        like \\begin{pmatrix}. Use simple notation instead.
        """
        from scripts.math_plot import render_latex

        output = tmp_path / "matrix.png"
        # Use simple fraction/expression instead of matrix environment
        # (matplotlib mathtext doesn't support \begin{pmatrix})
        latex = r"A = \left(\frac{a}{b}\right)"
        result = render_latex(latex, str(output))

        assert result["success"] is True
        assert output.exists()

    def test_render_with_custom_fontsize(self, tmp_path):
        """Test rendering with custom font size."""
        from scripts.math_plot import render_latex

        output = tmp_path / "large.png"
        result = render_latex(r"\nabla \times \mathbf{E}", str(output), fontsize=30)

        assert result["success"] is True
        assert output.exists()


class TestMultipleFunctions:
    """Tests for plotting multiple functions."""

    def test_plot_multiple_2d(self, tmp_path):
        """Test plotting multiple 2D functions on the same plot."""
        from scripts.math_plot import plot_2d_multi

        output = tmp_path / "multi.png"
        expressions = ["sin(x)", "cos(x)", "sin(x)**2"]
        result = plot_2d_multi(expressions, "x", -6.28, 6.28, str(output))

        assert result["success"] is True
        assert output.exists()

    def test_plot_multiple_with_labels(self, tmp_path):
        """Test plotting multiple functions with custom labels."""
        from scripts.math_plot import plot_2d_multi

        output = tmp_path / "labeled.png"
        expressions = ["x**2", "x**3"]
        labels = ["Quadratic", "Cubic"]
        result = plot_2d_multi(
            expressions, "x", -2, 2, str(output),
            labels=labels
        )

        assert result["success"] is True
        assert output.exists()


class TestCLI:
    """Tests for CLI interface."""

    def test_cli_help(self):
        """Test that CLI help works."""
        import subprocess

        result = subprocess.run(
            ["python", "scripts/math_plot.py", "--help"],
            capture_output=True,
            text=True,
            cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit"
        )

        assert result.returncode == 0
        assert "plot2d" in result.stdout or "usage" in result.stdout.lower()

    def test_cli_plot2d(self, tmp_path):
        """Test CLI plot2d command."""
        import subprocess

        output = tmp_path / "cli_sin.png"
        result = subprocess.run(
            [
                "python", "scripts/math_plot.py",
                "plot2d", "sin(x)",
                "--var", "x",
                "--range", "-10", "10",
                "--output", str(output)
            ],
            capture_output=True,
            text=True,
            cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit"
        )

        assert result.returncode == 0
        assert output.exists()

    def test_cli_latex(self, tmp_path):
        """Test CLI latex command."""
        import subprocess

        output = tmp_path / "cli_eq.png"
        result = subprocess.run(
            [
                "python", "scripts/math_plot.py",
                "latex", r"E = mc^2",
                "--output", str(output)
            ],
            capture_output=True,
            text=True,
            cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit"
        )

        assert result.returncode == 0
        assert output.exists()
