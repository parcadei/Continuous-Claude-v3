"""NumPy computation CLI - 160 functions across 10 categories (linalg, array_math, fft, polynomial, stats, sorting, reduction, math, set, logic).

USAGE:
    uv run python scripts/numpy_compute.py <command> [args]

    # Linear algebra examples
    uv run python scripts/numpy_compute.py det "[[1,2],[3,4]]"
    uv run python scripts/numpy_compute.py inv "[[1,2],[3,4]]"
    uv run python scripts/numpy_compute.py eig "[[1,2],[3,4]]"
    uv run python scripts/numpy_compute.py svd "[[1,2,3],[4,5,6]]"
    uv run python scripts/numpy_compute.py solve "[[3,1],[1,2]]" "[9,8]"
    uv run python scripts/numpy_compute.py lstsq "[[1,1],[1,2],[1,3]]" "[1,2,2]"
"""

import sys

from scripts.math_base import (
    create_main_parser,
    format_latex_matrix,
    get_array_info,
    get_registry,
    main_cli,
    math_command,
    parse_array,
    parse_matrix,
    validate_square,
)

# Lazy numpy import
_np = None


def get_np():
    """Lazy import of numpy."""
    global _np
    if _np is None:
        import numpy

        _np = numpy
    return _np


# =============================================================================
# LINALG (21 functions)
# =============================================================================


@math_command(
    name="det",
    category="linalg",
    description="Compute matrix determinant",
    latex_template=r"\det(A) = {result}",
    args=[{"name": "matrix", "help": "Matrix as [[a,b],[c,d]]"}],
)
def cmd_det(matrix: str) -> dict:
    """Compute determinant of a square matrix."""
    M = parse_matrix(matrix)
    validate_square(M, "determinant")
    result = get_np().linalg.det(M)
    return {"result": float(result), **get_array_info(M)}


@math_command(
    name="inv",
    category="linalg",
    description="Compute matrix inverse",
    args=[{"name": "matrix", "help": "Square matrix as [[a,b],[c,d]]"}],
)
def cmd_inv(matrix: str) -> dict:
    """Compute inverse of a square matrix."""
    M = parse_matrix(matrix)
    validate_square(M, "inverse")
    result = get_np().linalg.inv(M)
    return {
        "result": result.tolist(),
        "latex": format_latex_matrix(result),
        **get_array_info(result),
    }


@math_command(
    name="pinv",
    category="linalg",
    description="Compute Moore-Penrose pseudo-inverse",
    args=[{"name": "matrix", "help": "Matrix as [[a,b],[c,d]]"}],
)
def cmd_pinv(matrix: str) -> dict:
    """Compute Moore-Penrose pseudo-inverse."""
    M = parse_matrix(matrix)
    result = get_np().linalg.pinv(M)
    return {
        "result": result.tolist(),
        "latex": format_latex_matrix(result),
        **get_array_info(result),
    }


@math_command(
    name="matrix_power",
    category="linalg",
    description="Raise matrix to integer power",
    args=[
        {"name": "matrix", "help": "Square matrix as [[a,b],[c,d]]"},
        {"name": "n", "type": int, "help": "Integer power"},
    ],
)
def cmd_matrix_power(matrix: str, n: int) -> dict:
    """Raise square matrix to integer power."""
    M = parse_matrix(matrix)
    validate_square(M, "matrix_power")
    result = get_np().linalg.matrix_power(M, n)
    return {
        "result": result.tolist(),
        "latex": format_latex_matrix(result),
        "power": n,
        **get_array_info(result),
    }


@math_command(
    name="matrix_rank",
    category="linalg",
    description="Compute matrix rank",
    args=[{"name": "matrix", "help": "Matrix as [[a,b],[c,d]]"}],
)
def cmd_matrix_rank(matrix: str) -> dict:
    """Compute matrix rank using SVD."""
    M = parse_matrix(matrix)
    result = get_np().linalg.matrix_rank(M)
    return {"result": int(result), **get_array_info(M)}


@math_command(
    name="norm",
    category="linalg",
    description="Compute matrix or vector norm",
    args=[
        {"name": "matrix", "help": "Matrix or vector"},
        {
            "name": "--ord",
            "dest": "ord_",
            "default": None,
            "help": "Order: 'fro', 'nuc', 1, 2, inf, -1, -2, -inf",
        },
    ],
)
def cmd_norm(matrix: str, ord_: str = None) -> dict:
    """Compute matrix or vector norm."""
    np = get_np()
    M = parse_matrix(matrix)

    # Parse ord parameter
    ord_val = None
    if ord_ is not None:
        ord_lower = ord_.lower()
        if ord_lower == "fro":
            ord_val = "fro"
        elif ord_lower == "nuc":
            ord_val = "nuc"
        elif ord_lower == "inf":
            ord_val = np.inf
        elif ord_lower == "-inf":
            ord_val = -np.inf
        else:
            ord_val = float(ord_)

    result = np.linalg.norm(M, ord=ord_val)
    return {"result": float(result), "ord": str(ord_), **get_array_info(M)}


@math_command(
    name="cond",
    category="linalg",
    description="Compute matrix condition number",
    args=[
        {"name": "matrix", "help": "Matrix as [[a,b],[c,d]]"},
        {"name": "--p", "default": None, "help": "Order: None, 'fro', 1, 2, inf, -1, -2, -inf"},
    ],
)
def cmd_cond(matrix: str, p: str = None) -> dict:
    """Compute condition number of a matrix."""
    np = get_np()
    M = parse_matrix(matrix)

    # Parse p parameter
    p_val = None
    if p is not None:
        p_lower = p.lower()
        if p_lower == "fro":
            p_val = "fro"
        elif p_lower == "inf":
            p_val = np.inf
        elif p_lower == "-inf":
            p_val = -np.inf
        else:
            p_val = float(p)

    result = np.linalg.cond(M, p=p_val)
    return {"result": float(result), "p": str(p), **get_array_info(M)}


@math_command(
    name="trace",
    category="linalg",
    description="Compute matrix trace (sum of diagonal)",
    args=[{"name": "matrix", "help": "Matrix as [[a,b],[c,d]]"}],
)
def cmd_trace(matrix: str) -> dict:
    """Compute trace (sum of diagonal elements)."""
    M = parse_matrix(matrix)
    result = get_np().trace(M)
    return {"result": float(result), **get_array_info(M)}


@math_command(
    name="eig",
    category="linalg",
    description="Compute eigenvalues and eigenvectors",
    args=[{"name": "matrix", "help": "Square matrix as [[a,b],[c,d]]"}],
)
def cmd_eig(matrix: str) -> dict:
    """Compute eigenvalues and right eigenvectors."""
    M = parse_matrix(matrix)
    validate_square(M, "eigendecomposition")
    eigenvalues, eigenvectors = get_np().linalg.eig(M)
    return {
        "result": {"eigenvalues": eigenvalues.tolist(), "eigenvectors": eigenvectors.tolist()},
        "eigenvalues_latex": format_latex_matrix(eigenvalues.reshape(-1, 1)),
        **get_array_info(M),
    }


@math_command(
    name="eigh",
    category="linalg",
    description="Eigenvalues/vectors for Hermitian matrix",
    args=[{"name": "matrix", "help": "Hermitian matrix as [[a,b],[b,c]]"}],
)
def cmd_eigh(matrix: str) -> dict:
    """Compute eigenvalues and eigenvectors for Hermitian/symmetric matrix."""
    M = parse_matrix(matrix)
    validate_square(M, "eigh")
    eigenvalues, eigenvectors = get_np().linalg.eigh(M)
    return {
        "result": {"eigenvalues": eigenvalues.tolist(), "eigenvectors": eigenvectors.tolist()},
        **get_array_info(M),
    }


@math_command(
    name="eigvals",
    category="linalg",
    description="Compute eigenvalues only",
    args=[{"name": "matrix", "help": "Square matrix as [[a,b],[c,d]]"}],
)
def cmd_eigvals(matrix: str) -> dict:
    """Compute eigenvalues of a square matrix."""
    M = parse_matrix(matrix)
    validate_square(M, "eigvals")
    eigenvalues = get_np().linalg.eigvals(M)
    return {
        "result": eigenvalues.tolist(),
        "latex": format_latex_matrix(eigenvalues.reshape(-1, 1)),
        **get_array_info(M),
    }


@math_command(
    name="eigvalsh",
    category="linalg",
    description="Eigenvalues for Hermitian matrix",
    args=[{"name": "matrix", "help": "Hermitian matrix as [[a,b],[b,c]]"}],
)
def cmd_eigvalsh(matrix: str) -> dict:
    """Compute eigenvalues of Hermitian/symmetric matrix."""
    M = parse_matrix(matrix)
    validate_square(M, "eigvalsh")
    eigenvalues = get_np().linalg.eigvalsh(M)
    return {"result": eigenvalues.tolist(), **get_array_info(M)}


@math_command(
    name="svd",
    category="linalg",
    description="Singular Value Decomposition",
    args=[
        {"name": "matrix", "help": "Matrix as [[a,b],[c,d]]"},
        {
            "name": "--full-matrices",
            "action": "store_true",
            "default": False,
            "help": "Return full U and Vh matrices",
        },
    ],
)
def cmd_svd(matrix: str, full_matrices: bool = False) -> dict:
    """Compute Singular Value Decomposition: A = U @ S @ Vh."""
    M = parse_matrix(matrix)
    U, S, Vh = get_np().linalg.svd(M, full_matrices=full_matrices)
    return {
        "result": {"U": U.tolist(), "S": S.tolist(), "Vh": Vh.tolist()},
        "singular_values_latex": format_latex_matrix(S.reshape(-1, 1)),
        **get_array_info(M),
    }


@math_command(
    name="qr",
    category="linalg",
    description="QR decomposition",
    args=[
        {"name": "matrix", "help": "Matrix as [[a,b],[c,d]]"},
        {"name": "--mode", "default": "reduced", "help": "Mode: 'reduced', 'complete', 'r', 'raw'"},
    ],
)
def cmd_qr(matrix: str, mode: str = "reduced") -> dict:
    """Compute QR decomposition: A = Q @ R."""
    M = parse_matrix(matrix)
    result = get_np().linalg.qr(M, mode=mode)

    if mode == "r":
        return {"result": {"R": result.tolist()}, **get_array_info(M)}
    elif mode == "raw":
        h, tau = result
        return {"result": {"h": h.tolist(), "tau": tau.tolist()}, **get_array_info(M)}
    else:
        Q, R = result
        return {"result": {"Q": Q.tolist(), "R": R.tolist()}, **get_array_info(M)}


@math_command(
    name="cholesky",
    category="linalg",
    description="Cholesky decomposition",
    args=[{"name": "matrix", "help": "Positive-definite matrix"}],
)
def cmd_cholesky(matrix: str) -> dict:
    """Compute Cholesky decomposition: A = L @ L.T."""
    M = parse_matrix(matrix)
    validate_square(M, "cholesky")
    L = get_np().linalg.cholesky(M)
    return {"result": L.tolist(), "latex": format_latex_matrix(L), **get_array_info(M)}


@math_command(
    name="lstsq",
    category="linalg",
    description="Least-squares solution to Ax=b",
    args=[
        {"name": "a", "help": "Coefficient matrix A"},
        {"name": "b", "help": "Dependent variable b"},
    ],
)
def cmd_lstsq(a: str, b: str) -> dict:
    """Solve least-squares problem: minimize ||Ax - b||."""
    A = parse_matrix(a)
    B = parse_array(b)
    x, residuals, rank, s = get_np().linalg.lstsq(A, B, rcond=None)
    return {
        "result": {
            "x": x.tolist(),
            "residuals": residuals.tolist() if residuals.size > 0 else [],
            "rank": int(rank),
            "singular_values": s.tolist(),
        },
        "solution_latex": format_latex_matrix(x.reshape(-1, 1)),
        **get_array_info(A),
    }


@math_command(
    name="solve",
    category="linalg",
    description="Solve linear system Ax=b",
    args=[
        {"name": "a", "help": "Coefficient matrix A"},
        {"name": "b", "help": "Right-hand side b"},
    ],
)
def cmd_solve(a: str, b: str) -> dict:
    """Solve linear system Ax = b for x."""
    A = parse_matrix(a)
    B = parse_array(b)
    validate_square(A, "solve")
    x = get_np().linalg.solve(A, B)
    return {
        "result": x.tolist(),
        "latex": format_latex_matrix(x.reshape(-1, 1)),
        **get_array_info(A),
    }


@math_command(
    name="tensorsolve",
    category="linalg",
    description="Solve tensor equation a x = b",
    args=[{"name": "a", "help": "Coefficient tensor"}, {"name": "b", "help": "Right-hand side"}],
)
def cmd_tensorsolve(a: str, b: str) -> dict:
    """Solve tensor equation sum_k a[i0,...,iN-1,k0,...,kM-1]*x[k0,...,kM-1] = b[i0,...,iN-1]."""
    A = parse_matrix(a)
    B = parse_array(b)
    x = get_np().linalg.tensorsolve(A, B)
    return {"result": x.tolist(), **get_array_info(x)}


@math_command(
    name="tensorinv",
    category="linalg",
    description="Compute tensor inverse",
    args=[
        {"name": "a", "help": "Tensor to invert"},
        {
            "name": "--ind",
            "type": int,
            "default": 2,
            "help": "Number of first indices that are summed in tensorsolve",
        },
    ],
)
def cmd_tensorinv(a: str, ind: int = 2) -> dict:
    """Compute inverse of N-dimensional array."""
    A = parse_matrix(a)
    result = get_np().linalg.tensorinv(A, ind=ind)
    return {"result": result.tolist(), **get_array_info(result)}


@math_command(
    name="multi_dot",
    category="linalg",
    description="Efficient multiple matrix multiplication",
    args=[
        {"name": "matrices", "help": "Semicolon-separated matrices: [[1,2],[3,4]];[[5,6],[7,8]]"}
    ],
)
def cmd_multi_dot(matrices: str) -> dict:
    """Compute matrix product of multiple matrices efficiently."""
    # Parse semicolon-separated matrices
    matrix_strs = matrices.split(";")
    arrays = [parse_matrix(m.strip()) for m in matrix_strs]
    result = get_np().linalg.multi_dot(arrays)
    return {
        "result": result.tolist(),
        "latex": format_latex_matrix(result),
        "num_matrices": len(arrays),
        **get_array_info(result),
    }


@math_command(
    name="slogdet",
    category="linalg",
    description="Sign and log of determinant",
    args=[{"name": "matrix", "help": "Square matrix as [[a,b],[c,d]]"}],
)
def cmd_slogdet(matrix: str) -> dict:
    """Compute sign and natural log of determinant."""
    M = parse_matrix(matrix)
    validate_square(M, "slogdet")
    sign, logdet = get_np().linalg.slogdet(M)
    return {
        "result": {"sign": float(sign), "logdet": float(logdet)},
        "determinant": float(sign * get_np().exp(logdet)),
        **get_array_info(M),
    }


# =============================================================================
# ARRAY MATH (10 functions)
# =============================================================================


@math_command(
    name="dot",
    category="array_math",
    description="Dot product of two arrays",
    args=[{"name": "a", "help": "First array"}, {"name": "b", "help": "Second array"}],
)
def cmd_dot(a: str, b: str) -> dict:
    """Compute dot product of two arrays."""
    A = parse_array(a)
    B = parse_array(b)
    r = get_np().dot(A, B)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="vdot",
    category="array_math",
    description="Vector dot product (flattens input)",
    args=[{"name": "a", "help": "First array"}, {"name": "b", "help": "Second array"}],
)
def cmd_vdot(a: str, b: str) -> dict:
    """Compute vector dot product (conjugates first argument if complex)."""
    A = parse_array(a)
    B = parse_array(b)
    r = get_np().vdot(A, B)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="inner",
    category="array_math",
    description="Inner product of two arrays",
    args=[{"name": "a", "help": "First array"}, {"name": "b", "help": "Second array"}],
)
def cmd_inner(a: str, b: str) -> dict:
    """Compute inner product of two arrays."""
    A = parse_array(a)
    B = parse_array(b)
    r = get_np().inner(A, B)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="outer",
    category="array_math",
    description="Outer product of two arrays",
    args=[{"name": "a", "help": "First array"}, {"name": "b", "help": "Second array"}],
)
def cmd_outer(a: str, b: str) -> dict:
    """Compute outer product of two vectors."""
    A = parse_array(a)
    B = parse_array(b)
    r = get_np().outer(A, B)
    return {"result": r.tolist(), "latex": format_latex_matrix(r), **get_array_info(r)}


@math_command(
    name="matmul",
    category="array_math",
    description="Matrix product of two arrays",
    args=[{"name": "a", "help": "First array"}, {"name": "b", "help": "Second array"}],
)
def cmd_matmul(a: str, b: str) -> dict:
    """Compute matrix product of two arrays."""
    A = parse_matrix(a)
    B = parse_matrix(b)
    r = get_np().matmul(A, B)
    return {"result": r.tolist(), "latex": format_latex_matrix(r), **get_array_info(r)}


@math_command(
    name="tensordot",
    category="array_math",
    description="Tensor dot product along specified axes",
    args=[
        {"name": "a", "help": "First array"},
        {"name": "b", "help": "Second array"},
        {
            "name": "--axes",
            "type": int,
            "default": 2,
            "help": "Sum over last N axes of a and first N axes of b",
        },
    ],
)
def cmd_tensordot(a: str, b: str, axes: int = 2) -> dict:
    """Compute tensor dot product along specified axes."""
    A = parse_matrix(a)
    B = parse_matrix(b)
    r = get_np().tensordot(A, B, axes=axes)
    result = {"result": r.tolist() if hasattr(r, "tolist") else float(r)}
    if hasattr(r, "shape"):
        result.update(get_array_info(r))
    return result


@math_command(
    name="einsum",
    category="array_math",
    description="Einstein summation convention",
    args=[
        {"name": "subscripts", "help": "Subscript string (e.g., 'ij,jk->ik')"},
        {"name": "operands", "help": "Semicolon-separated arrays"},
    ],
)
def cmd_einsum(subscripts: str, operands: str) -> dict:
    """Evaluate Einstein summation convention."""
    # Parse semicolon-separated operands
    operand_strs = operands.split(";")
    arrays = [parse_matrix(o.strip()) for o in operand_strs]
    r = get_np().einsum(subscripts, *arrays)
    result = {"result": r.tolist() if hasattr(r, "tolist") else float(r), "subscripts": subscripts}
    if hasattr(r, "shape"):
        result.update(get_array_info(r))
    return result


@math_command(
    name="einsum_path",
    category="array_math",
    description="Optimal contraction path for einsum",
    args=[
        {"name": "subscripts", "help": "Subscript string (e.g., 'ij,jk->ik')"},
        {"name": "operands", "help": "Semicolon-separated arrays"},
    ],
)
def cmd_einsum_path(subscripts: str, operands: str) -> dict:
    """Evaluate optimal contraction path for einsum."""
    operand_strs = operands.split(";")
    arrays = [parse_matrix(o.strip()) for o in operand_strs]
    path, info = get_np().einsum_path(subscripts, *arrays, optimize="optimal")
    return {
        "result": {"path": [list(p) if hasattr(p, "__iter__") else p for p in path], "info": info},
        "subscripts": subscripts,
    }


@math_command(
    name="cross",
    category="array_math",
    description="Cross product of two vectors",
    args=[
        {"name": "a", "help": "First vector (2D or 3D)"},
        {"name": "b", "help": "Second vector (2D or 3D)"},
    ],
)
def cmd_cross(a: str, b: str) -> dict:
    """Compute cross product of two vectors."""
    A = parse_array(a)
    B = parse_array(b)
    r = get_np().cross(A, B)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="kron",
    category="array_math",
    description="Kronecker product of two arrays",
    args=[{"name": "a", "help": "First array"}, {"name": "b", "help": "Second array"}],
)
def cmd_kron(a: str, b: str) -> dict:
    """Compute Kronecker product of two arrays."""
    A = parse_matrix(a)
    B = parse_matrix(b)
    r = get_np().kron(A, B)
    return {"result": r.tolist(), "latex": format_latex_matrix(r), **get_array_info(r)}


# =============================================================================
# FFT (18 functions)
# =============================================================================


@math_command(
    name="fft",
    category="fft",
    description="One-dimensional discrete Fourier Transform",
    args=[
        {"name": "a", "help": "Input array"},
        {"name": "--n", "type": int, "default": None, "help": "Length of transformed axis"},
    ],
)
def cmd_fft(a: str, n: int = None) -> dict:
    """Compute one-dimensional discrete Fourier Transform."""
    A = parse_array(a)
    r = get_np().fft.fft(A, n=n)
    return {"result": {"real": r.real.tolist(), "imag": r.imag.tolist()}, **get_array_info(r)}


@math_command(
    name="ifft",
    category="fft",
    description="One-dimensional inverse discrete Fourier Transform",
    args=[
        {"name": "a", "help": "Input array"},
        {"name": "--n", "type": int, "default": None, "help": "Length of transformed axis"},
    ],
)
def cmd_ifft(a: str, n: int = None) -> dict:
    """Compute one-dimensional inverse discrete Fourier Transform."""
    A = parse_array(a)
    r = get_np().fft.ifft(A, n=n)
    return {"result": {"real": r.real.tolist(), "imag": r.imag.tolist()}, **get_array_info(r)}


@math_command(
    name="fft2",
    category="fft",
    description="Two-dimensional discrete Fourier Transform",
    args=[{"name": "a", "help": "Input 2D array"}],
)
def cmd_fft2(a: str) -> dict:
    """Compute two-dimensional discrete Fourier Transform."""
    A = parse_matrix(a)
    r = get_np().fft.fft2(A)
    return {"result": {"real": r.real.tolist(), "imag": r.imag.tolist()}, **get_array_info(r)}


@math_command(
    name="ifft2",
    category="fft",
    description="Two-dimensional inverse discrete Fourier Transform",
    args=[{"name": "a", "help": "Input 2D array"}],
)
def cmd_ifft2(a: str) -> dict:
    """Compute two-dimensional inverse discrete Fourier Transform."""
    A = parse_matrix(a)
    r = get_np().fft.ifft2(A)
    return {"result": {"real": r.real.tolist(), "imag": r.imag.tolist()}, **get_array_info(r)}


@math_command(
    name="fftn",
    category="fft",
    description="N-dimensional discrete Fourier Transform",
    args=[{"name": "a", "help": "Input array"}],
)
def cmd_fftn(a: str) -> dict:
    """Compute N-dimensional discrete Fourier Transform."""
    A = parse_matrix(a)
    r = get_np().fft.fftn(A)
    return {"result": {"real": r.real.tolist(), "imag": r.imag.tolist()}, **get_array_info(r)}


@math_command(
    name="ifftn",
    category="fft",
    description="N-dimensional inverse discrete Fourier Transform",
    args=[{"name": "a", "help": "Input array"}],
)
def cmd_ifftn(a: str) -> dict:
    """Compute N-dimensional inverse discrete Fourier Transform."""
    A = parse_matrix(a)
    r = get_np().fft.ifftn(A)
    return {"result": {"real": r.real.tolist(), "imag": r.imag.tolist()}, **get_array_info(r)}


@math_command(
    name="rfft",
    category="fft",
    description="One-dimensional FFT for real input",
    args=[
        {"name": "a", "help": "Input array (real)"},
        {"name": "--n", "type": int, "default": None, "help": "Length of transformed axis"},
    ],
)
def cmd_rfft(a: str, n: int = None) -> dict:
    """Compute one-dimensional FFT for real input."""
    A = parse_array(a)
    r = get_np().fft.rfft(A, n=n)
    return {"result": {"real": r.real.tolist(), "imag": r.imag.tolist()}, **get_array_info(r)}


@math_command(
    name="irfft",
    category="fft",
    description="Inverse FFT for real input",
    args=[
        {"name": "a", "help": "Input array"},
        {"name": "--n", "type": int, "default": None, "help": "Length of transformed axis"},
    ],
)
def cmd_irfft(a: str, n: int = None) -> dict:
    """Compute inverse of rfft."""
    A = parse_array(a)
    r = get_np().fft.irfft(A, n=n)
    return {"result": r.tolist(), **get_array_info(r)}


@math_command(
    name="rfft2",
    category="fft",
    description="Two-dimensional FFT for real input",
    args=[{"name": "a", "help": "Input 2D array (real)"}],
)
def cmd_rfft2(a: str) -> dict:
    """Compute two-dimensional FFT for real input."""
    A = parse_matrix(a)
    r = get_np().fft.rfft2(A)
    return {"result": {"real": r.real.tolist(), "imag": r.imag.tolist()}, **get_array_info(r)}


@math_command(
    name="irfft2",
    category="fft",
    description="Inverse two-dimensional FFT for real input",
    args=[{"name": "a", "help": "Input 2D array"}],
)
def cmd_irfft2(a: str) -> dict:
    """Compute inverse of rfft2."""
    A = parse_matrix(a)
    r = get_np().fft.irfft2(A)
    return {"result": r.tolist(), **get_array_info(r)}


@math_command(
    name="rfftn",
    category="fft",
    description="N-dimensional FFT for real input",
    args=[{"name": "a", "help": "Input array (real)"}],
)
def cmd_rfftn(a: str) -> dict:
    """Compute N-dimensional FFT for real input."""
    A = parse_matrix(a)
    r = get_np().fft.rfftn(A)
    return {"result": {"real": r.real.tolist(), "imag": r.imag.tolist()}, **get_array_info(r)}


@math_command(
    name="irfftn",
    category="fft",
    description="Inverse N-dimensional FFT for real input",
    args=[{"name": "a", "help": "Input array"}],
)
def cmd_irfftn(a: str) -> dict:
    """Compute inverse of rfftn."""
    A = parse_matrix(a)
    r = get_np().fft.irfftn(A)
    return {"result": r.tolist(), **get_array_info(r)}


@math_command(
    name="hfft",
    category="fft",
    description="FFT of Hermitian-symmetric signal",
    args=[
        {"name": "a", "help": "Input array"},
        {"name": "--n", "type": int, "default": None, "help": "Length of transformed axis"},
    ],
)
def cmd_hfft(a: str, n: int = None) -> dict:
    """Compute FFT of a signal with Hermitian symmetry (real spectrum)."""
    A = parse_array(a)
    r = get_np().fft.hfft(A, n=n)
    return {"result": r.tolist(), **get_array_info(r)}


@math_command(
    name="ihfft",
    category="fft",
    description="Inverse FFT of Hermitian-symmetric signal",
    args=[
        {"name": "a", "help": "Input array"},
        {"name": "--n", "type": int, "default": None, "help": "Length of transformed axis"},
    ],
)
def cmd_ihfft(a: str, n: int = None) -> dict:
    """Compute inverse of hfft."""
    A = parse_array(a)
    r = get_np().fft.ihfft(A, n=n)
    return {"result": {"real": r.real.tolist(), "imag": r.imag.tolist()}, **get_array_info(r)}


@math_command(
    name="fftfreq",
    category="fft",
    description="Discrete Fourier Transform sample frequencies",
    args=[
        {"name": "n", "type": int, "help": "Window length"},
        {"name": "--d", "type": float, "default": 1.0, "help": "Sample spacing"},
    ],
)
def cmd_fftfreq(n: int, d: float = 1.0) -> dict:
    """Return the Discrete Fourier Transform sample frequencies."""
    r = get_np().fft.fftfreq(n, d=d)
    return {"result": r.tolist(), **get_array_info(r)}


@math_command(
    name="rfftfreq",
    category="fft",
    description="DFT sample frequencies for rfft",
    args=[
        {"name": "n", "type": int, "help": "Window length"},
        {"name": "--d", "type": float, "default": 1.0, "help": "Sample spacing"},
    ],
)
def cmd_rfftfreq(n: int, d: float = 1.0) -> dict:
    """Return the Discrete Fourier Transform sample frequencies for rfft."""
    r = get_np().fft.rfftfreq(n, d=d)
    return {"result": r.tolist(), **get_array_info(r)}


@math_command(
    name="fftshift",
    category="fft",
    description="Shift zero-frequency component to center",
    args=[{"name": "a", "help": "Input array"}],
)
def cmd_fftshift(a: str) -> dict:
    """Shift the zero-frequency component to the center of the spectrum."""
    A = parse_array(a)
    r = get_np().fft.fftshift(A)
    return {"result": r.tolist(), **get_array_info(r)}


@math_command(
    name="ifftshift",
    category="fft",
    description="Inverse of fftshift",
    args=[{"name": "a", "help": "Input array"}],
)
def cmd_ifftshift(a: str) -> dict:
    """Inverse of fftshift."""
    A = parse_array(a)
    r = get_np().fft.ifftshift(A)
    return {"result": r.tolist(), **get_array_info(r)}


# =============================================================================
# POLYNOMIAL (11 functions)
# =============================================================================


@math_command(
    name="polyval",
    category="polynomial",
    description="Evaluate polynomial at given points",
    args=[
        {"name": "p", "help": "Polynomial coefficients (highest power first)"},
        {"name": "x", "help": "Points to evaluate at"},
    ],
)
def cmd_polyval(p: str, x: str) -> dict:
    """Evaluate polynomial p at points x."""
    P = parse_array(p)
    X = parse_array(x)
    r = get_np().polyval(P, X)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r), "degree": len(P) - 1}


@math_command(
    name="polyfit",
    category="polynomial",
    description="Least squares polynomial fit",
    args=[
        {"name": "x", "help": "x-coordinates"},
        {"name": "y", "help": "y-coordinates"},
        {"name": "deg", "type": int, "help": "Degree of polynomial"},
    ],
)
def cmd_polyfit(x: str, y: str, deg: int) -> dict:
    """Fit polynomial of given degree to data points."""
    X = parse_array(x)
    Y = parse_array(y)
    coeffs = get_np().polyfit(X, Y, deg)
    return {"result": coeffs.tolist(), "degree": deg, "coefficients_highest_first": True}


@math_command(
    name="polyadd",
    category="polynomial",
    description="Add two polynomials",
    args=[
        {"name": "a1", "help": "First polynomial coefficients"},
        {"name": "a2", "help": "Second polynomial coefficients"},
    ],
)
def cmd_polyadd(a1: str, a2: str) -> dict:
    """Add two polynomials."""
    A1 = parse_array(a1)
    A2 = parse_array(a2)
    r = get_np().polyadd(A1, A2)
    return {"result": r.tolist(), "degree": len(r) - 1}


@math_command(
    name="polysub",
    category="polynomial",
    description="Subtract two polynomials",
    args=[
        {"name": "a1", "help": "First polynomial coefficients"},
        {"name": "a2", "help": "Second polynomial coefficients"},
    ],
)
def cmd_polysub(a1: str, a2: str) -> dict:
    """Subtract one polynomial from another."""
    A1 = parse_array(a1)
    A2 = parse_array(a2)
    r = get_np().polysub(A1, A2)
    return {"result": r.tolist(), "degree": len(r) - 1}


@math_command(
    name="polymul",
    category="polynomial",
    description="Multiply two polynomials",
    args=[
        {"name": "a1", "help": "First polynomial coefficients"},
        {"name": "a2", "help": "Second polynomial coefficients"},
    ],
)
def cmd_polymul(a1: str, a2: str) -> dict:
    """Multiply two polynomials."""
    A1 = parse_array(a1)
    A2 = parse_array(a2)
    r = get_np().polymul(A1, A2)
    return {"result": r.tolist(), "degree": len(r) - 1}


@math_command(
    name="polydiv",
    category="polynomial",
    description="Divide two polynomials",
    args=[
        {"name": "u", "help": "Dividend polynomial coefficients"},
        {"name": "v", "help": "Divisor polynomial coefficients"},
    ],
)
def cmd_polydiv(u: str, v: str) -> dict:
    """Divide one polynomial by another (returns quotient and remainder)."""
    U = parse_array(u)
    V = parse_array(v)
    q, r = get_np().polydiv(U, V)
    return {"result": {"quotient": q.tolist(), "remainder": r.tolist()}}


@math_command(
    name="polyder",
    category="polynomial",
    description="Derivative of a polynomial",
    args=[
        {"name": "p", "help": "Polynomial coefficients"},
        {"name": "--m", "type": int, "default": 1, "help": "Order of derivative"},
    ],
)
def cmd_polyder(p: str, m: int = 1) -> dict:
    """Compute the m-th derivative of a polynomial."""
    P = parse_array(p)
    r = get_np().polyder(P, m=m)
    return {"result": r.tolist(), "derivative_order": m}


@math_command(
    name="polyint",
    category="polynomial",
    description="Antiderivative (indefinite integral) of polynomial",
    args=[
        {"name": "p", "help": "Polynomial coefficients"},
        {"name": "--m", "type": int, "default": 1, "help": "Order of integration"},
        {"name": "--k", "default": None, "help": "Integration constants"},
    ],
)
def cmd_polyint(p: str, m: int = 1, k=None) -> dict:
    """Compute the m-th antiderivative of a polynomial."""
    P = parse_array(p)
    k_val = None
    if k is not None:
        k_val = parse_array(k).tolist()
    r = get_np().polyint(P, m=m, k=k_val)
    return {"result": r.tolist(), "integration_order": m}


@math_command(
    name="roots",
    category="polynomial",
    description="Find roots of a polynomial",
    args=[{"name": "p", "help": "Polynomial coefficients (highest power first)"}],
)
def cmd_roots(p: str) -> dict:
    """Find roots of polynomial with given coefficients."""
    P = parse_array(p)
    r = get_np().roots(P)
    return {"result": {"real": r.real.tolist(), "imag": r.imag.tolist()}, "degree": len(P) - 1}


@math_command(
    name="poly",
    category="polynomial",
    description="Find polynomial from roots",
    args=[{"name": "seq_of_zeros", "help": "Sequence of polynomial roots"}],
)
def cmd_poly(seq_of_zeros: str) -> dict:
    """Find polynomial coefficients given the roots."""
    Z = parse_array(seq_of_zeros)
    r = get_np().poly(Z)
    return {"result": r.tolist(), "degree": len(r) - 1, "coefficients_highest_first": True}


@math_command(
    name="polyvander",
    category="polynomial",
    description="Vandermonde matrix of given degree",
    args=[
        {"name": "x", "help": "Array of points"},
        {"name": "deg", "type": int, "help": "Degree of polynomial"},
    ],
)
def cmd_polyvander(x: str, deg: int) -> dict:
    """Generate Vandermonde matrix of given degree."""
    X = parse_array(x)
    r = get_np().polynomial.polynomial.polyvander(X, deg)
    return {"result": r.tolist(), "latex": format_latex_matrix(r), **get_array_info(r)}


# =============================================================================
# STATS (18 functions)
# =============================================================================


@math_command(
    name="mean",
    category="stats",
    description="Arithmetic mean",
    args=[
        {"name": "data", "help": "Array as [1,2,3] or [[1,2],[3,4]]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to compute"},
    ],
)
def cmd_mean(data: str, axis: int = None) -> dict:
    """Compute arithmetic mean."""
    arr = parse_array(data)
    r = get_np().mean(arr, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="average",
    category="stats",
    description="Weighted average",
    args=[
        {"name": "data", "help": "Array as [1,2,3]"},
        {"name": "--weights", "default": None, "help": "Weights as [w1,w2,w3]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to compute"},
    ],
)
def cmd_average(data: str, weights: str = None, axis: int = None) -> dict:
    """Compute weighted average."""
    arr = parse_array(data)
    w = parse_array(weights) if weights else None
    r = get_np().average(arr, weights=w, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="median",
    category="stats",
    description="Median value",
    args=[
        {"name": "data", "help": "Array as [1,2,3,4,5]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to compute"},
    ],
)
def cmd_median(data: str, axis: int = None) -> dict:
    """Compute median."""
    arr = parse_array(data)
    r = get_np().median(arr, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="std",
    category="stats",
    description="Standard deviation",
    args=[
        {"name": "data", "help": "Array as [1,2,3,4,5]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to compute"},
        {"name": "--ddof", "type": int, "default": 0, "help": "Delta degrees of freedom"},
    ],
)
def cmd_std(data: str, axis: int = None, ddof: int = 0) -> dict:
    """Compute standard deviation."""
    arr = parse_array(data)
    r = get_np().std(arr, axis=axis, ddof=ddof)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="var",
    category="stats",
    description="Variance",
    args=[
        {"name": "data", "help": "Array as [1,2,3,4,5]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to compute"},
        {"name": "--ddof", "type": int, "default": 0, "help": "Delta degrees of freedom"},
    ],
)
def cmd_var(data: str, axis: int = None, ddof: int = 0) -> dict:
    """Compute variance."""
    arr = parse_array(data)
    r = get_np().var(arr, axis=axis, ddof=ddof)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="cov",
    category="stats",
    description="Covariance matrix",
    args=[
        {"name": "data", "help": "Array as [[x1,x2,...],[y1,y2,...]]"},
        {
            "name": "--rowvar",
            "action": "store_true",
            "default": True,
            "help": "Each row is a variable",
        },
        {"name": "--ddof", "type": int, "default": None, "help": "Delta degrees of freedom"},
    ],
)
def cmd_cov(data: str, rowvar: bool = True, ddof: int = None) -> dict:
    """Compute covariance matrix."""
    arr = parse_array(data)
    r = get_np().cov(arr, rowvar=rowvar, ddof=ddof)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="corrcoef",
    category="stats",
    description="Correlation coefficient matrix",
    args=[
        {"name": "data", "help": "Array as [[x1,x2,...],[y1,y2,...]]"},
        {
            "name": "--rowvar",
            "action": "store_true",
            "default": True,
            "help": "Each row is a variable",
        },
    ],
)
def cmd_corrcoef(data: str, rowvar: bool = True) -> dict:
    """Compute Pearson correlation coefficient matrix."""
    arr = parse_array(data)
    r = get_np().corrcoef(arr, rowvar=rowvar)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="histogram",
    category="stats",
    description="Compute histogram",
    args=[
        {"name": "data", "help": "Array as [1,2,3,4,5]"},
        {"name": "--bins", "type": int, "default": 10, "help": "Number of bins"},
    ],
)
def cmd_histogram(data: str, bins: int = 10) -> dict:
    """Compute histogram."""
    arr = parse_array(data)
    hist, bin_edges = get_np().histogram(arr, bins=bins)
    return {"result": {"counts": hist.tolist(), "bin_edges": bin_edges.tolist()}}


@math_command(
    name="histogram2d",
    category="stats",
    description="Compute 2D histogram",
    args=[
        {"name": "x", "help": "X values as [1,2,3,4,5]"},
        {"name": "y", "help": "Y values as [1,2,3,4,5]"},
        {"name": "--bins", "type": int, "default": 10, "help": "Number of bins"},
    ],
)
def cmd_histogram2d(x: str, y: str, bins: int = 10) -> dict:
    """Compute 2D histogram."""
    x_arr = parse_array(x)
    y_arr = parse_array(y)
    hist, xedges, yedges = get_np().histogram2d(x_arr, y_arr, bins=bins)
    return {
        "result": {"counts": hist.tolist(), "x_edges": xedges.tolist(), "y_edges": yedges.tolist()}
    }


@math_command(
    name="histogramdd",
    category="stats",
    description="Compute multi-dimensional histogram",
    args=[
        {"name": "data", "help": "Sample as [[x1,y1],[x2,y2],...]"},
        {"name": "--bins", "type": int, "default": 10, "help": "Number of bins"},
    ],
)
def cmd_histogramdd(data: str, bins: int = 10) -> dict:
    """Compute multi-dimensional histogram."""
    arr = parse_array(data)
    hist, edges = get_np().histogramdd(arr, bins=bins)
    return {"result": {"counts": hist.tolist(), "edges": [e.tolist() for e in edges]}}


@math_command(
    name="bincount",
    category="stats",
    description="Count occurrences of each value",
    args=[
        {"name": "data", "help": "Array of non-negative ints as [0,1,1,2,2,2]"},
        {"name": "--minlength", "type": int, "default": 0, "help": "Minimum number of bins"},
    ],
)
def cmd_bincount(data: str, minlength: int = 0) -> dict:
    """Count number of occurrences of each value in array of non-negative ints."""
    arr = parse_array(data).astype(int)
    r = get_np().bincount(arr, minlength=minlength)
    return {"result": r.tolist()}


@math_command(
    name="digitize",
    category="stats",
    description="Return indices of bins to which each value belongs",
    args=[
        {"name": "data", "help": "Array as [0.2,6.4,3.0,1.6]"},
        {"name": "bins", "help": "Bin edges as [0,1,2.5,4,10]"},
    ],
)
def cmd_digitize(data: str, bins: str) -> dict:
    """Return indices of bins to which each value belongs."""
    arr = parse_array(data)
    b = parse_array(bins)
    r = get_np().digitize(arr, b)
    return {"result": r.tolist()}


@math_command(
    name="percentile",
    category="stats",
    description="Compute percentile",
    args=[
        {"name": "data", "help": "Array as [1,2,3,4,5]"},
        {"name": "q", "help": "Percentile(s) as 50 or [25,50,75]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to compute"},
    ],
)
def cmd_percentile(data: str, q: str, axis: int = None) -> dict:
    """Compute q-th percentile."""
    arr = parse_array(data)
    q_val = parse_array(q) if "[" in q else float(q)
    r = get_np().percentile(arr, q_val, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="quantile",
    category="stats",
    description="Compute quantile",
    args=[
        {"name": "data", "help": "Array as [1,2,3,4,5]"},
        {"name": "q", "help": "Quantile(s) as 0.5 or [0.25,0.5,0.75]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to compute"},
    ],
)
def cmd_quantile(data: str, q: str, axis: int = None) -> dict:
    """Compute q-th quantile."""
    arr = parse_array(data)
    q_val = parse_array(q) if "[" in q else float(q)
    r = get_np().quantile(arr, q_val, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="nanmean",
    category="stats",
    description="Mean ignoring NaNs",
    args=[
        {"name": "data", "help": "Array as [1,nan,3,4,5]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to compute"},
    ],
)
def cmd_nanmean(data: str, axis: int = None) -> dict:
    """Compute mean ignoring NaN values."""
    arr = parse_array(data)
    r = get_np().nanmean(arr, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="nanstd",
    category="stats",
    description="Standard deviation ignoring NaNs",
    args=[
        {"name": "data", "help": "Array as [1,nan,3,4,5]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to compute"},
        {"name": "--ddof", "type": int, "default": 0, "help": "Delta degrees of freedom"},
    ],
)
def cmd_nanstd(data: str, axis: int = None, ddof: int = 0) -> dict:
    """Compute standard deviation ignoring NaN values."""
    arr = parse_array(data)
    r = get_np().nanstd(arr, axis=axis, ddof=ddof)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="nanvar",
    category="stats",
    description="Variance ignoring NaNs",
    args=[
        {"name": "data", "help": "Array as [1,nan,3,4,5]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to compute"},
        {"name": "--ddof", "type": int, "default": 0, "help": "Delta degrees of freedom"},
    ],
)
def cmd_nanvar(data: str, axis: int = None, ddof: int = 0) -> dict:
    """Compute variance ignoring NaN values."""
    arr = parse_array(data)
    r = get_np().nanvar(arr, axis=axis, ddof=ddof)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="nanmedian",
    category="stats",
    description="Median ignoring NaNs",
    args=[
        {"name": "data", "help": "Array as [1,nan,3,4,5]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to compute"},
    ],
)
def cmd_nanmedian(data: str, axis: int = None) -> dict:
    """Compute median ignoring NaN values."""
    arr = parse_array(data)
    r = get_np().nanmedian(arr, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


# =============================================================================
# SORTING (16 functions)
# =============================================================================


@math_command(
    name="sort",
    category="sorting",
    description="Sort array",
    args=[
        {"name": "data", "help": "Array as [3,1,4,1,5,9]"},
        {"name": "--axis", "type": int, "default": -1, "help": "Axis along which to sort"},
    ],
)
def cmd_sort(data: str, axis: int = -1) -> dict:
    """Return sorted copy of array."""
    arr = parse_array(data)
    r = get_np().sort(arr, axis=axis)
    return {"result": r.tolist()}


@math_command(
    name="argsort",
    category="sorting",
    description="Indices that would sort array",
    args=[
        {"name": "data", "help": "Array as [3,1,4,1,5,9]"},
        {"name": "--axis", "type": int, "default": -1, "help": "Axis along which to sort"},
    ],
)
def cmd_argsort(data: str, axis: int = -1) -> dict:
    """Return indices that would sort array."""
    arr = parse_array(data)
    r = get_np().argsort(arr, axis=axis)
    return {"result": r.tolist()}


@math_command(
    name="lexsort",
    category="sorting",
    description="Indirect stable sort using sequence of keys",
    args=[{"name": "keys", "help": "Keys as [[k1],[k2],...] where last key is primary"}],
)
def cmd_lexsort(keys: str) -> dict:
    """Perform indirect stable sort using sequence of keys."""
    k = parse_array(keys)
    r = get_np().lexsort(k)
    return {"result": r.tolist()}


@math_command(
    name="partition",
    category="sorting",
    description="Partition array around kth element",
    args=[
        {"name": "data", "help": "Array as [3,4,2,1]"},
        {"name": "kth", "type": int, "help": "Index of element to partition around"},
    ],
)
def cmd_partition(data: str, kth: int) -> dict:
    """Return partitioned copy with kth element in sorted position."""
    arr = parse_array(data)
    r = get_np().partition(arr, kth)
    return {"result": r.tolist()}


@math_command(
    name="argpartition",
    category="sorting",
    description="Indices that would partition array",
    args=[
        {"name": "data", "help": "Array as [3,4,2,1]"},
        {"name": "kth", "type": int, "help": "Index of element to partition around"},
    ],
)
def cmd_argpartition(data: str, kth: int) -> dict:
    """Return indices that would partition array."""
    arr = parse_array(data)
    r = get_np().argpartition(arr, kth)
    return {"result": r.tolist()}


@math_command(
    name="searchsorted",
    category="sorting",
    description="Find indices where elements should be inserted",
    args=[
        {"name": "sorted_arr", "help": "Sorted array as [1,2,3,4,5]"},
        {"name": "values", "help": "Values to insert as [2.5,3.5]"},
        {"name": "--side", "default": "left", "help": "'left' or 'right'"},
    ],
)
def cmd_searchsorted(sorted_arr: str, values: str, side: str = "left") -> dict:
    """Find indices where elements should be inserted to maintain order."""
    a = parse_array(sorted_arr)
    v = parse_array(values)
    r = get_np().searchsorted(a, v, side=side)
    return {"result": r.tolist()}


@math_command(
    name="argmax",
    category="sorting",
    description="Index of maximum value",
    args=[
        {"name": "data", "help": "Array as [1,3,2]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to find max"},
    ],
)
def cmd_argmax(data: str, axis: int = None) -> dict:
    """Return index of maximum value."""
    arr = parse_array(data)
    r = get_np().argmax(arr, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else int(r)}


@math_command(
    name="argmin",
    category="sorting",
    description="Index of minimum value",
    args=[
        {"name": "data", "help": "Array as [3,1,2]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to find min"},
    ],
)
def cmd_argmin(data: str, axis: int = None) -> dict:
    """Return index of minimum value."""
    arr = parse_array(data)
    r = get_np().argmin(arr, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else int(r)}


@math_command(
    name="nanargmax",
    category="sorting",
    description="Index of maximum value ignoring NaNs",
    args=[
        {"name": "data", "help": "Array as [1,nan,2]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to find max"},
    ],
)
def cmd_nanargmax(data: str, axis: int = None) -> dict:
    """Return index of maximum value ignoring NaN."""
    arr = parse_array(data)
    r = get_np().nanargmax(arr, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else int(r)}


@math_command(
    name="nanargmin",
    category="sorting",
    description="Index of minimum value ignoring NaNs",
    args=[
        {"name": "data", "help": "Array as [3,nan,1]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to find min"},
    ],
)
def cmd_nanargmin(data: str, axis: int = None) -> dict:
    """Return index of minimum value ignoring NaN."""
    arr = parse_array(data)
    r = get_np().nanargmin(arr, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else int(r)}


@math_command(
    name="where",
    category="sorting",
    description="Return elements chosen from x or y depending on condition",
    args=[
        {"name": "condition", "help": "Boolean array as [true,false,true]"},
        {"name": "--x", "default": None, "help": "Values where condition is True"},
        {"name": "--y", "default": None, "help": "Values where condition is False"},
    ],
)
def cmd_where(condition: str, x: str = None, y: str = None) -> dict:
    """Return elements chosen from x or y depending on condition."""
    np = get_np()
    cond = parse_array(condition).astype(bool)
    if x is None and y is None:
        r = np.where(cond)
        return {"result": [arr.tolist() for arr in r]}
    else:
        x_arr = parse_array(x) if x else None
        y_arr = parse_array(y) if y else None
        r = np.where(cond, x_arr, y_arr)
        return {"result": r.tolist()}


@math_command(
    name="nonzero",
    category="sorting",
    description="Indices of non-zero elements",
    args=[{"name": "data", "help": "Array as [0,1,0,2,0]"}],
)
def cmd_nonzero(data: str) -> dict:
    """Return indices of non-zero elements."""
    arr = parse_array(data)
    r = get_np().nonzero(arr)
    return {"result": [arr.tolist() for arr in r]}


@math_command(
    name="flatnonzero",
    category="sorting",
    description="Indices of non-zero elements in flattened array",
    args=[{"name": "data", "help": "Array as [0,1,0,2,0]"}],
)
def cmd_flatnonzero(data: str) -> dict:
    """Return indices that are non-zero in flattened array."""
    arr = parse_array(data)
    r = get_np().flatnonzero(arr)
    return {"result": r.tolist()}


@math_command(
    name="count_nonzero",
    category="sorting",
    description="Count non-zero elements",
    args=[
        {"name": "data", "help": "Array as [0,1,0,2,0]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to count"},
    ],
)
def cmd_count_nonzero(data: str, axis: int = None) -> dict:
    """Count number of non-zero elements."""
    arr = parse_array(data)
    r = get_np().count_nonzero(arr, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else int(r)}


@math_command(
    name="argwhere",
    category="sorting",
    description="Indices of non-zero elements as array of indices",
    args=[{"name": "data", "help": "Array as [[0,1],[2,0]]"}],
)
def cmd_argwhere(data: str) -> dict:
    """Return indices of non-zero elements as (N, ndim) array."""
    arr = parse_array(data)
    r = get_np().argwhere(arr)
    return {"result": r.tolist()}


@math_command(
    name="extract",
    category="sorting",
    description="Extract elements where condition is True",
    args=[
        {"name": "condition", "help": "Boolean array as [true,false,true]"},
        {"name": "data", "help": "Array to extract from as [1,2,3]"},
    ],
)
def cmd_extract(condition: str, data: str) -> dict:
    """Return elements of array where condition is True."""
    cond = parse_array(condition).astype(bool)
    arr = parse_array(data)
    r = get_np().extract(cond, arr)
    return {"result": r.tolist()}


# =============================================================================
# REDUCTION (12 functions)
# =============================================================================


@math_command(
    name="sum",
    category="reduction",
    description="Sum of array elements",
    args=[
        {"name": "data", "help": "Array as [1,2,3,4,5]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to sum"},
    ],
)
def cmd_sum(data: str, axis: int = None) -> dict:
    """Sum of array elements."""
    arr = parse_array(data)
    r = get_np().sum(arr, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="prod",
    category="reduction",
    description="Product of array elements",
    args=[
        {"name": "data", "help": "Array as [1,2,3,4,5]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to multiply"},
    ],
)
def cmd_prod(data: str, axis: int = None) -> dict:
    """Product of array elements."""
    arr = parse_array(data)
    r = get_np().prod(arr, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="cumsum",
    category="reduction",
    description="Cumulative sum",
    args=[
        {"name": "data", "help": "Array as [1,2,3,4,5]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to cumsum"},
    ],
)
def cmd_cumsum(data: str, axis: int = None) -> dict:
    """Return cumulative sum of elements."""
    arr = parse_array(data)
    r = get_np().cumsum(arr, axis=axis)
    return {"result": r.tolist()}


@math_command(
    name="cumprod",
    category="reduction",
    description="Cumulative product",
    args=[
        {"name": "data", "help": "Array as [1,2,3,4,5]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to cumprod"},
    ],
)
def cmd_cumprod(data: str, axis: int = None) -> dict:
    """Return cumulative product of elements."""
    arr = parse_array(data)
    r = get_np().cumprod(arr, axis=axis)
    return {"result": r.tolist()}


@math_command(
    name="diff",
    category="reduction",
    description="Discrete difference along axis",
    args=[
        {"name": "data", "help": "Array as [1,2,4,7,0]"},
        {"name": "--n", "type": int, "default": 1, "help": "Number of times to differentiate"},
        {"name": "--axis", "type": int, "default": -1, "help": "Axis along which to differentiate"},
    ],
)
def cmd_diff(data: str, n: int = 1, axis: int = -1) -> dict:
    """Calculate n-th discrete difference along given axis."""
    arr = parse_array(data)
    r = get_np().diff(arr, n=n, axis=axis)
    return {"result": r.tolist()}


@math_command(
    name="gradient",
    category="reduction",
    description="Gradient of N-dimensional array",
    args=[
        {"name": "data", "help": "Array as [1,2,4,7,11]"},
        {"name": "--spacing", "type": float, "default": 1.0, "help": "Sample spacing"},
    ],
)
def cmd_gradient(data: str, spacing: float = 1.0) -> dict:
    """Return gradient of N-dimensional array."""
    arr = parse_array(data)
    r = get_np().gradient(arr, spacing)
    if isinstance(r, list):
        return {"result": [g.tolist() for g in r]}
    return {"result": r.tolist()}


@math_command(
    name="ediff1d",
    category="reduction",
    description="Differences between consecutive elements",
    args=[{"name": "data", "help": "Array as [1,2,4,7,0]"}],
)
def cmd_ediff1d(data: str) -> dict:
    """Return differences between consecutive elements of array."""
    arr = parse_array(data)
    r = get_np().ediff1d(arr)
    return {"result": r.tolist()}


@math_command(
    name="nancumsum",
    category="reduction",
    description="Cumulative sum treating NaNs as zero",
    args=[
        {"name": "data", "help": "Array as [1,nan,3,4]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to cumsum"},
    ],
)
def cmd_nancumsum(data: str, axis: int = None) -> dict:
    """Return cumulative sum of elements, treating NaN as zero."""
    arr = parse_array(data)
    r = get_np().nancumsum(arr, axis=axis)
    return {"result": r.tolist()}


@math_command(
    name="nancumprod",
    category="reduction",
    description="Cumulative product treating NaNs as one",
    args=[
        {"name": "data", "help": "Array as [1,nan,3,4]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to cumprod"},
    ],
)
def cmd_nancumprod(data: str, axis: int = None) -> dict:
    """Return cumulative product of elements, treating NaN as one."""
    arr = parse_array(data)
    r = get_np().nancumprod(arr, axis=axis)
    return {"result": r.tolist()}


@math_command(
    name="nansum",
    category="reduction",
    description="Sum treating NaNs as zero",
    args=[
        {"name": "data", "help": "Array as [1,nan,3,4]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to sum"},
    ],
)
def cmd_nansum(data: str, axis: int = None) -> dict:
    """Return sum of elements, treating NaN as zero."""
    arr = parse_array(data)
    r = get_np().nansum(arr, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="nanprod",
    category="reduction",
    description="Product treating NaNs as one",
    args=[
        {"name": "data", "help": "Array as [1,nan,3,4]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to multiply"},
    ],
)
def cmd_nanprod(data: str, axis: int = None) -> dict:
    """Return product of elements, treating NaN as one."""
    arr = parse_array(data)
    r = get_np().nanprod(arr, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


# =============================================================================
# MATH FUNCTIONS (35)
# =============================================================================


@math_command(
    name="np_sin",
    category="math",
    description="Sine (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_sin(x: str) -> dict:
    """Compute sine element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().sin(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_cos",
    category="math",
    description="Cosine (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_cos(x: str) -> dict:
    """Compute cosine element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().cos(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_tan",
    category="math",
    description="Tangent (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_tan(x: str) -> dict:
    """Compute tangent element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().tan(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_arcsin",
    category="math",
    description="Inverse sine (element-wise)",
    args=[{"name": "x", "help": "Value or array in [-1, 1]"}],
)
def cmd_np_arcsin(x: str) -> dict:
    """Compute inverse sine element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().arcsin(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_arccos",
    category="math",
    description="Inverse cosine (element-wise)",
    args=[{"name": "x", "help": "Value or array in [-1, 1]"}],
)
def cmd_np_arccos(x: str) -> dict:
    """Compute inverse cosine element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().arccos(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_arctan",
    category="math",
    description="Inverse tangent (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_arctan(x: str) -> dict:
    """Compute inverse tangent element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().arctan(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_arctan2",
    category="math",
    description="Element-wise arc tangent of y/x",
    args=[{"name": "y", "help": "Y coordinates"}, {"name": "x", "help": "X coordinates"}],
)
def cmd_np_arctan2(y: str, x: str) -> dict:
    """Compute element-wise arc tangent of y/x choosing quadrant correctly."""
    y_arr = parse_array(y) if "[" in y else float(y)
    x_arr = parse_array(x) if "[" in x else float(x)
    r = get_np().arctan2(y_arr, x_arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_hypot",
    category="math",
    description="Hypotenuse sqrt(x^2 + y^2)",
    args=[{"name": "x", "help": "First leg"}, {"name": "y", "help": "Second leg"}],
)
def cmd_np_hypot(x: str, y: str) -> dict:
    """Compute hypotenuse given the two legs of a right triangle."""
    x_arr = parse_array(x) if "[" in x else float(x)
    y_arr = parse_array(y) if "[" in y else float(y)
    r = get_np().hypot(x_arr, y_arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_sinh",
    category="math",
    description="Hyperbolic sine (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_sinh(x: str) -> dict:
    """Compute hyperbolic sine element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().sinh(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_cosh",
    category="math",
    description="Hyperbolic cosine (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_cosh(x: str) -> dict:
    """Compute hyperbolic cosine element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().cosh(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_tanh",
    category="math",
    description="Hyperbolic tangent (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_tanh(x: str) -> dict:
    """Compute hyperbolic tangent element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().tanh(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_arcsinh",
    category="math",
    description="Inverse hyperbolic sine (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_arcsinh(x: str) -> dict:
    """Compute inverse hyperbolic sine element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().arcsinh(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_arccosh",
    category="math",
    description="Inverse hyperbolic cosine (element-wise)",
    args=[{"name": "x", "help": "Value or array >= 1"}],
)
def cmd_np_arccosh(x: str) -> dict:
    """Compute inverse hyperbolic cosine element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().arccosh(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_arctanh",
    category="math",
    description="Inverse hyperbolic tangent (element-wise)",
    args=[{"name": "x", "help": "Value or array in (-1, 1)"}],
)
def cmd_np_arctanh(x: str) -> dict:
    """Compute inverse hyperbolic tangent element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().arctanh(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_exp",
    category="math",
    description="Exponential e^x (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_exp(x: str) -> dict:
    """Compute exponential element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().exp(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_exp2",
    category="math",
    description="2^x (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_exp2(x: str) -> dict:
    """Compute 2**x element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().exp2(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_expm1",
    category="math",
    description="e^x - 1 (accurate for small x)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_expm1(x: str) -> dict:
    """Compute exp(x) - 1 with better precision for small x."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().expm1(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_log",
    category="math",
    description="Natural logarithm (element-wise)",
    args=[{"name": "x", "help": "Value or array > 0"}],
)
def cmd_np_log(x: str) -> dict:
    """Compute natural logarithm element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().log(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_log2",
    category="math",
    description="Base-2 logarithm (element-wise)",
    args=[{"name": "x", "help": "Value or array > 0"}],
)
def cmd_np_log2(x: str) -> dict:
    """Compute base-2 logarithm element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().log2(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_log10",
    category="math",
    description="Base-10 logarithm (element-wise)",
    args=[{"name": "x", "help": "Value or array > 0"}],
)
def cmd_np_log10(x: str) -> dict:
    """Compute base-10 logarithm element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().log10(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_log1p",
    category="math",
    description="log(1 + x) (accurate for small x)",
    args=[{"name": "x", "help": "Value or array > -1"}],
)
def cmd_np_log1p(x: str) -> dict:
    """Compute log(1+x) with better precision for small x."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().log1p(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_power",
    category="math",
    description="x^y (element-wise)",
    args=[
        {"name": "x", "help": "Base value or array"},
        {"name": "y", "help": "Exponent value or array"},
    ],
)
def cmd_np_power(x: str, y: str) -> dict:
    """Compute x raised to power y element-wise."""
    x_arr = parse_array(x) if "[" in x else float(x)
    y_arr = parse_array(y) if "[" in y else float(y)
    r = get_np().power(x_arr, y_arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_sqrt",
    category="math",
    description="Square root (element-wise)",
    args=[{"name": "x", "help": "Value or array >= 0"}],
)
def cmd_np_sqrt(x: str) -> dict:
    """Compute square root element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().sqrt(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_cbrt",
    category="math",
    description="Cube root (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_cbrt(x: str) -> dict:
    """Compute cube root element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().cbrt(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_square",
    category="math",
    description="Square x^2 (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_square(x: str) -> dict:
    """Compute square element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().square(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_reciprocal",
    category="math",
    description="Reciprocal 1/x (element-wise)",
    args=[{"name": "x", "help": "Value or array != 0"}],
)
def cmd_np_reciprocal(x: str) -> dict:
    """Compute reciprocal 1/x element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().reciprocal(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_absolute",
    category="math",
    description="Absolute value (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_absolute(x: str) -> dict:
    """Compute absolute value element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().absolute(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_sign",
    category="math",
    description="Sign of elements (-1, 0, or 1)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_sign(x: str) -> dict:
    """Compute sign of each element (-1, 0, or 1)."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().sign(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_floor",
    category="math",
    description="Floor (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_floor(x: str) -> dict:
    """Compute floor element-wise (largest integer <= x)."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().floor(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_ceil",
    category="math",
    description="Ceiling (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_ceil(x: str) -> dict:
    """Compute ceiling element-wise (smallest integer >= x)."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().ceil(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_trunc",
    category="math",
    description="Truncate to integer (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_trunc(x: str) -> dict:
    """Truncate to integer element-wise (round toward zero)."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().trunc(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_rint",
    category="math",
    description="Round to nearest integer (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_rint(x: str) -> dict:
    """Round to nearest integer element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().rint(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_around",
    category="math",
    description="Round to given decimals",
    args=[
        {"name": "x", "help": "Value or array"},
        {"name": "--decimals", "type": int, "default": 0, "help": "Number of decimal places"},
    ],
)
def cmd_np_around(x: str, decimals: int = 0) -> dict:
    """Round to given number of decimals."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().around(arr, decimals=decimals)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_fix",
    category="math",
    description="Round toward zero (element-wise)",
    args=[{"name": "x", "help": "Value or array"}],
)
def cmd_np_fix(x: str) -> dict:
    """Round toward zero element-wise."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().fix(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_degrees",
    category="math",
    description="Convert radians to degrees",
    args=[{"name": "x", "help": "Angle(s) in radians"}],
)
def cmd_np_degrees(x: str) -> dict:
    """Convert angles from radians to degrees."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().degrees(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


@math_command(
    name="np_radians",
    category="math",
    description="Convert degrees to radians",
    args=[{"name": "x", "help": "Angle(s) in degrees"}],
)
def cmd_np_radians(x: str) -> dict:
    """Convert angles from degrees to radians."""
    arr = parse_array(x) if "[" in x else float(x)
    r = get_np().radians(arr)
    return {"result": r.tolist() if hasattr(r, "tolist") else float(r)}


# =============================================================================
# SET OPERATIONS (7)
# =============================================================================


@math_command(
    name="np_unique",
    category="set",
    description="Find unique elements",
    args=[
        {"name": "data", "help": "Array as [1,2,2,3,3,3]"},
        {
            "name": "--return-counts",
            "action": "store_true",
            "default": False,
            "help": "Also return element counts",
        },
    ],
)
def cmd_np_unique(data: str, return_counts: bool = False) -> dict:
    """Find unique elements of array."""
    arr = parse_array(data)
    if return_counts:
        unique, counts = get_np().unique(arr, return_counts=True)
        return {"result": {"unique": unique.tolist(), "counts": counts.tolist()}}
    r = get_np().unique(arr)
    return {"result": r.tolist()}


@math_command(
    name="np_intersect1d",
    category="set",
    description="Intersection of two arrays",
    args=[{"name": "a", "help": "First array"}, {"name": "b", "help": "Second array"}],
)
def cmd_np_intersect1d(a: str, b: str) -> dict:
    """Find sorted intersection of two arrays."""
    arr1 = parse_array(a)
    arr2 = parse_array(b)
    r = get_np().intersect1d(arr1, arr2)
    return {"result": r.tolist()}


@math_command(
    name="np_union1d",
    category="set",
    description="Union of two arrays",
    args=[{"name": "a", "help": "First array"}, {"name": "b", "help": "Second array"}],
)
def cmd_np_union1d(a: str, b: str) -> dict:
    """Find sorted union of two arrays."""
    arr1 = parse_array(a)
    arr2 = parse_array(b)
    r = get_np().union1d(arr1, arr2)
    return {"result": r.tolist()}


@math_command(
    name="np_setdiff1d",
    category="set",
    description="Set difference (a - b)",
    args=[{"name": "a", "help": "First array"}, {"name": "b", "help": "Second array"}],
)
def cmd_np_setdiff1d(a: str, b: str) -> dict:
    """Find set difference of two arrays (elements in a not in b)."""
    arr1 = parse_array(a)
    arr2 = parse_array(b)
    r = get_np().setdiff1d(arr1, arr2)
    return {"result": r.tolist()}


@math_command(
    name="np_setxor1d",
    category="set",
    description="Symmetric difference (XOR)",
    args=[{"name": "a", "help": "First array"}, {"name": "b", "help": "Second array"}],
)
def cmd_np_setxor1d(a: str, b: str) -> dict:
    """Find symmetric difference of two arrays (elements in exactly one)."""
    arr1 = parse_array(a)
    arr2 = parse_array(b)
    r = get_np().setxor1d(arr1, arr2)
    return {"result": r.tolist()}


@math_command(
    name="np_isin",
    category="set",
    description="Test membership of elements",
    args=[{"name": "a", "help": "Test array"}, {"name": "b", "help": "Set to test against"}],
)
def cmd_np_isin(a: str, b: str) -> dict:
    """Test whether each element of a is in b (preserves shape)."""
    arr1 = parse_array(a)
    arr2 = parse_array(b)
    r = get_np().isin(arr1, arr2)
    return {"result": r.tolist()}


# =============================================================================
# LOGIC (8)
# =============================================================================


@math_command(
    name="np_all",
    category="logic",
    description="Test whether all elements are True",
    args=[
        {"name": "data", "help": "Array as [true,true,false]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to test"},
    ],
)
def cmd_np_all(data: str, axis: int = None) -> dict:
    """Test whether all elements along axis evaluate to True."""
    arr = parse_array(data)
    r = get_np().all(arr, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else bool(r)}


@math_command(
    name="np_any",
    category="logic",
    description="Test whether any element is True",
    args=[
        {"name": "data", "help": "Array as [false,false,true]"},
        {"name": "--axis", "type": int, "default": None, "help": "Axis along which to test"},
    ],
)
def cmd_np_any(data: str, axis: int = None) -> dict:
    """Test whether any element along axis evaluates to True."""
    arr = parse_array(data)
    r = get_np().any(arr, axis=axis)
    return {"result": r.tolist() if hasattr(r, "tolist") else bool(r)}


@math_command(
    name="np_logical_and",
    category="logic",
    description="Element-wise logical AND",
    args=[{"name": "a", "help": "First array"}, {"name": "b", "help": "Second array"}],
)
def cmd_np_logical_and(a: str, b: str) -> dict:
    """Compute element-wise logical AND."""
    arr1 = parse_array(a)
    arr2 = parse_array(b)
    r = get_np().logical_and(arr1, arr2)
    return {"result": r.tolist()}


@math_command(
    name="np_logical_or",
    category="logic",
    description="Element-wise logical OR",
    args=[{"name": "a", "help": "First array"}, {"name": "b", "help": "Second array"}],
)
def cmd_np_logical_or(a: str, b: str) -> dict:
    """Compute element-wise logical OR."""
    arr1 = parse_array(a)
    arr2 = parse_array(b)
    r = get_np().logical_or(arr1, arr2)
    return {"result": r.tolist()}


@math_command(
    name="np_logical_not",
    category="logic",
    description="Element-wise logical NOT",
    args=[{"name": "data", "help": "Array as [true,false,true]"}],
)
def cmd_np_logical_not(data: str) -> dict:
    """Compute element-wise logical NOT."""
    arr = parse_array(data)
    r = get_np().logical_not(arr)
    return {"result": r.tolist()}


@math_command(
    name="np_logical_xor",
    category="logic",
    description="Element-wise logical XOR",
    args=[{"name": "a", "help": "First array"}, {"name": "b", "help": "Second array"}],
)
def cmd_np_logical_xor(a: str, b: str) -> dict:
    """Compute element-wise logical XOR."""
    arr1 = parse_array(a)
    arr2 = parse_array(b)
    r = get_np().logical_xor(arr1, arr2)
    return {"result": r.tolist()}


@math_command(
    name="np_array_equal",
    category="logic",
    description="Test if two arrays are equal",
    args=[{"name": "a", "help": "First array"}, {"name": "b", "help": "Second array"}],
)
def cmd_np_array_equal(a: str, b: str) -> dict:
    """Test if two arrays have same shape and elements."""
    arr1 = parse_array(a)
    arr2 = parse_array(b)
    r = get_np().array_equal(arr1, arr2)
    return {"result": bool(r)}


@math_command(
    name="np_array_equiv",
    category="logic",
    description="Test if two arrays are equivalent (broadcastable)",
    args=[{"name": "a", "help": "First array"}, {"name": "b", "help": "Second array"}],
)
def cmd_np_array_equiv(a: str, b: str) -> dict:
    """Test if two arrays are equivalent (broadcastable and equal elements)."""
    arr1 = parse_array(a)
    arr2 = parse_array(b)
    r = get_np().array_equiv(arr1, arr2)
    return {"result": bool(r)}


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    parser = create_main_parser(
        "numpy_compute",
        "NumPy computation CLI - Linear Algebra",
        epilog="""
Examples:
  # Determinant
  %(prog)s det "[[1,2],[3,4]]"

  # Matrix inverse
  %(prog)s inv "[[1,2],[3,4]]"

  # Eigenvalues and eigenvectors
  %(prog)s eig "[[1,2],[3,4]]"

  # SVD decomposition
  %(prog)s svd "[[1,2,3],[4,5,6]]"

  # Solve linear system
  %(prog)s solve "[[3,1],[1,2]]" "[9,8]"

  # Least squares
  %(prog)s lstsq "[[1,1],[1,2],[1,3]]" "[1,2,2]"
""",
    )
    sys.exit(main_cli(parser, get_registry()))
