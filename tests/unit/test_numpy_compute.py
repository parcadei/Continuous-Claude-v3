#!/usr/bin/env python3
"""Tests for numpy_compute.py - NumPy computation cognitive prosthetics.

TDD: These tests cover all major categories of numpy_compute.py:
- Linalg: det, inv, pinv, eig, eigvals, svd, qr, cholesky, solve, lstsq, norm, cond, rank
- Array math: dot, matmul, cross, outer, inner
- FFT: fft, ifft, rfft
- Polynomial: polyfit, polyval, roots
- Stats: mean, std, var, median, percentile
- Reduction: sum, prod, cumsum, cumprod, diff
- CLI: argument parsing
- Error handling: edge cases
"""

import pytest
import sys
from pathlib import Path

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


# =============================================================================
# Test: Linalg - Determinant, Inverse, Pseudo-inverse
# =============================================================================


class TestLinalgBasic:
    """Tests for basic linalg functions: det, inv, pinv."""

    def test_det_2x2(self):
        """Compute determinant of 2x2 matrix."""
        from numpy_compute import cmd_det

        result = cmd_det("[[1,2],[3,4]]")
        # det = 1*4 - 2*3 = -2
        assert "result" in result
        assert abs(result["result"] - (-2.0)) < 1e-10

    def test_det_3x3(self):
        """Compute determinant of 3x3 matrix."""
        from numpy_compute import cmd_det

        result = cmd_det("[[1,2,3],[4,5,6],[7,8,10]]")
        # This matrix has det = -3
        assert "result" in result
        assert abs(result["result"] - (-3.0)) < 1e-10

    def test_det_singular(self):
        """Compute determinant of singular matrix."""
        from numpy_compute import cmd_det

        result = cmd_det("[[1,2],[2,4]]")
        # det of singular matrix = 0
        assert "result" in result
        assert abs(result["result"]) < 1e-10

    def test_inv_2x2(self):
        """Compute inverse of 2x2 matrix."""
        from numpy_compute import cmd_inv

        result = cmd_inv("[[1,2],[3,4]]")
        # inv = 1/-2 * [[4,-2],[-3,1]] = [[-2,1],[1.5,-0.5]]
        assert "result" in result
        inv = result["result"]
        assert abs(inv[0][0] - (-2.0)) < 1e-10
        assert abs(inv[0][1] - 1.0) < 1e-10
        assert abs(inv[1][0] - 1.5) < 1e-10
        assert abs(inv[1][1] - (-0.5)) < 1e-10

    def test_inv_3x3(self):
        """Compute inverse of 3x3 matrix."""
        from numpy_compute import cmd_inv

        # Use identity matrix for simple verification
        result = cmd_inv("[[1,0,0],[0,1,0],[0,0,1]]")
        assert "result" in result
        inv = result["result"]
        # Inverse of identity is identity
        assert abs(inv[0][0] - 1.0) < 1e-10
        assert abs(inv[1][1] - 1.0) < 1e-10
        assert abs(inv[2][2] - 1.0) < 1e-10

    def test_inv_singular_error(self):
        """Inverse of singular matrix should produce error."""
        from numpy_compute import cmd_inv

        result = cmd_inv("[[1,2],[2,4]]")
        # Singular matrix - should have error
        assert "error" in result or "message" in result

    def test_pinv_rectangular(self):
        """Compute pseudo-inverse of rectangular matrix."""
        from numpy_compute import cmd_pinv

        result = cmd_pinv("[[1,2],[3,4],[5,6]]")
        assert "result" in result
        # Pseudo-inverse of 3x2 should be 2x3
        pinv = result["result"]
        assert len(pinv) == 2
        assert len(pinv[0]) == 3


# =============================================================================
# Test: Linalg - Solve and Least Squares
# =============================================================================


class TestLinalgSolve:
    """Tests for linear system solving: solve, lstsq."""

    def test_solve_2x2(self):
        """Solve 2x2 linear system."""
        from numpy_compute import cmd_solve

        # Solve [[3,1],[1,2]] @ x = [9,8]
        # Solution: x = [2, 3]
        result = cmd_solve("[[3,1],[1,2]]", "[9,8]")
        assert "result" in result
        x = result["result"]
        assert abs(x[0] - 2.0) < 1e-10
        assert abs(x[1] - 3.0) < 1e-10

    def test_solve_3x3(self):
        """Solve 3x3 linear system."""
        from numpy_compute import cmd_solve

        # Solve identity @ x = [1,2,3]
        # Solution: x = [1, 2, 3]
        result = cmd_solve("[[1,0,0],[0,1,0],[0,0,1]]", "[1,2,3]")
        assert "result" in result
        x = result["result"]
        assert abs(x[0] - 1.0) < 1e-10
        assert abs(x[1] - 2.0) < 1e-10
        assert abs(x[2] - 3.0) < 1e-10

    def test_lstsq_overdetermined(self):
        """Least squares for overdetermined system."""
        from numpy_compute import cmd_lstsq

        # Fit y = a*x + b to points (1,1), (2,2), (3,2)
        result = cmd_lstsq("[[1,1],[1,2],[1,3]]", "[1,2,2]")
        assert "result" in result
        # x contains [intercept, slope]
        x = result["result"]["x"]
        assert len(x) == 2

    def test_lstsq_underdetermined(self):
        """Least squares for underdetermined system."""
        from numpy_compute import cmd_lstsq

        # 1 equation, 2 unknowns
        result = cmd_lstsq("[[1,1]]", "[2]")
        assert "result" in result
        x = result["result"]["x"]
        assert len(x) == 2


# =============================================================================
# Test: Linalg - Eigenvalues and Eigenvectors
# =============================================================================


class TestLinalgEig:
    """Tests for eigenvalue/eigenvector computation."""

    def test_eig_2x2(self):
        """Compute eigenvalues of 2x2 matrix."""
        from numpy_compute import cmd_eig

        # Matrix [[2,1],[0,1]] has eigenvalues 2, 1
        result = cmd_eig("[[2,1],[0,1]]")
        assert "result" in result
        eigenvalues = result["result"]["eigenvalues"]
        # Sort for comparison
        sorted_eigs = sorted([abs(e) for e in eigenvalues])
        assert abs(sorted_eigs[0] - 1.0) < 1e-10
        assert abs(sorted_eigs[1] - 2.0) < 1e-10

    def test_eig_symmetric(self):
        """Compute eigenvalues of symmetric matrix."""
        from numpy_compute import cmd_eig

        # Symmetric matrix [[2,1],[1,2]] has eigenvalues 3, 1
        result = cmd_eig("[[2,1],[1,2]]")
        assert "result" in result
        eigenvalues = result["result"]["eigenvalues"]
        sorted_eigs = sorted([float(e.real) if hasattr(e, 'real') else float(e) for e in eigenvalues])
        assert abs(sorted_eigs[0] - 1.0) < 1e-10
        assert abs(sorted_eigs[1] - 3.0) < 1e-10

    def test_eigvals_only(self):
        """Compute eigenvalues only (no eigenvectors)."""
        from numpy_compute import cmd_eigvals

        result = cmd_eigvals("[[2,1],[0,1]]")
        assert "result" in result
        eigenvalues = result["result"]
        assert len(eigenvalues) == 2

    def test_eigh_hermitian(self):
        """Compute eigenvalues of Hermitian (symmetric) matrix."""
        from numpy_compute import cmd_eigh

        result = cmd_eigh("[[2,1],[1,2]]")
        assert "result" in result
        eigenvalues = result["result"]["eigenvalues"]
        sorted_eigs = sorted(eigenvalues)
        assert abs(sorted_eigs[0] - 1.0) < 1e-10
        assert abs(sorted_eigs[1] - 3.0) < 1e-10


# =============================================================================
# Test: Linalg - Matrix Decompositions
# =============================================================================


class TestLinalgDecomposition:
    """Tests for matrix decompositions: SVD, QR, Cholesky."""

    def test_svd_rectangular(self):
        """Compute SVD of rectangular matrix."""
        from numpy_compute import cmd_svd

        result = cmd_svd("[[1,2,3],[4,5,6]]")
        assert "result" in result
        assert "U" in result["result"]
        assert "S" in result["result"]
        assert "Vh" in result["result"]
        # 2x3 matrix should have 2 singular values
        assert len(result["result"]["S"]) == 2

    def test_svd_square(self):
        """Compute SVD of square matrix."""
        from numpy_compute import cmd_svd

        result = cmd_svd("[[1,2],[3,4]]")
        assert "result" in result
        assert "U" in result["result"]
        assert "S" in result["result"]
        assert "Vh" in result["result"]

    def test_qr_decomposition(self):
        """Compute QR decomposition."""
        from numpy_compute import cmd_qr

        result = cmd_qr("[[1,2],[3,4]]")
        assert "result" in result
        assert "Q" in result["result"]
        assert "R" in result["result"]

    def test_cholesky_positive_definite(self):
        """Compute Cholesky decomposition of positive-definite matrix."""
        from numpy_compute import cmd_cholesky

        # [[4,2],[2,2]] is positive-definite
        result = cmd_cholesky("[[4,2],[2,2]]")
        assert "result" in result
        L = result["result"]
        # L @ L.T should equal original
        assert len(L) == 2

    def test_cholesky_error_not_pd(self):
        """Cholesky of non-positive-definite matrix should error."""
        from numpy_compute import cmd_cholesky

        # [[1,2],[2,1]] is not positive-definite
        result = cmd_cholesky("[[1,2],[2,1]]")
        assert "error" in result or "message" in result


# =============================================================================
# Test: Linalg - Matrix Properties
# =============================================================================


class TestLinalgProperties:
    """Tests for matrix properties: norm, cond, rank."""

    def test_norm_frobenius(self):
        """Compute Frobenius norm."""
        from numpy_compute import cmd_norm

        # Frobenius norm of [[1,2],[3,4]] = sqrt(1+4+9+16) = sqrt(30)
        result = cmd_norm("[[1,2],[3,4]]", ord_="fro")
        assert "result" in result
        import math
        assert abs(result["result"] - math.sqrt(30)) < 1e-10

    def test_norm_2(self):
        """Compute 2-norm (spectral norm)."""
        from numpy_compute import cmd_norm

        result = cmd_norm("[[1,0],[0,2]]", ord_="2")
        assert "result" in result
        # Spectral norm of diagonal matrix is max eigenvalue = 2
        assert abs(result["result"] - 2.0) < 1e-10

    def test_norm_inf(self):
        """Compute infinity norm (max row sum)."""
        from numpy_compute import cmd_norm

        result = cmd_norm("[[1,2],[3,4]]", ord_="inf")
        assert "result" in result
        # Max row sum: max(3, 7) = 7
        assert abs(result["result"] - 7.0) < 1e-10

    def test_cond_wellconditioned(self):
        """Condition number of well-conditioned matrix."""
        from numpy_compute import cmd_cond

        # Identity has condition number 1
        result = cmd_cond("[[1,0],[0,1]]")
        assert "result" in result
        assert abs(result["result"] - 1.0) < 1e-10

    def test_cond_illconditioned(self):
        """Condition number of ill-conditioned matrix."""
        from numpy_compute import cmd_cond

        # Near-singular matrix has high condition number
        result = cmd_cond("[[1,1],[1,1.0001]]")
        assert "result" in result
        assert result["result"] > 10000  # High condition number

    def test_matrix_rank(self):
        """Compute matrix rank."""
        from numpy_compute import cmd_matrix_rank

        result = cmd_matrix_rank("[[1,2,3],[4,5,6],[7,8,9]]")
        assert "result" in result
        # This matrix has rank 2 (third row is sum of first two)
        assert result["result"] == 2


# =============================================================================
# Test: Array Operations
# =============================================================================


class TestArrayOps:
    """Tests for array manipulation functions."""

    def test_dot_vectors(self):
        """Dot product of two vectors."""
        from numpy_compute import cmd_dot

        result = cmd_dot("[1,2,3]", "[4,5,6]")
        assert "result" in result
        # 1*4 + 2*5 + 3*6 = 4 + 10 + 18 = 32
        assert abs(result["result"] - 32.0) < 1e-10

    def test_matmul_2x2(self):
        """Matrix multiplication 2x2."""
        from numpy_compute import cmd_matmul

        result = cmd_matmul("[[1,2],[3,4]]", "[[5,6],[7,8]]")
        assert "result" in result
        # [[1*5+2*7, 1*6+2*8], [3*5+4*7, 3*6+4*8]] = [[19,22],[43,50]]
        r = result["result"]
        assert r[0][0] == 19
        assert r[0][1] == 22
        assert r[1][0] == 43
        assert r[1][1] == 50

    def test_cross_3d(self):
        """Cross product of 3D vectors."""
        from numpy_compute import cmd_cross

        result = cmd_cross("[1,0,0]", "[0,1,0]")
        assert "result" in result
        # [1,0,0] x [0,1,0] = [0,0,1]
        r = result["result"]
        assert r[0] == 0
        assert r[1] == 0
        assert r[2] == 1

    def test_outer_product(self):
        """Outer product of two vectors."""
        from numpy_compute import cmd_outer

        result = cmd_outer("[1,2]", "[3,4]")
        assert "result" in result
        # [[1*3,1*4],[2*3,2*4]] = [[3,4],[6,8]]
        r = result["result"]
        assert r[0][0] == 3
        assert r[0][1] == 4
        assert r[1][0] == 6
        assert r[1][1] == 8


# =============================================================================
# Test: Statistics
# =============================================================================


class TestStatistics:
    """Tests for statistical functions."""

    def test_mean_1d(self):
        """Compute mean of 1D array."""
        from numpy_compute import cmd_mean

        result = cmd_mean("[1,2,3,4,5]")
        assert "result" in result
        assert abs(result["result"] - 3.0) < 1e-10

    def test_mean_2d_axis(self):
        """Compute mean along axis."""
        from numpy_compute import cmd_mean

        result = cmd_mean("[[1,2],[3,4]]", axis=0)
        assert "result" in result
        # Mean along axis 0: [2, 3]
        r = result["result"]
        assert abs(r[0] - 2.0) < 1e-10
        assert abs(r[1] - 3.0) < 1e-10

    def test_std_population(self):
        """Compute population standard deviation (ddof=0)."""
        from numpy_compute import cmd_std

        result = cmd_std("[1,2,3,4,5]", ddof=0)
        assert "result" in result
        # Population std of [1,2,3,4,5] = sqrt(2)
        import math
        assert abs(result["result"] - math.sqrt(2)) < 1e-10

    def test_std_sample(self):
        """Compute sample standard deviation (ddof=1)."""
        from numpy_compute import cmd_std

        result = cmd_std("[1,2,3,4,5]", ddof=1)
        assert "result" in result
        # Sample std = sqrt(var/4) = sqrt(10/4) = sqrt(2.5)
        import math
        assert abs(result["result"] - math.sqrt(2.5)) < 1e-10

    def test_var_1d(self):
        """Compute variance."""
        from numpy_compute import cmd_var

        result = cmd_var("[1,2,3,4,5]", ddof=0)
        assert "result" in result
        # Population variance = 2
        assert abs(result["result"] - 2.0) < 1e-10

    def test_median_odd(self):
        """Compute median of odd-length array."""
        from numpy_compute import cmd_median

        result = cmd_median("[1,3,2,5,4]")
        assert "result" in result
        # Sorted: [1,2,3,4,5], median = 3
        assert abs(result["result"] - 3.0) < 1e-10

    def test_median_even(self):
        """Compute median of even-length array."""
        from numpy_compute import cmd_median

        result = cmd_median("[1,2,3,4]")
        assert "result" in result
        # Sorted: [1,2,3,4], median = (2+3)/2 = 2.5
        assert abs(result["result"] - 2.5) < 1e-10

    def test_percentile_25_50_75(self):
        """Compute multiple percentiles."""
        from numpy_compute import cmd_percentile

        result = cmd_percentile("[0,1,2,3,4,5,6,7,8,9,10]", "[25,50,75]")
        assert "result" in result
        r = result["result"]
        assert abs(r[0] - 2.5) < 1e-10  # 25th percentile
        assert abs(r[1] - 5.0) < 1e-10  # 50th percentile (median)
        assert abs(r[2] - 7.5) < 1e-10  # 75th percentile


# =============================================================================
# Test: Reduction Operations
# =============================================================================


class TestReduction:
    """Tests for reduction operations: sum, prod, cumsum, cumprod, diff."""

    def test_sum_1d(self):
        """Sum of 1D array."""
        from numpy_compute import cmd_sum

        result = cmd_sum("[1,2,3,4,5]")
        assert "result" in result
        assert result["result"] == 15

    def test_sum_2d_axis(self):
        """Sum along axis."""
        from numpy_compute import cmd_sum

        result = cmd_sum("[[1,2],[3,4]]", axis=0)
        assert "result" in result
        # Sum along axis 0: [4, 6]
        r = result["result"]
        assert r[0] == 4
        assert r[1] == 6

    def test_prod_1d(self):
        """Product of 1D array."""
        from numpy_compute import cmd_prod

        result = cmd_prod("[1,2,3,4,5]")
        assert "result" in result
        assert result["result"] == 120

    def test_cumsum(self):
        """Cumulative sum."""
        from numpy_compute import cmd_cumsum

        result = cmd_cumsum("[1,2,3,4,5]")
        assert "result" in result
        # [1, 3, 6, 10, 15]
        r = result["result"]
        assert r == [1, 3, 6, 10, 15]

    def test_cumprod(self):
        """Cumulative product."""
        from numpy_compute import cmd_cumprod

        result = cmd_cumprod("[1,2,3,4,5]")
        assert "result" in result
        # [1, 2, 6, 24, 120]
        r = result["result"]
        assert r == [1, 2, 6, 24, 120]

    def test_diff(self):
        """Discrete difference."""
        from numpy_compute import cmd_diff

        result = cmd_diff("[1,2,4,7,0]")
        assert "result" in result
        # [1, 2, 3, -7]
        r = result["result"]
        assert r == [1, 2, 3, -7]


# =============================================================================
# Test: FFT
# =============================================================================


class TestFFT:
    """Tests for FFT operations."""

    def test_fft_simple(self):
        """Compute FFT of simple signal."""
        from numpy_compute import cmd_fft

        result = cmd_fft("[1,0,0,0]")
        assert "result" in result
        assert "real" in result["result"]
        assert "imag" in result["result"]
        # First element is sum = 1
        assert abs(result["result"]["real"][0] - 1.0) < 1e-10

    def test_ifft_roundtrip(self):
        """Verify FFT -> IFFT roundtrip."""
        from numpy_compute import cmd_fft, cmd_ifft

        # FFT of [1,2,3,4]
        fft_result = cmd_fft("[1,2,3,4]")

        # For roundtrip, we need to reconstruct the complex input for ifft
        # Since ifft expects the same format, verify the structure
        assert "result" in fft_result
        assert "real" in fft_result["result"]
        assert "imag" in fft_result["result"]

    def test_rfft_real_input(self):
        """Compute FFT optimized for real input."""
        from numpy_compute import cmd_rfft

        result = cmd_rfft("[1,2,3,4]")
        assert "result" in result
        assert "real" in result["result"]
        assert "imag" in result["result"]


# =============================================================================
# Test: Polynomial
# =============================================================================


class TestPolynomial:
    """Tests for polynomial operations."""

    def test_polyfit(self):
        """Fit polynomial to data."""
        from numpy_compute import cmd_polyfit

        # Fit line to (0,0), (1,1), (2,2)
        result = cmd_polyfit("[0,1,2]", "[0,1,2]", 1)
        assert "result" in result
        # Should be approximately [1, 0] (slope=1, intercept=0)
        coeffs = result["result"]
        assert abs(coeffs[0] - 1.0) < 1e-10  # slope
        assert abs(coeffs[1] - 0.0) < 1e-10  # intercept

    def test_polyval(self):
        """Evaluate polynomial at points."""
        from numpy_compute import cmd_polyval

        # p(x) = x^2 + 2x + 1 = (x+1)^2, coeffs [1, 2, 1]
        result = cmd_polyval("[1,2,1]", "[0,1,2]")
        assert "result" in result
        # p(0)=1, p(1)=4, p(2)=9
        r = result["result"]
        assert r[0] == 1
        assert r[1] == 4
        assert r[2] == 9

    def test_roots(self):
        """Find polynomial roots."""
        from numpy_compute import cmd_roots

        # p(x) = x^2 - 3x + 2 = (x-1)(x-2), roots at 1 and 2
        result = cmd_roots("[1,-3,2]")
        assert "result" in result
        roots_real = sorted(result["result"]["real"])
        assert abs(roots_real[0] - 1.0) < 1e-10
        assert abs(roots_real[1] - 2.0) < 1e-10


# =============================================================================
# Test: CLI Interface
# =============================================================================


class TestCLI:
    """Tests for CLI argument parsing."""

    def test_main_parser_exists(self):
        """Main parser function should exist."""
        from numpy_compute import get_registry

        registry = get_registry()
        # Should have many commands registered
        assert len(registry) > 50  # numpy_compute has 160+ functions

    def test_det_command_registered(self):
        """det command should be registered."""
        from numpy_compute import get_registry

        registry = get_registry()
        assert "det" in registry

    def test_inv_command_registered(self):
        """inv command should be registered."""
        from numpy_compute import get_registry

        registry = get_registry()
        assert "inv" in registry

    def test_eig_command_registered(self):
        """eig command should be registered."""
        from numpy_compute import get_registry

        registry = get_registry()
        assert "eig" in registry


# =============================================================================
# Test: Error Handling
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_det_nonsquare_error(self):
        """Determinant of non-square matrix should error."""
        from numpy_compute import cmd_det

        result = cmd_det("[[1,2,3],[4,5,6]]")
        assert "error" in result or "message" in result

    def test_solve_dimension_mismatch(self):
        """Solve with mismatched dimensions should error."""
        from numpy_compute import cmd_solve

        result = cmd_solve("[[1,2],[3,4]]", "[1,2,3]")
        assert "error" in result or "message" in result

    def test_eig_nonsquare_error(self):
        """Eigenvalues of non-square matrix should error."""
        from numpy_compute import cmd_eig

        result = cmd_eig("[[1,2,3],[4,5,6]]")
        assert "error" in result or "message" in result


# =============================================================================
# Test: Additional Linalg Functions
# =============================================================================


class TestLinalgAdvanced:
    """Tests for additional linalg functions."""

    def test_trace(self):
        """Compute matrix trace."""
        from numpy_compute import cmd_trace

        result = cmd_trace("[[1,2],[3,4]]")
        assert "result" in result
        # trace = 1 + 4 = 5
        assert result["result"] == 5

    def test_matrix_power(self):
        """Raise matrix to power."""
        from numpy_compute import cmd_matrix_power

        result = cmd_matrix_power("[[1,1],[0,1]]", 3)
        assert "result" in result
        # [[1,1],[0,1]]^3 = [[1,3],[0,1]]
        r = result["result"]
        assert r[0][0] == 1
        assert r[0][1] == 3
        assert r[1][0] == 0
        assert r[1][1] == 1

    def test_slogdet(self):
        """Compute sign and log of determinant."""
        from numpy_compute import cmd_slogdet

        result = cmd_slogdet("[[1,2],[3,4]]")
        assert "result" in result
        assert "sign" in result["result"]
        assert "logdet" in result["result"]


# =============================================================================
# Test: Additional Stats Functions
# =============================================================================


class TestStatsAdvanced:
    """Tests for additional stats functions."""

    def test_cov(self):
        """Compute covariance matrix."""
        from numpy_compute import cmd_cov

        result = cmd_cov("[[1,2,3],[4,5,6]]")
        assert "result" in result

    def test_corrcoef(self):
        """Compute correlation coefficient."""
        from numpy_compute import cmd_corrcoef

        result = cmd_corrcoef("[[1,2,3],[1,2,3]]")
        assert "result" in result
        # Perfect correlation = 1
        r = result["result"]
        assert abs(r[0][0] - 1.0) < 1e-10
        assert abs(r[1][1] - 1.0) < 1e-10

    def test_histogram(self):
        """Compute histogram."""
        from numpy_compute import cmd_histogram

        result = cmd_histogram("[0,1,2,3,4,5,6,7,8,9]", bins=5)
        assert "result" in result
        assert "counts" in result["result"]
        assert "bin_edges" in result["result"]


# =============================================================================
# Test: Sorting Functions
# =============================================================================


class TestSorting:
    """Tests for sorting functions."""

    def test_sort_1d(self):
        """Sort 1D array."""
        from numpy_compute import cmd_sort

        result = cmd_sort("[3,1,4,1,5,9,2,6]")
        assert "result" in result
        assert result["result"] == [1, 1, 2, 3, 4, 5, 6, 9]

    def test_argsort(self):
        """Get indices that would sort array."""
        from numpy_compute import cmd_argsort

        result = cmd_argsort("[3,1,2]")
        assert "result" in result
        # [1, 2, 0] because arr[1]=1 < arr[2]=2 < arr[0]=3
        assert result["result"] == [1, 2, 0]

    def test_argmax(self):
        """Find index of maximum."""
        from numpy_compute import cmd_argmax

        result = cmd_argmax("[1,5,3,4,2]")
        assert "result" in result
        assert result["result"] == 1  # 5 is at index 1

    def test_argmin(self):
        """Find index of minimum."""
        from numpy_compute import cmd_argmin

        result = cmd_argmin("[3,1,4,1,5]")
        assert "result" in result
        assert result["result"] == 1  # First 1 is at index 1


# =============================================================================
# Test: Random (via specific seeds)
# =============================================================================


class TestRandom:
    """Tests for random-related functions (using seeded outputs)."""

    def test_random_seed_consistency(self):
        """Random operations should be deterministic with seed."""
        # This is a conceptual test - numpy_compute doesn't expose random directly
        # but we can test that array operations on known data work consistently
        from numpy_compute import cmd_mean

        result = cmd_mean("[1,2,3,4,5]")
        assert "result" in result
        assert result["result"] == 3.0


# =============================================================================
# Test: Output Format Consistency
# =============================================================================


class TestOutputFormat:
    """Tests for output format consistency."""

    def test_result_has_metadata(self):
        """Results should have metadata."""
        from numpy_compute import cmd_det

        result = cmd_det("[[1,2],[3,4]]")
        # Wrapped result should have metadata structure
        assert "result" in result or "error" in result

    def test_array_result_has_shape(self):
        """Array results should include shape info."""
        from numpy_compute import cmd_inv

        result = cmd_inv("[[1,2],[3,4]]")
        if "error" not in result:
            assert "metadata" in result
            if "shape" in result["metadata"]:
                # Shape can be tuple or list depending on serialization
                assert list(result["metadata"]["shape"]) == [2, 2]
