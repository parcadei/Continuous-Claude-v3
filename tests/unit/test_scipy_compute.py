#!/usr/bin/env python3
"""Tests for scipy_compute.py - SciPy computation CLI wrapper.

TDD: These tests written FIRST to validate the existing implementation.

Note: scipy_compute uses math_base which wraps results in:
    {"result": <value>, "metadata": {...}}
structure. Tests check both result and relevant metadata.

Categories covered:
- optimize: minimize, root, curve_fit, linprog, etc.
- integrate: quad, dblquad, odeint, solve_ivp, etc.
- signal: convolve, correlate, butter, filtfilt, etc.
- stats: distributions (norm, t, chi2), tests (ttest, kstest), descriptive stats
- interpolate: interp1d, spline, griddata
"""

import pytest
import sys
from pathlib import Path
import numpy as np

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


# =============================================================================
# OPTIMIZE CATEGORY TESTS
# =============================================================================

class TestOptimize:
    """Tests for basic optimization functions."""

    def test_minimize_quadratic(self):
        """Minimize x^2 + 2x should find x = -1."""
        from scipy_compute import cmd_minimize

        output = cmd_minimize("x**2 + 2*x", "5")
        assert output["metadata"]["success"] is True
        assert pytest.approx(output["result"], abs=1e-6) == -1.0
        assert pytest.approx(output["metadata"]["fun"], abs=1e-6) == -1.0

    def test_minimize_multivariate(self):
        """Minimize x[0]^2 + x[1]^2 should find (0, 0)."""
        from scipy_compute import cmd_minimize

        output = cmd_minimize("x[0]**2 + x[1]**2", "1,1")
        assert output["metadata"]["success"] is True
        assert pytest.approx(output["result"][0], abs=1e-4) == 0.0
        assert pytest.approx(output["result"][1], abs=1e-4) == 0.0

    def test_minimize_nelder_mead(self):
        """Test minimize with Nelder-Mead method."""
        from scipy_compute import cmd_minimize

        output = cmd_minimize("x**2 - 4*x + 4", "0", method="Nelder-Mead")
        assert output["metadata"]["success"] is True
        assert pytest.approx(output["result"], abs=1e-4) == 2.0

    def test_minimize_scalar_brent(self):
        """Test scalar minimization with Brent's method."""
        from scipy_compute import cmd_minimize_scalar

        output = cmd_minimize_scalar("x**2 - 4*x")
        assert output["metadata"]["success"] is True
        assert pytest.approx(output["result"], abs=1e-6) == 2.0
        assert pytest.approx(output["metadata"]["fun"], abs=1e-6) == -4.0

    def test_root_cubic(self):
        """Find root of x^3 - x - 2 near 1.5."""
        from scipy_compute import cmd_root

        # Root requires array input format (comma-separated even for single value)
        output = cmd_root("x**3 - x - 2", "1.5,")
        assert output["metadata"]["success"] is True
        # The real root is approximately 1.5214
        assert pytest.approx(output["result"][0], abs=1e-4) == 1.5214

    def test_root_system(self):
        """Solve system: x[0]^2 + x[1] - 1 = 0, x[0] - x[1] = 0."""
        from scipy_compute import cmd_root

        output = cmd_root("x[0]**2 + x[1] - 1, x[0] - x[1]", "0.5,0.5")
        assert output["metadata"]["success"] is True
        # Solution: x[0] = x[1], and x[0]^2 + x[0] = 1, so x[0] = (-1 + sqrt(5))/2 ~ 0.618
        x0, x1 = output["result"]
        assert pytest.approx(x0, abs=1e-4) == pytest.approx(x1, abs=1e-4)
        assert pytest.approx(x0**2 + x1, abs=1e-4) == 1.0

    def test_fsolve_nonlinear(self):
        """Test fsolve for system of equations."""
        from scipy_compute import cmd_fsolve

        # Circle: x^2 + y^2 = 1, line: x = y
        output = cmd_fsolve("x[0]**2 + x[1]**2 - 1, x[0] - x[1]", "0.5,0.5")
        x0, x1 = output["result"]
        assert pytest.approx(x0, abs=1e-4) == pytest.approx(x1, abs=1e-4)
        assert pytest.approx(x0**2 + x1**2, abs=1e-4) == 1.0

    def test_brentq_bracketed(self):
        """Find root using Brent's method in bracket [0, 2]."""
        from scipy_compute import cmd_brentq

        # x^3 - 1 = 0, root at x = 1
        output = cmd_brentq("x**3 - 1", "0", "2")
        # Note: converged might be False in metadata even when it works
        assert pytest.approx(output["result"], abs=1e-10) == 1.0

    def test_bisect_simple(self):
        """Find root using bisection method."""
        from scipy_compute import cmd_bisect

        # x^2 - 2 = 0, root at sqrt(2) ~ 1.414
        output = cmd_bisect("x**2 - 2", "1", "2")
        assert pytest.approx(output["result"], abs=1e-6) == np.sqrt(2)

    def test_newton_with_derivative(self):
        """Test Newton's method with provided derivative."""
        from scipy_compute import cmd_newton

        # x^2 - 2 = 0, f'(x) = 2x
        output = cmd_newton("x**2 - 2", "1", fprime="2*x")
        assert pytest.approx(output["result"], abs=1e-6) == np.sqrt(2)


class TestOptimizeFitting:
    """Tests for curve fitting functions."""

    def test_curve_fit_exponential(self):
        """Fit exponential decay: y = a * exp(-b*x)."""
        from scipy_compute import cmd_curve_fit

        # Generate test data: y = 2 * exp(-0.5*x)
        output = cmd_curve_fit(
            "a*exp(-b*x)",
            "0,1,2,3,4",
            "2.0,1.21,0.74,0.45,0.27",
            "1,0.5"
        )
        a, b = output["result"]
        assert pytest.approx(a, abs=0.1) == 2.0
        assert pytest.approx(b, abs=0.1) == 0.5

    def test_curve_fit_polynomial(self):
        """Fit linear function: y = a*x + b."""
        from scipy_compute import cmd_curve_fit

        # y = 2*x + 1
        output = cmd_curve_fit(
            "a*x + b",
            "0,1,2,3,4",
            "1,3,5,7,9",
            "1,0"
        )
        a, b = output["result"]
        assert pytest.approx(a, abs=0.01) == 2.0
        assert pytest.approx(b, abs=0.01) == 1.0


class TestOptimizeAdvanced:
    """Tests for advanced optimization functions."""

    def test_linprog_simple(self):
        """Simple linear programming: minimize -x - 2y subject to x + y <= 4."""
        from scipy_compute import cmd_linprog

        # Minimize c^T x = -x - 2y
        # Subject to: x + y <= 4, 2x + y <= 5
        output = cmd_linprog(
            "-1,-2",
            "[[1,1],[2,1]]",
            "[4,5]"
        )
        assert output["metadata"]["success"] is True
        # Optimal at (0, 4) with value -8 (when y is maximized)
        x = output["result"]
        assert pytest.approx(x[0], abs=0.1) == 0.0
        assert pytest.approx(x[1], abs=0.1) == 4.0

    def test_linprog_with_bounds(self):
        """Linear programming with variable bounds."""
        from scipy_compute import cmd_linprog

        output = cmd_linprog(
            "-1,-1",
            "[[1,2]]",
            "[4]",
            bounds="0,2:0,2"
        )
        assert output["metadata"]["success"] is True

    def test_differential_evolution(self):
        """Global optimization with differential evolution."""
        from scipy_compute import cmd_differential_evolution

        # Rastrigin-like function, minimum at (0, 0)
        output = cmd_differential_evolution(
            "(x[0])**2 + (x[1])**2",
            "-5,5:-5,5",
            maxiter=100
        )
        assert output["metadata"]["success"] is True
        assert pytest.approx(output["result"][0], abs=0.1) == 0.0
        assert pytest.approx(output["result"][1], abs=0.1) == 0.0


# =============================================================================
# INTEGRATE CATEGORY TESTS
# =============================================================================

class TestIntegrate:
    """Tests for basic integration functions."""

    def test_quad_polynomial(self):
        """Integrate x^2 from 0 to 1 should give 1/3."""
        from scipy_compute import cmd_quad

        output = cmd_quad("x**2", "0", "1")
        assert pytest.approx(output["result"], abs=1e-8) == 1/3
        assert output["metadata"]["error"] < 1e-10

    def test_quad_trig(self):
        """Integrate sin(x) from 0 to pi should give 2."""
        from scipy_compute import cmd_quad

        output = cmd_quad("sin(x)", "0", "3.141592653589793")
        assert pytest.approx(output["result"], abs=1e-6) == 2.0

    def test_quad_infinite_bounds(self):
        """Integrate exp(-x^2) from -inf to inf should give sqrt(pi)."""
        from scipy_compute import cmd_quad

        output = cmd_quad("exp(-x**2)", "-inf", "inf")
        assert pytest.approx(output["result"], abs=1e-6) == np.sqrt(np.pi)

    def test_dblquad_simple(self):
        """Double integral of x*y over [0,1] x [0,1] should give 0.25."""
        from scipy_compute import cmd_dblquad

        output = cmd_dblquad("x*y", "0", "1", "0", "1")
        assert pytest.approx(output["result"], abs=1e-6) == 0.25

    def test_dblquad_triangular_region(self):
        """Double integral over triangular region."""
        from scipy_compute import cmd_dblquad

        # Integrate 1 over triangle: 0 <= x <= 1, 0 <= y <= x
        # Area = 0.5
        output = cmd_dblquad("1", "0", "1", "0", "x")
        assert pytest.approx(output["result"], abs=1e-6) == 0.5


class TestIntegrateODE:
    """Tests for ODE integration functions."""

    def test_odeint_exponential_decay(self):
        """Solve dy/dt = -y, y(0) = 1 (exponential decay)."""
        from scipy_compute import cmd_odeint

        # Initial condition must be comma-separated, time in "start,end,n" format
        output = cmd_odeint("-y", "1,", "0,1,11")
        t = output["metadata"]["t"]
        y = output["metadata"]["y"]  # y is in metadata
        # y(t) = exp(-t)
        assert len(t) == 11
        assert pytest.approx(y[0][0], abs=1e-3) == 1.0  # y(0) = 1
        assert pytest.approx(y[-1][0], abs=1e-2) == np.exp(-1.0)  # y(1) ~ 0.368

    def test_solve_ivp_harmonic(self):
        """Solve simple harmonic oscillator: y'' = -y."""
        from scipy_compute import cmd_solve_ivp

        # Transform to system: y[0]' = y[1], y[1]' = -y[0]
        # IC: y(0) = 1, y'(0) = 0
        # Note: y0 must be comma-separated
        output = cmd_solve_ivp(
            "[y[1], -y[0]]",
            "0,6.28",  # One period
            "1,0",  # Two components, so comma-separated works
            t_eval="0,1.57,3.14,4.71,6.28"
        )
        assert output["metadata"]["success"] is True
        y = output["metadata"]["y"]  # y is in metadata, result is None for solve_ivp
        # y[0] should be approximately cos(t)
        assert pytest.approx(y[0][0], abs=0.1) == 1.0  # cos(0) = 1
        assert pytest.approx(y[0][2], abs=0.1) == -1.0  # cos(pi) = -1

    def test_solve_ivp_exponential_growth(self):
        """Solve dy/dt = y, y(0) = 1 (exponential growth)."""
        from scipy_compute import cmd_solve_ivp

        # Single IC must have comma to be parsed as array
        output = cmd_solve_ivp(
            "y",
            "0,1",
            "1,",  # Trailing comma for single-element array
            t_eval="0,0.5,1"
        )
        assert output["metadata"]["success"] is True
        y = output["metadata"]["y"]  # y is in metadata
        # y(1) = e ~ 2.718
        assert pytest.approx(y[0][-1], abs=0.1) == np.e


class TestIntegrateAdvanced:
    """Tests for advanced integration functions."""

    def test_simpson_uniform(self):
        """Simpson's rule integration from samples."""
        from scipy_compute import cmd_simpson

        # Integrate y = x^2 from 0 to 4 using samples
        # Exact integral = 64/3 ~ 21.33
        output = cmd_simpson("0,1,4,9,16", x="0,1,2,3,4")
        assert pytest.approx(output["result"], abs=0.5) == 64/3

    def test_trapezoid_uniform(self):
        """Trapezoidal rule integration from samples."""
        from scipy_compute import cmd_trapezoid

        # Integrate y = x from 0 to 4 using samples
        # Exact integral = 8
        output = cmd_trapezoid("0,1,2,3,4", x="0,1,2,3,4")
        assert pytest.approx(output["result"], abs=0.01) == 8.0

    def test_cumulative_trapezoid(self):
        """Cumulative trapezoidal integration."""
        from scipy_compute import cmd_cumulative_trapezoid

        # Cumulative integral of constant 1 should be [0, 1, 2, 3, ...]
        output = cmd_cumulative_trapezoid("1,1,1,1,1", dx=1.0, initial=0)
        expected = [0.0, 1.0, 2.0, 3.0, 4.0]
        assert len(output["result"]) == 5
        for i, val in enumerate(output["result"]):
            assert pytest.approx(val, abs=0.01) == expected[i]


# =============================================================================
# SIGNAL CATEGORY TESTS
# =============================================================================

class TestSignal:
    """Tests for basic signal processing functions."""

    def test_convolve_simple(self):
        """Test 1D convolution."""
        from scipy_compute import cmd_sig_convolve

        # Convolve [1,2,3] with [1,1]
        output = cmd_sig_convolve("1,2,3", "1,1")
        expected = [1, 3, 5, 3]
        assert len(output["result"]) == 4
        for i, val in enumerate(output["result"]):
            assert pytest.approx(val, abs=1e-10) == expected[i]

    def test_correlate_autocorrelation(self):
        """Test autocorrelation (correlate signal with itself)."""
        from scipy_compute import cmd_sig_correlate

        # Autocorrelation of [1,2,3]
        output = cmd_sig_correlate("1,2,3", "1,2,3")
        # Peak should be at center
        max_idx = output["result"].index(max(output["result"]))
        assert max_idx == 2  # Center of length-5 result

    def test_fftconvolve(self):
        """Test FFT-based convolution."""
        from scipy_compute import cmd_fftconvolve

        output = cmd_fftconvolve("1,2,3", "1,1")
        expected = [1, 3, 5, 3]
        for i, val in enumerate(output["result"]):
            assert pytest.approx(val, abs=1e-10) == expected[i]

    def test_convolve2d(self):
        """Test 2D convolution."""
        from scipy_compute import cmd_convolve2d

        # Simple 2D convolution
        output = cmd_convolve2d("1,2;3,4", "1,0;0,1", mode="full")
        # Should produce 3x3 result
        assert len(output["result"]) == 3
        assert len(output["result"][0]) == 3


class TestSignalFilters:
    """Tests for filter design and application."""

    def test_butter_lowpass(self):
        """Design Butterworth lowpass filter."""
        from scipy_compute import cmd_butter

        output = cmd_butter(4, "0.1", btype="low")
        b, a = output["metadata"]["b"], output["metadata"]["a"]
        # Should have 5 coefficients for 4th order filter
        assert len(b) == 5
        assert len(a) == 5
        # a[0] should be 1.0
        assert pytest.approx(a[0], abs=1e-10) == 1.0

    def test_butter_bandpass(self):
        """Design Butterworth bandpass filter."""
        from scipy_compute import cmd_butter

        output = cmd_butter(2, "0.1,0.3", btype="band")
        # Bandpass doubles the order
        assert len(output["metadata"]["b"]) == 5

    def test_cheby1_filter(self):
        """Design Chebyshev Type I filter."""
        from scipy_compute import cmd_cheby1

        output = cmd_cheby1(4, 0.5, "0.2")
        assert "b" in output["metadata"]
        assert "a" in output["metadata"]

    def test_filtfilt_apply(self):
        """Apply zero-phase filtering."""
        from scipy_compute import cmd_butter, cmd_filtfilt

        # Design filter
        filt = cmd_butter(2, "0.1")

        # Apply to signal (simple sine wave with noise)
        np.random.seed(42)
        signal = ",".join([str(np.sin(0.1*i) + 0.1*np.random.randn()) for i in range(100)])
        b = ",".join([str(x) for x in filt["metadata"]["b"]])
        a = ",".join([str(x) for x in filt["metadata"]["a"]])

        output = cmd_filtfilt(b, a, signal)
        # Result should have same length as input
        assert len(output["result"]) == 100


class TestSignalAdvanced:
    """Tests for advanced signal processing."""

    def test_wiener_filter(self):
        """Test Wiener filter for noise reduction."""
        from scipy_compute import cmd_wiener

        # Apply Wiener filter to noisy signal
        signal = "1,2,3,4,5,6,7,8,9,10"
        output = cmd_wiener(signal, mysize=3)
        assert len(output["result"]) == 10

    def test_medfilt_1d(self):
        """Test 1D median filter."""
        from scipy_compute import cmd_medfilt

        # Median filter should remove outliers
        # Signal: [1, 1, 100, 1, 1] -> [1, 1, 1, 1, 1] with kernel_size=3
        output = cmd_medfilt("1,1,100,1,1", kernel_size=3)
        # Middle value should be reduced from 100
        assert output["result"][2] < 100


# =============================================================================
# STATS CATEGORY TESTS
# =============================================================================

class TestStatsDescriptive:
    """Tests for descriptive statistics."""

    def test_describe_basic(self):
        """Test describe function."""
        from scipy_compute import cmd_describe

        output = cmd_describe("1,2,3,4,5")
        d = output["result"]
        assert d["nobs"] == 5
        assert pytest.approx(d["mean"], abs=1e-10) == 3.0
        assert d["min"] == 1.0
        assert d["max"] == 5.0

    def test_skew_symmetric(self):
        """Symmetric distribution should have skew near 0."""
        from scipy_compute import cmd_skew

        output = cmd_skew("1,2,3,4,5,6,7,8,9")
        assert pytest.approx(output["result"], abs=0.1) == 0.0

    def test_kurtosis_normal(self):
        """Normal distribution should have excess kurtosis near 0."""
        from scipy_compute import cmd_kurtosis

        # Use data that approximates normal distribution
        data = "-2,-1,0,1,2"
        output = cmd_kurtosis(data, fisher=True)
        # Excess kurtosis for this data
        assert abs(output["result"]) < 3.0

    def test_zscore_standardize(self):
        """Z-scores should have mean 0 and std 1."""
        from scipy_compute import cmd_zscore

        output = cmd_zscore("1,2,3,4,5")
        zscores = output["result"]
        assert pytest.approx(np.mean(zscores), abs=1e-10) == 0.0
        assert pytest.approx(np.std(zscores), abs=1e-10) == 1.0

    def test_iqr_simple(self):
        """Test interquartile range."""
        from scipy_compute import cmd_iqr

        # IQR of [1,2,3,4,5,6,7,8,9] should be Q3 - Q1
        output = cmd_iqr("1,2,3,4,5,6,7,8,9")
        assert output["result"] > 0


class TestStatsDistributions:
    """Tests for probability distributions."""

    def test_norm_pdf(self):
        """Test normal PDF at mean should be 1/(sigma*sqrt(2*pi))."""
        from scipy_compute import cmd_norm

        output = cmd_norm("pdf", x="0", loc=0.0, scale=1.0)
        expected = 1.0 / np.sqrt(2 * np.pi)
        assert pytest.approx(output["result"], abs=1e-6) == expected

    def test_norm_cdf(self):
        """Test normal CDF at mean should be 0.5."""
        from scipy_compute import cmd_norm

        output = cmd_norm("cdf", x="0", loc=0.0, scale=1.0)
        assert pytest.approx(output["result"], abs=1e-6) == 0.5

    def test_norm_ppf(self):
        """Test normal PPF: ppf(0.5) should be 0 (the mean)."""
        from scipy_compute import cmd_norm

        output = cmd_norm("ppf", x="0.5", loc=0.0, scale=1.0)
        assert pytest.approx(output["result"], abs=1e-6) == 0.0

    def test_norm_rvs(self):
        """Test random sample generation."""
        from scipy_compute import cmd_norm

        output = cmd_norm("rvs", size=100)
        samples = output["result"]
        assert len(samples) == 100
        # Mean should be close to 0 for standard normal
        assert abs(np.mean(samples)) < 0.5  # Large tolerance for randomness

    def test_t_distribution(self):
        """Test t-distribution PDF."""
        from scipy_compute import cmd_t

        output = cmd_t("pdf", x="0", df=10.0)
        # PDF at 0 should be positive
        assert output["result"] > 0

    def test_chi2_distribution(self):
        """Test chi-square distribution CDF."""
        from scipy_compute import cmd_chi2

        output = cmd_chi2("cdf", x="5", df=5.0)
        # CDF should be between 0 and 1
        assert 0 < output["result"] < 1


class TestStatsTests:
    """Tests for statistical hypothesis tests."""

    def test_ttest_1samp_mean_zero(self):
        """One-sample t-test: test if mean differs from 0."""
        from scipy_compute import cmd_ttest_1samp

        # Data with mean clearly different from 0
        output = cmd_ttest_1samp("10,11,12,13,14", "0")
        # Should reject null hypothesis (p-value < 0.05)
        assert output["result"]["pvalue"] < 0.05

    def test_ttest_ind_different_means(self):
        """Two-sample t-test: compare means of two groups."""
        from scipy_compute import cmd_ttest_ind

        # Two groups with different means
        output = cmd_ttest_ind("1,2,3,4,5", "10,11,12,13,14")
        # Should reject null hypothesis (p-value < 0.05)
        assert output["result"]["pvalue"] < 0.05

    def test_ttest_rel_paired(self):
        """Paired t-test."""
        from scipy_compute import cmd_ttest_rel

        # Before and after treatment
        output = cmd_ttest_rel("1,2,3,4,5", "2,3,4,5,6")
        assert "statistic" in output["result"]
        assert "pvalue" in output["result"]

    def test_chisquare_uniform(self):
        """Chi-square test for uniform distribution."""
        from scipy_compute import cmd_chisquare

        # Observed frequencies close to expected
        output = cmd_chisquare("10,10,10,10,10")
        # Should not reject uniformity
        assert output["result"]["pvalue"] > 0.05

    def test_kstest_normal(self):
        """Kolmogorov-Smirnov test against normal distribution."""
        from scipy_compute import cmd_kstest

        # Generate data that looks roughly normal
        data = "-2,-1,-0.5,0,0.5,1,2"
        output = cmd_kstest(data, "norm")
        assert "statistic" in output["result"]
        assert "pvalue" in output["result"]


class TestStatsCorrelation:
    """Tests for correlation functions."""

    def test_pearsonr_perfect(self):
        """Perfect linear correlation should have r = 1."""
        from scipy_compute import cmd_pearsonr

        output = cmd_pearsonr("1,2,3,4,5", "2,4,6,8,10")
        assert pytest.approx(output["result"]["correlation"], abs=1e-10) == 1.0

    def test_pearsonr_negative(self):
        """Perfect negative correlation should have r = -1."""
        from scipy_compute import cmd_pearsonr

        output = cmd_pearsonr("1,2,3,4,5", "10,8,6,4,2")
        assert pytest.approx(output["result"]["correlation"], abs=1e-10) == -1.0

    def test_spearmanr_monotonic(self):
        """Spearman correlation for monotonic relationship."""
        from scipy_compute import cmd_spearmanr

        output = cmd_spearmanr("1,2,3,4,5", "1,4,9,16,25")
        assert pytest.approx(output["result"]["correlation"], abs=1e-10) == 1.0

    def test_linregress_slope(self):
        """Linear regression slope and intercept."""
        from scipy_compute import cmd_linregress

        # y = 2x + 1
        output = cmd_linregress("1,2,3,4,5", "3,5,7,9,11")
        assert pytest.approx(output["result"]["slope"], abs=1e-10) == 2.0
        assert pytest.approx(output["result"]["intercept"], abs=1e-10) == 1.0


# =============================================================================
# INTERPOLATE CATEGORY TESTS
# =============================================================================

class TestInterpolate:
    """Tests for interpolation functions."""

    def test_interp1d_linear(self):
        """Test linear interpolation."""
        from scipy_compute import cmd_interp1d

        output = cmd_interp1d("0,1,2,3,4", "0,2,4,6,8", "0.5,1.5,2.5,3.5")
        expected = [1.0, 3.0, 5.0, 7.0]
        for i, val in enumerate(output["result"]):
            assert pytest.approx(val, abs=1e-10) == expected[i]

    def test_interp1d_cubic(self):
        """Test cubic interpolation."""
        from scipy_compute import cmd_interp1d

        output = cmd_interp1d("0,1,2,3,4", "0,1,4,9,16", "0.5,1.5,2.5", kind="cubic")
        # Should be close to x^2 behavior
        assert len(output["result"]) == 3
        # Check interpolated values are reasonable
        assert 0 < output["result"][0] < 1

    def test_CubicSpline(self):
        """Test cubic spline interpolation."""
        from scipy_compute import cmd_CubicSpline

        output = cmd_CubicSpline("0,1,2,3,4", "0,1,4,9,16", "0.5,1.5,2.5")
        assert len(output["result"]) == 3

    def test_make_interp_spline(self):
        """Test B-spline interpolation."""
        from scipy_compute import cmd_make_interp_spline

        output = cmd_make_interp_spline("0,1,2,3,4", "0,2,4,6,8", "0.5,1.5,2.5")
        # Linear data should interpolate linearly
        expected = [1.0, 3.0, 5.0]
        for i, val in enumerate(output["result"]):
            assert pytest.approx(val, abs=0.1) == expected[i]


class TestInterpolateAdvanced:
    """Tests for advanced interpolation functions."""

    def test_UnivariateSpline(self):
        """Test UnivariateSpline fitting."""
        from scipy_compute import cmd_UnivariateSpline

        output = cmd_UnivariateSpline("0,1,2,3,4", "0,1,4,9,16", "0.5,1.5,2.5")
        assert len(output["result"]) == 3

    def test_griddata_linear(self):
        """Test 2D griddata interpolation."""
        from scipy_compute import cmd_griddata

        # Sample points and values
        output = cmd_griddata(
            "0,0;0,1;1,0;1,1",  # points
            "0,1,1,2",  # values at points
            "0.5,0.5",  # query point
            method="linear"
        )
        # Value at center should be average = 1.0
        assert pytest.approx(output["result"][0], abs=0.1) == 1.0


# =============================================================================
# CLI AND ERROR HANDLING TESTS
# =============================================================================

class TestCLI:
    """Tests for CLI argument parsing."""

    def test_minimize_with_all_args(self):
        """Test minimize with all optional arguments."""
        from scipy_compute import cmd_minimize

        output = cmd_minimize(
            "x**2",
            "5",
            method="Powell",
            tol=1e-6,
            maxiter=500
        )
        assert output["metadata"]["success"] is True

    def test_quad_with_tolerances(self):
        """Test quad with tolerance arguments."""
        from scipy_compute import cmd_quad

        output = cmd_quad(
            "x**2",
            "0",
            "1",
            epsabs=1e-10,
            epsrel=1e-10,
            limit=100
        )
        assert pytest.approx(output["result"], abs=1e-10) == 1/3


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_root_no_solution_in_bracket(self):
        """Test root finding when no root exists in bracket."""
        from scipy_compute import cmd_brentq

        # x^2 + 1 = 0 has no real roots, brentq returns error dict
        output = cmd_brentq("x**2 + 1", "0", "2")
        # The function should return an error dict since f(a) and f(b) have same sign
        assert "error" in output or output.get("metadata", {}).get("converged") is False

    def test_minimize_convergence_failure(self):
        """Test that convergence info is reported correctly."""
        from scipy_compute import cmd_minimize

        # Very tight tolerance with few iterations may not converge
        output = cmd_minimize("x**4 - x**2", "0.5", maxiter=2)
        # Should still return a result even if not fully converged
        assert "success" in output["metadata"]

    def test_linprog_infeasible(self):
        """Test linear programming with infeasible constraints."""
        from scipy_compute import cmd_linprog

        # x + y <= 1 and x + y >= 2 is infeasible
        output = cmd_linprog(
            "1,1",
            "[[1,1],[-1,-1]]",
            "[1,-2]"
        )
        # Should report failure
        assert output["metadata"]["success"] is False

    def test_single_element_stats(self):
        """Test statistics with minimal data."""
        from scipy_compute import cmd_describe

        # Single element - need comma-separated format
        output = cmd_describe("5,")
        assert output["result"]["nobs"] == 1
        assert output["result"]["mean"] == 5.0


# =============================================================================
# SPECIAL FUNCTIONS TESTS
# =============================================================================

class TestSpecialFunctions:
    """Tests for scipy.special functions."""

    def test_gamma_integers(self):
        """Gamma(n) = (n-1)! for positive integers."""
        from scipy_compute import cmd_sp_gamma

        output = cmd_sp_gamma("5")
        # gamma(5) = 4! = 24
        assert pytest.approx(output["result"], abs=1e-6) == 24.0

    def test_gamma_half(self):
        """Gamma(0.5) = sqrt(pi)."""
        from scipy_compute import cmd_sp_gamma

        output = cmd_sp_gamma("0.5")
        assert pytest.approx(output["result"], abs=1e-6) == np.sqrt(np.pi)

    def test_erf_bounds(self):
        """Error function should be bounded by [-1, 1]."""
        from scipy_compute import cmd_sp_erf

        output_neg = cmd_sp_erf("-10")
        output_pos = cmd_sp_erf("10")
        assert pytest.approx(output_neg["result"], abs=1e-10) == -1.0
        assert pytest.approx(output_pos["result"], abs=1e-10) == 1.0

    def test_erf_zero(self):
        """erf(0) = 0."""
        from scipy_compute import cmd_sp_erf

        output = cmd_sp_erf("0")
        assert pytest.approx(output["result"], abs=1e-10) == 0.0

    def test_factorial(self):
        """Test factorial function."""
        from scipy_compute import cmd_sp_factorial

        output = cmd_sp_factorial(5)
        assert output["result"] == 120

    def test_comb_binomial(self):
        """Test binomial coefficient C(n,k)."""
        from scipy_compute import cmd_sp_comb

        output = cmd_sp_comb(5, 2)
        assert output["result"] == 10  # 5! / (2! * 3!) = 10

    def test_bessel_j0_at_zero(self):
        """J_0(0) = 1."""
        from scipy_compute import cmd_sp_jv

        output = cmd_sp_jv("0", "0")
        assert pytest.approx(output["result"], abs=1e-10) == 1.0


# =============================================================================
# LINALG CATEGORY TESTS
# =============================================================================

class TestLinalg:
    """Tests for scipy.linalg functions."""

    def test_scipy_solve(self):
        """Solve Ax = b."""
        from scipy_compute import cmd_scipy_solve

        # 2x2 system: [[1,2],[3,4]] x = [5,6]
        output = cmd_scipy_solve("[[1,2],[3,4]]", "[5,6]")
        x = output["result"]
        # Verify: Ax should equal b
        A = np.array([[1,2],[3,4]])
        b = np.array([5,6])
        assert np.allclose(A @ np.array(x), b)

    def test_scipy_det(self):
        """Compute determinant."""
        from scipy_compute import cmd_scipy_det

        # det([[1,2],[3,4]]) = 1*4 - 2*3 = -2
        output = cmd_scipy_det("[[1,2],[3,4]]")
        assert pytest.approx(output["result"], abs=1e-10) == -2.0

    def test_scipy_inv(self):
        """Compute matrix inverse."""
        from scipy_compute import cmd_scipy_inv

        output = cmd_scipy_inv("[[1,2],[3,4]]")
        inv = np.array(output["result"])
        A = np.array([[1,2],[3,4]])
        # A * A^(-1) should be identity
        assert np.allclose(A @ inv, np.eye(2))

    def test_scipy_eig(self):
        """Compute eigenvalues and eigenvectors."""
        from scipy_compute import cmd_scipy_eig

        # Symmetric matrix has real eigenvalues
        output = cmd_scipy_eig("[[2,1],[1,2]]")
        # Eigenvalues are in metadata, not result
        eigenvalues = output["metadata"]["eigenvalues"]
        # Eigenvalues are complex tuples (real, imag) - extract real parts
        # They come as complex numbers
        real_parts = sorted([e.real if hasattr(e, 'real') else e[0] for e in eigenvalues])
        assert pytest.approx(real_parts[0], abs=1e-6) == 1.0
        assert pytest.approx(real_parts[1], abs=1e-6) == 3.0

    def test_scipy_norm(self):
        """Compute matrix norm."""
        from scipy_compute import cmd_scipy_norm

        # Frobenius norm of [[1,2],[3,4]] = sqrt(1+4+9+16) = sqrt(30)
        output = cmd_scipy_norm("[[1,2],[3,4]]", ord="fro")
        assert pytest.approx(output["result"], abs=1e-6) == np.sqrt(30)

    def test_expm(self):
        """Matrix exponential."""
        from scipy_compute import cmd_expm

        # exp([[0,0],[0,0]]) = I
        output = cmd_expm("[[0,0],[0,0]]")
        assert np.allclose(output["result"], np.eye(2))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
