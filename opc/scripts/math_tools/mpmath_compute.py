"""mpmath arbitrary-precision CLI - 153 functions across 14 categories.

USAGE:
    # Precision control (4)
    uv run python scripts/mpmath_compute.py set_dps 100
    uv run python scripts/mpmath_compute.py get_dps
    uv run python scripts/mpmath_compute.py set_prec 332
    uv run python scripts/mpmath_compute.py get_prec

    # Constants (14)
    uv run python scripts/mpmath_compute.py pi --dps 100
    uv run python scripts/mpmath_compute.py e --dps 50
    uv run python scripts/mpmath_compute.py euler --dps 30
    uv run python scripts/mpmath_compute.py catalan --dps 30
    uv run python scripts/mpmath_compute.py phi --dps 50
    uv run python scripts/mpmath_compute.py khinchin --dps 30
    uv run python scripts/mpmath_compute.py glaisher --dps 30
    uv run python scripts/mpmath_compute.py apery --dps 30
    uv run python scripts/mpmath_compute.py mertens --dps 30
    uv run python scripts/mpmath_compute.py twinprime --dps 30
    uv run python scripts/mpmath_compute.py degree --dps 30
    uv run python scripts/mpmath_compute.py inf
    uv run python scripts/mpmath_compute.py nan
    uv run python scripts/mpmath_compute.py j

    # Elementary (10)
    uv run python -m scripts.mpmath_compute mp_sqrt "2" --dps 100
    uv run python -m scripts.mpmath_compute mp_cbrt "8" --dps 50
    uv run python -m scripts.mpmath_compute mp_root "16" 4 --dps 50
    uv run python -m scripts.mpmath_compute mp_exp "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_expm1 "0.001" --dps 50
    uv run python -m scripts.mpmath_compute mp_log "2" --dps 50
    uv run python -m scripts.mpmath_compute mp_log10 "1000" --dps 50
    uv run python -m scripts.mpmath_compute mp_log1p "0.001" --dps 50
    uv run python -m scripts.mpmath_compute mp_power "2" "10" --dps 50
    uv run python -m scripts.mpmath_compute mp_lambertw "1" --dps 50

    # Trigonometric (12)
    uv run python -m scripts.mpmath_compute mp_sin "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_cos "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_tan "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_sec "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_csc "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_cot "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_asin "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_acos "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_atan "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_atan2 "1" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_sinpi "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_cospi "0.5" --dps 50

    # Hyperbolic (6)
    uv run python -m scripts.mpmath_compute mp_sinh "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_cosh "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_tanh "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_asinh "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_acosh "2" --dps 50
    uv run python -m scripts.mpmath_compute mp_atanh "0.5" --dps 50

    # Gamma functions (14)
    uv run python -m scripts.mpmath_compute mp_gamma "5" --dps 50
    uv run python -m scripts.mpmath_compute mp_rgamma "5" --dps 50
    uv run python -m scripts.mpmath_compute mp_loggamma "5" --dps 50
    uv run python -m scripts.mpmath_compute mp_factorial "10" --dps 50
    uv run python -m scripts.mpmath_compute mp_fac2 "10" --dps 50
    uv run python -m scripts.mpmath_compute mp_rf "5" "3" --dps 50
    uv run python -m scripts.mpmath_compute mp_ff "5" "3" --dps 50
    uv run python -m scripts.mpmath_compute mp_binomial "10" "5" --dps 50
    uv run python -m scripts.mpmath_compute mp_beta "2" "3" --dps 50
    uv run python -m scripts.mpmath_compute mp_betainc "2" "3" "0" "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_gammainc "2" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_digamma "5" --dps 50
    uv run python -m scripts.mpmath_compute mp_polygamma 1 "5" --dps 50
    uv run python -m scripts.mpmath_compute mp_harmonic "10" --dps 50

    # Zeta functions (8)
    uv run python -m scripts.mpmath_compute mp_zeta "2" --dps 50
    uv run python -m scripts.mpmath_compute mp_altzeta "2" --dps 50
    uv run python -m scripts.mpmath_compute mp_dirichlet "2" "1,-1" --dps 50
    uv run python -m scripts.mpmath_compute mp_polylog "2" "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_lerchphi "0.5" "2" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_stieltjes 0 --dps 50
    uv run python -m scripts.mpmath_compute mp_primezeta "2" --dps 50
    uv run python -m scripts.mpmath_compute mp_secondzeta "0.5" --dps 50

    # Hypergeometric functions (11)
    uv run python -m scripts.mpmath_compute mp_hyp0f1 "1" "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_hyp1f1 "1" "2" "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_hyp1f2 "1" "2" "3" "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_hyp2f0 "1" "2" "0.1" --dps 50
    uv run python -m scripts.mpmath_compute mp_hyp2f1 "1" "2" "3" "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_hyp2f2 "1" "2" "3" "4" "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_hyp3f2 "1" "2" "3" "4" "5" "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_hyperu "1" "2" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_hyper "1,2" "3" "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_meijerg "1" "" "0" "0.5" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_appellf1 "1" "2" "3" "4" "0.1" "0.2" --dps 50

    # Bessel functions (17)
    uv run python -m scripts.mpmath_compute mp_besselj "0" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_bessely "0" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_besseli "0" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_besselk "0" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_hankel1 "0" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_hankel2 "0" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_airyai "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_airybi "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_airyaizero 1 --dps 50
    uv run python -m scripts.mpmath_compute mp_airybizero 1 --dps 50
    uv run python -m scripts.mpmath_compute mp_struveh "0" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_struvel "0" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_kelvin "0" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_ber "0" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_bei "0" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_ker "0" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_kei "0" "1" --dps 50

    # Orthogonal polynomials (10)
    uv run python -m scripts.mpmath_compute mp_legendre 5 "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_legenp 2 1 "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_legenq 2 0 "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_chebyt 5 "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_chebyu 5 "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_hermite 5 "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_gegenbauer 5 "0.5" "0.3" --dps 50
    uv run python -m scripts.mpmath_compute mp_laguerre 5 0 "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_jacobi 5 1 2 "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_spherharm 2 1 "0.5" "0.3" --dps 50

    # Elliptic functions (14)
    uv run python -m scripts.mpmath_compute mp_ellipk "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_ellipe "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_ellipf "0.5" "0.3" --dps 50
    uv run python -m scripts.mpmath_compute mp_ellippi "0.5" "0.3" --dps 50
    uv run python -m scripts.mpmath_compute mp_elliprj "0.5" "1" "1.5" "2" --dps 50
    uv run python -m scripts.mpmath_compute mp_elliprf "0.5" "1" "1.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_elliprc "0.5" "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_elliprd "0.5" "1" "1.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_elliprg "0.5" "1" "1.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_agm "1" "2" --dps 50
    uv run python -m scripts.mpmath_compute mp_jtheta 1 "0.5" "0.1" --dps 50
    uv run python -m scripts.mpmath_compute mp_qfrom --m "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_mfrom --q "0.1" --dps 50
    uv run python -m scripts.mpmath_compute mp_kleinj "0.5+0.5j" --dps 50

    # Error/Exponential integrals (16)
    uv run python -m scripts.mpmath_compute mp_erf "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_erfc "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_erfi "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_erfinv "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_erfcinv "0.5" --dps 50
    uv run python -m scripts.mpmath_compute mp_npdf "0" --dps 50
    uv run python -m scripts.mpmath_compute mp_ncdf "0" --dps 50
    uv run python -m scripts.mpmath_compute mp_ei "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_li "2" --dps 50
    uv run python -m scripts.mpmath_compute mp_ci "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_si "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_chi "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_shi "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_fresnels "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_fresnelc "1" --dps 50
    uv run python -m scripts.mpmath_compute mp_expint 1 "1" --dps 50

    # Number theory (17)
    uv run python -m scripts.mpmath_compute mp_primepi 100
    uv run python -m scripts.mpmath_compute mp_prime 10
    uv run python -m scripts.mpmath_compute mp_isprime 17
    uv run python -m scripts.mpmath_compute mp_nextprime 10
    uv run python -m scripts.mpmath_compute mp_prevprime 10
    uv run python -m scripts.mpmath_compute mp_moebius 6
    uv run python -m scripts.mpmath_compute mp_bernoulli 10 --dps 50
    uv run python -m scripts.mpmath_compute mp_euler_number 10 --dps 50
    uv run python -m scripts.mpmath_compute mp_stirling1 5 3 --dps 50
    uv run python -m scripts.mpmath_compute mp_stirling2 5 3 --dps 50
    uv run python -m scripts.mpmath_compute mp_bell 10 --dps 50
    uv run python -m scripts.mpmath_compute mp_npartitions 100
    uv run python -m scripts.mpmath_compute mp_fibonacci 50 --dps 50
    uv run python -m scripts.mpmath_compute mp_lucas 50 --dps 50
    uv run python -m scripts.mpmath_compute mp_gcd 48 18
    uv run python -m scripts.mpmath_compute mp_lcm 12 18
    uv run python -m scripts.mpmath_compute mp_isqrt 1000
"""

import sys

from scripts.math_base import (
    create_main_parser,
    get_registry,
    main_cli,
    math_command,
    parse_bound,
    parse_callable,
    parse_complex,
    parse_matrix,
)

# =============================================================================
# PRECISION (4 functions)
# =============================================================================


@math_command(
    name="set_dps",
    category="precision",
    description="Set decimal places for mpmath computations",
    args=[{"name": "dps", "type": int, "help": "Number of decimal places"}],
)
def cmd_set_dps(dps: int) -> dict:
    """Set the number of decimal places for all mpmath operations."""
    from mpmath import mp

    mp.dps = dps
    return {"result": dps, "description": f"Decimal places set to {dps}"}


@math_command(
    name="get_dps", category="precision", description="Get current decimal places setting", args=[]
)
def cmd_get_dps() -> dict:
    """Get the current number of decimal places."""
    from mpmath import mp

    return {"result": mp.dps, "description": "Current decimal places"}


@math_command(
    name="set_prec",
    category="precision",
    description="Set binary precision (bits) for mpmath computations",
    args=[{"name": "prec", "type": int, "help": "Number of bits of precision"}],
)
def cmd_set_prec(prec: int) -> dict:
    """Set the binary precision (number of bits) for all mpmath operations."""
    from mpmath import mp

    mp.prec = prec
    return {
        "result": prec,
        "dps_equivalent": mp.dps,
        "description": f"Binary precision set to {prec} bits (~{mp.dps} decimal places)",
    }


@math_command(
    name="get_prec",
    category="precision",
    description="Get current binary precision setting",
    args=[],
)
def cmd_get_prec() -> dict:
    """Get the current binary precision (bits)."""
    from mpmath import mp

    return {
        "result": mp.prec,
        "dps_equivalent": mp.dps,
        "description": f"Current binary precision: {mp.prec} bits (~{mp.dps} decimal places)",
    }


# =============================================================================
# CONSTANTS (14 functions)
# =============================================================================


@math_command(
    name="pi",
    category="constants",
    description="Pi (ratio of circumference to diameter) to arbitrary precision",
    latex_template=r"\pi = {result}",
    args=[{"name": "--dps", "type": int, "default": 50, "help": "Decimal places"}],
)
def cmd_pi(dps: int = 50) -> dict:
    """Compute pi to arbitrary precision."""
    from mpmath import mp

    mp.dps = dps
    return {"result": str(mp.pi), "dps": dps}


@math_command(
    name="e",
    category="constants",
    description="Euler's number (base of natural logarithm) to arbitrary precision",
    latex_template=r"e = {result}",
    args=[{"name": "--dps", "type": int, "default": 50, "help": "Decimal places"}],
)
def cmd_e(dps: int = 50) -> dict:
    """Compute e (Euler's number) to arbitrary precision."""
    from mpmath import mp

    mp.dps = dps
    return {"result": str(mp.e), "dps": dps}


@math_command(
    name="euler",
    category="constants",
    description="Euler-Mascheroni constant (gamma) to arbitrary precision",
    latex_template=r"\gamma = {result}",
    args=[{"name": "--dps", "type": int, "default": 50, "help": "Decimal places"}],
)
def cmd_euler(dps: int = 50) -> dict:
    """Compute the Euler-Mascheroni constant (gamma).

    gamma = lim(n->inf) [1 + 1/2 + 1/3 + ... + 1/n - ln(n)]
    """
    from mpmath import mp

    mp.dps = dps
    return {"result": str(mp.euler), "dps": dps}


@math_command(
    name="catalan",
    category="constants",
    description="Catalan's constant to arbitrary precision",
    latex_template=r"G = {result}",
    args=[{"name": "--dps", "type": int, "default": 50, "help": "Decimal places"}],
)
def cmd_catalan(dps: int = 50) -> dict:
    """Compute Catalan's constant.

    G = sum(k=0 to inf) [(-1)^k / (2k+1)^2]
    """
    from mpmath import mp

    mp.dps = dps
    return {"result": str(mp.catalan), "dps": dps}


@math_command(
    name="phi",
    category="constants",
    description="Golden ratio to arbitrary precision",
    latex_template=r"\phi = {result}",
    args=[{"name": "--dps", "type": int, "default": 50, "help": "Decimal places"}],
)
def cmd_phi(dps: int = 50) -> dict:
    """Compute the golden ratio.

    phi = (1 + sqrt(5)) / 2
    """
    from mpmath import mp

    mp.dps = dps
    return {"result": str(mp.phi), "dps": dps}


@math_command(
    name="khinchin",
    category="constants",
    description="Khinchin's constant to arbitrary precision",
    latex_template=r"K_0 = {result}",
    args=[{"name": "--dps", "type": int, "default": 50, "help": "Decimal places"}],
)
def cmd_khinchin(dps: int = 50) -> dict:
    """Compute Khinchin's constant.

    The geometric mean of the continued fraction coefficients of
    almost all real numbers.
    """
    from mpmath import mp

    mp.dps = dps
    return {"result": str(mp.khinchin), "dps": dps}


@math_command(
    name="glaisher",
    category="constants",
    description="Glaisher-Kinkelin constant to arbitrary precision",
    latex_template=r"A = {result}",
    args=[{"name": "--dps", "type": int, "default": 50, "help": "Decimal places"}],
)
def cmd_glaisher(dps: int = 50) -> dict:
    """Compute the Glaisher-Kinkelin constant.

    Related to the derivative of the Riemann zeta function.
    """
    from mpmath import mp

    mp.dps = dps
    return {"result": str(mp.glaisher), "dps": dps}


@math_command(
    name="apery",
    category="constants",
    description="Apery's constant (zeta(3)) to arbitrary precision",
    latex_template=r"\zeta(3) = {result}",
    args=[{"name": "--dps", "type": int, "default": 50, "help": "Decimal places"}],
)
def cmd_apery(dps: int = 50) -> dict:
    """Compute Apery's constant.

    zeta(3) = 1 + 1/8 + 1/27 + 1/64 + ...
    """
    from mpmath import mp

    mp.dps = dps
    return {"result": str(mp.apery), "dps": dps}


@math_command(
    name="mertens",
    category="constants",
    description="Meissel-Mertens constant to arbitrary precision",
    latex_template=r"M = {result}",
    args=[{"name": "--dps", "type": int, "default": 50, "help": "Decimal places"}],
)
def cmd_mertens(dps: int = 50) -> dict:
    """Compute the Meissel-Mertens constant.

    Related to the sum of reciprocals of primes.
    """
    from mpmath import mp

    mp.dps = dps
    return {"result": str(mp.mertens), "dps": dps}


@math_command(
    name="twinprime",
    category="constants",
    description="Twin prime constant to arbitrary precision",
    latex_template=r"C_2 = {result}",
    args=[{"name": "--dps", "type": int, "default": 50, "help": "Decimal places"}],
)
def cmd_twinprime(dps: int = 50) -> dict:
    """Compute the twin prime constant.

    Related to the density of twin primes.
    """
    from mpmath import mp

    mp.dps = dps
    return {"result": str(mp.twinprime), "dps": dps}


@math_command(
    name="degree",
    category="constants",
    description="One degree in radians (pi/180)",
    latex_template=r"1^{{\circ}} = {result}\text{{ rad}}",
    args=[{"name": "--dps", "type": int, "default": 50, "help": "Decimal places"}],
)
def cmd_degree(dps: int = 50) -> dict:
    """Compute one degree in radians.

    degree = pi / 180
    """
    from mpmath import mp

    mp.dps = dps
    return {"result": str(mp.degree), "dps": dps}


@math_command(
    name="inf",
    category="constants",
    description="Positive infinity representation in mpmath",
    latex_template=r"+\infty",
    args=[],
)
def cmd_inf() -> dict:
    """Return mpmath's positive infinity representation."""
    from mpmath import mp

    return {"result": str(mp.inf), "type": "infinity"}


@math_command(
    name="nan",
    category="constants",
    description="Not-a-Number representation in mpmath",
    latex_template=None,  # No template - {NaN} in LaTeX conflicts with .format()
    args=[],
)
def cmd_nan() -> dict:
    """Return mpmath's NaN (Not a Number) representation."""
    from mpmath import mp

    return {"result": str(mp.nan), "type": "nan", "latex": r"\text{NaN}"}


@math_command(
    name="j",
    category="constants",
    description="Imaginary unit (sqrt(-1))",
    latex_template=None,  # No template - using double braces is confusing
    args=[],
)
def cmd_j() -> dict:
    """Return the imaginary unit.

    j = sqrt(-1) = i
    """
    from mpmath import mp

    return {
        "result": str(mp.j),
        "type": "imaginary_unit",
        "real": 0,
        "imag": 1,
        "latex": r"j = \sqrt{-1}",
    }


# =============================================================================
# ELEMENTARY (10 functions)
# =============================================================================


@math_command(
    name="mp_sqrt",
    category="elementary",
    description="Arbitrary precision square root",
    args=[
        {"name": "x", "help": "Number to take square root of"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_sqrt(x: str, dps: int = 50) -> dict:
    """Compute square root to arbitrary precision."""
    from mpmath import mp, sqrt

    mp.dps = dps
    r = sqrt(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\sqrt{{{x}}} = {r}"}


@math_command(
    name="mp_cbrt",
    category="elementary",
    description="Arbitrary precision cube root",
    args=[
        {"name": "x", "help": "Number to take cube root of"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_cbrt(x: str, dps: int = 50) -> dict:
    """Compute cube root to arbitrary precision."""
    from mpmath import cbrt, mp

    mp.dps = dps
    r = cbrt(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\sqrt[3]{{{x}}} = {r}"}


@math_command(
    name="mp_root",
    category="elementary",
    description="Arbitrary precision n-th root",
    args=[
        {"name": "x", "help": "Number to take root of"},
        {"name": "n", "type": int, "help": "Root degree"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_root(x: str, n: int, dps: int = 50) -> dict:
    """Compute n-th root to arbitrary precision."""
    from mpmath import mp, root

    mp.dps = dps
    r = root(mp.mpf(x), n)
    return {"result": str(r), "input": x, "n": n, "dps": dps, "latex": rf"\sqrt[{n}]{{{x}}} = {r}"}


@math_command(
    name="mp_exp",
    category="elementary",
    description="Arbitrary precision exponential (e^x)",
    args=[
        {"name": "x", "help": "Exponent"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_exp(x: str, dps: int = 50) -> dict:
    """Compute e^x to arbitrary precision."""
    from mpmath import exp, mp

    mp.dps = dps
    r = exp(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"e^{{{x}}} = {r}"}


@math_command(
    name="mp_expm1",
    category="elementary",
    description="Arbitrary precision exp(x) - 1 (accurate for small x)",
    args=[
        {"name": "x", "help": "Exponent"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_expm1(x: str, dps: int = 50) -> dict:
    """Compute exp(x) - 1 to arbitrary precision. Accurate for small x."""
    from mpmath import expm1, mp

    mp.dps = dps
    r = expm1(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"e^{{{x}}} - 1 = {r}"}


@math_command(
    name="mp_log",
    category="elementary",
    description="Arbitrary precision natural logarithm",
    args=[
        {"name": "x", "help": "Number to take log of"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_log(x: str, dps: int = 50) -> dict:
    """Compute natural logarithm to arbitrary precision."""
    from mpmath import log, mp

    mp.dps = dps
    r = log(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\ln({x}) = {r}"}


@math_command(
    name="mp_log10",
    category="elementary",
    description="Arbitrary precision base-10 logarithm",
    args=[
        {"name": "x", "help": "Number to take log of"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_log10(x: str, dps: int = 50) -> dict:
    """Compute base-10 logarithm to arbitrary precision."""
    from mpmath import log10, mp

    mp.dps = dps
    r = log10(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\log_{{10}}({x}) = {r}"}


@math_command(
    name="mp_log1p",
    category="elementary",
    description="Arbitrary precision log(1 + x) (accurate for small x)",
    args=[
        {"name": "x", "help": "Number (computes log(1+x))"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_log1p(x: str, dps: int = 50) -> dict:
    """Compute log(1 + x) to arbitrary precision. Accurate for small x."""
    from mpmath import log1p, mp

    mp.dps = dps
    r = log1p(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\ln(1 + {x}) = {r}"}


@math_command(
    name="mp_power",
    category="elementary",
    description="Arbitrary precision power (x^y)",
    args=[
        {"name": "x", "help": "Base"},
        {"name": "y", "help": "Exponent"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_power(x: str, y: str, dps: int = 50) -> dict:
    """Compute x^y to arbitrary precision."""
    from mpmath import mp, power

    mp.dps = dps
    r = power(mp.mpf(x), mp.mpf(y))
    return {"result": str(r), "base": x, "exponent": y, "dps": dps, "latex": rf"{x}^{{{y}}} = {r}"}


@math_command(
    name="mp_lambertw",
    category="elementary",
    description="Arbitrary precision Lambert W function (principal branch)",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--k", "type": int, "default": 0, "help": "Branch index (0=principal)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_lambertw(x: str, k: int = 0, dps: int = 50) -> dict:
    """Compute Lambert W function to arbitrary precision.

    W(x) is the inverse of f(w) = w * e^w.
    k=0 gives principal branch, k=-1 gives secondary real branch.
    """
    from mpmath import lambertw, mp

    mp.dps = dps
    r = lambertw(mp.mpf(x), k)
    return {"result": str(r), "input": x, "branch": k, "dps": dps, "latex": rf"W({x}) = {r}"}


# =============================================================================
# TRIGONOMETRIC (12 functions)
# =============================================================================


@math_command(
    name="mp_sin",
    category="trigonometric",
    description="Arbitrary precision sine",
    args=[
        {"name": "x", "help": "Angle in radians"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_sin(x: str, dps: int = 50) -> dict:
    """Compute sine to arbitrary precision."""
    from mpmath import mp, sin

    mp.dps = dps
    r = sin(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\sin({x}) = {r}"}


@math_command(
    name="mp_cos",
    category="trigonometric",
    description="Arbitrary precision cosine",
    args=[
        {"name": "x", "help": "Angle in radians"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_cos(x: str, dps: int = 50) -> dict:
    """Compute cosine to arbitrary precision."""
    from mpmath import cos, mp

    mp.dps = dps
    r = cos(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\cos({x}) = {r}"}


@math_command(
    name="mp_tan",
    category="trigonometric",
    description="Arbitrary precision tangent",
    args=[
        {"name": "x", "help": "Angle in radians"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_tan(x: str, dps: int = 50) -> dict:
    """Compute tangent to arbitrary precision."""
    from mpmath import mp, tan

    mp.dps = dps
    r = tan(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\tan({x}) = {r}"}


@math_command(
    name="mp_sec",
    category="trigonometric",
    description="Arbitrary precision secant",
    args=[
        {"name": "x", "help": "Angle in radians"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_sec(x: str, dps: int = 50) -> dict:
    """Compute secant to arbitrary precision."""
    from mpmath import mp, sec

    mp.dps = dps
    r = sec(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\sec({x}) = {r}"}


@math_command(
    name="mp_csc",
    category="trigonometric",
    description="Arbitrary precision cosecant",
    args=[
        {"name": "x", "help": "Angle in radians"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_csc(x: str, dps: int = 50) -> dict:
    """Compute cosecant to arbitrary precision."""
    from mpmath import csc, mp

    mp.dps = dps
    r = csc(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\csc({x}) = {r}"}


@math_command(
    name="mp_cot",
    category="trigonometric",
    description="Arbitrary precision cotangent",
    args=[
        {"name": "x", "help": "Angle in radians"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_cot(x: str, dps: int = 50) -> dict:
    """Compute cotangent to arbitrary precision."""
    from mpmath import cot, mp

    mp.dps = dps
    r = cot(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\cot({x}) = {r}"}


@math_command(
    name="mp_asin",
    category="trigonometric",
    description="Arbitrary precision arcsine",
    args=[
        {"name": "x", "help": "Value in [-1, 1]"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_asin(x: str, dps: int = 50) -> dict:
    """Compute arcsine to arbitrary precision. Returns radians."""
    from mpmath import asin, mp

    mp.dps = dps
    r = asin(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\arcsin({x}) = {r}"}


@math_command(
    name="mp_acos",
    category="trigonometric",
    description="Arbitrary precision arccosine",
    args=[
        {"name": "x", "help": "Value in [-1, 1]"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_acos(x: str, dps: int = 50) -> dict:
    """Compute arccosine to arbitrary precision. Returns radians."""
    from mpmath import acos, mp

    mp.dps = dps
    r = acos(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\arccos({x}) = {r}"}


@math_command(
    name="mp_atan",
    category="trigonometric",
    description="Arbitrary precision arctangent",
    args=[
        {"name": "x", "help": "Value"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_atan(x: str, dps: int = 50) -> dict:
    """Compute arctangent to arbitrary precision. Returns radians."""
    from mpmath import atan, mp

    mp.dps = dps
    r = atan(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\arctan({x}) = {r}"}


@math_command(
    name="mp_atan2",
    category="trigonometric",
    description="Arbitrary precision two-argument arctangent",
    args=[
        {"name": "y", "help": "Y coordinate"},
        {"name": "x", "help": "X coordinate"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_atan2(y: str, x: str, dps: int = 50) -> dict:
    """Compute atan2(y, x) to arbitrary precision. Returns radians in [-pi, pi]."""
    from mpmath import atan2, mp

    mp.dps = dps
    r = atan2(mp.mpf(y), mp.mpf(x))
    return {"result": str(r), "y": y, "x": x, "dps": dps, "latex": rf"\arctan2({y}, {x}) = {r}"}


@math_command(
    name="mp_sinpi",
    category="trigonometric",
    description="Arbitrary precision sin(pi * x) (exact for integers)",
    args=[
        {"name": "x", "help": "Multiplier of pi"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_sinpi(x: str, dps: int = 50) -> dict:
    """Compute sin(pi * x) to arbitrary precision.

    More accurate than sin(pi * x) for integer and half-integer values.
    """
    from mpmath import mp, sinpi

    mp.dps = dps
    r = sinpi(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\sin(\pi \cdot {x}) = {r}"}


@math_command(
    name="mp_cospi",
    category="trigonometric",
    description="Arbitrary precision cos(pi * x) (exact for integers)",
    args=[
        {"name": "x", "help": "Multiplier of pi"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_cospi(x: str, dps: int = 50) -> dict:
    """Compute cos(pi * x) to arbitrary precision.

    More accurate than cos(pi * x) for integer and half-integer values.
    """
    from mpmath import cospi, mp

    mp.dps = dps
    r = cospi(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\cos(\pi \cdot {x}) = {r}"}


# =============================================================================
# HYPERBOLIC (6 functions)
# =============================================================================


@math_command(
    name="mp_sinh",
    category="hyperbolic",
    description="Arbitrary precision hyperbolic sine",
    args=[
        {"name": "x", "help": "Value"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_sinh(x: str, dps: int = 50) -> dict:
    """Compute hyperbolic sine to arbitrary precision."""
    from mpmath import mp, sinh

    mp.dps = dps
    r = sinh(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\sinh({x}) = {r}"}


@math_command(
    name="mp_cosh",
    category="hyperbolic",
    description="Arbitrary precision hyperbolic cosine",
    args=[
        {"name": "x", "help": "Value"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_cosh(x: str, dps: int = 50) -> dict:
    """Compute hyperbolic cosine to arbitrary precision."""
    from mpmath import cosh, mp

    mp.dps = dps
    r = cosh(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\cosh({x}) = {r}"}


@math_command(
    name="mp_tanh",
    category="hyperbolic",
    description="Arbitrary precision hyperbolic tangent",
    args=[
        {"name": "x", "help": "Value"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_tanh(x: str, dps: int = 50) -> dict:
    """Compute hyperbolic tangent to arbitrary precision."""
    from mpmath import mp, tanh

    mp.dps = dps
    r = tanh(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\tanh({x}) = {r}"}


@math_command(
    name="mp_asinh",
    category="hyperbolic",
    description="Arbitrary precision inverse hyperbolic sine",
    args=[
        {"name": "x", "help": "Value"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_asinh(x: str, dps: int = 50) -> dict:
    """Compute inverse hyperbolic sine to arbitrary precision."""
    from mpmath import asinh, mp

    mp.dps = dps
    r = asinh(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\text{{asinh}}({x}) = {r}"}


@math_command(
    name="mp_acosh",
    category="hyperbolic",
    description="Arbitrary precision inverse hyperbolic cosine",
    args=[
        {"name": "x", "help": "Value >= 1"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_acosh(x: str, dps: int = 50) -> dict:
    """Compute inverse hyperbolic cosine to arbitrary precision."""
    from mpmath import acosh, mp

    mp.dps = dps
    r = acosh(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\text{{acosh}}({x}) = {r}"}


@math_command(
    name="mp_atanh",
    category="hyperbolic",
    description="Arbitrary precision inverse hyperbolic tangent",
    args=[
        {"name": "x", "help": "Value in (-1, 1)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_atanh(x: str, dps: int = 50) -> dict:
    """Compute inverse hyperbolic tangent to arbitrary precision."""
    from mpmath import atanh, mp

    mp.dps = dps
    r = atanh(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\text{{atanh}}({x}) = {r}"}


# =============================================================================
# GAMMA FUNCTIONS (14 functions)
# =============================================================================


@math_command(
    name="mp_gamma",
    category="gamma",
    description="Gamma function",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_gamma(x: str, dps: int = 50) -> dict:
    """Compute the gamma function to arbitrary precision.

    Gamma(n) = (n-1)! for positive integers.
    """
    from mpmath import gamma, mp

    mp.dps = dps
    r = gamma(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\Gamma({x}) = {r}"}


@math_command(
    name="mp_rgamma",
    category="gamma",
    description="Reciprocal gamma function (1/Gamma(x))",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_rgamma(x: str, dps: int = 50) -> dict:
    """Compute the reciprocal gamma function to arbitrary precision.

    rgamma(x) = 1/Gamma(x), entire function (no poles).
    """
    from mpmath import mp, rgamma

    mp.dps = dps
    r = rgamma(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"1/\Gamma({x}) = {r}"}


@math_command(
    name="mp_loggamma",
    category="gamma",
    description="Log-gamma function (ln(Gamma(x)))",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_loggamma(x: str, dps: int = 50) -> dict:
    """Compute the log-gamma function to arbitrary precision.

    loggamma(x) = ln(Gamma(x)), principal branch.
    """
    from mpmath import loggamma, mp

    mp.dps = dps
    r = loggamma(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\ln\Gamma({x}) = {r}"}


@math_command(
    name="mp_factorial",
    category="gamma",
    description="Factorial (n!)",
    args=[
        {"name": "n", "help": "Non-negative integer or real number"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_factorial(n: str, dps: int = 50) -> dict:
    """Compute factorial to arbitrary precision.

    n! = Gamma(n+1) for non-negative integers.
    """
    from mpmath import factorial, mp

    mp.dps = dps
    r = factorial(mp.mpf(n))
    return {"result": str(r), "input": n, "dps": dps, "latex": rf"{n}! = {r}"}


@math_command(
    name="mp_fac2",
    category="gamma",
    description="Double factorial (n!!)",
    args=[
        {"name": "n", "help": "Integer"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_fac2(n: str, dps: int = 50) -> dict:
    """Compute double factorial to arbitrary precision.

    n!! = n * (n-2) * (n-4) * ... * (1 or 2)
    """
    from mpmath import fac2, mp

    mp.dps = dps
    r = fac2(mp.mpf(n))
    return {"result": str(r), "input": n, "dps": dps, "latex": rf"{n}!! = {r}"}


@math_command(
    name="mp_rf",
    category="gamma",
    description="Rising factorial (Pochhammer symbol)",
    args=[
        {"name": "x", "help": "Base"},
        {"name": "n", "help": "Number of factors"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_rf(x: str, n: str, dps: int = 50) -> dict:
    """Compute rising factorial to arbitrary precision.

    (x)_n = x * (x+1) * (x+2) * ... * (x+n-1) = Gamma(x+n)/Gamma(x)
    """
    from mpmath import mp, rf

    mp.dps = dps
    r = rf(mp.mpf(x), mp.mpf(n))
    return {"result": str(r), "x": x, "n": n, "dps": dps, "latex": rf"({x})_{{{n}}} = {r}"}


@math_command(
    name="mp_ff",
    category="gamma",
    description="Falling factorial",
    args=[
        {"name": "x", "help": "Base"},
        {"name": "n", "help": "Number of factors"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_ff(x: str, n: str, dps: int = 50) -> dict:
    """Compute falling factorial to arbitrary precision.

    x_(n) = x * (x-1) * (x-2) * ... * (x-n+1)
    """
    from mpmath import ff, mp

    mp.dps = dps
    r = ff(mp.mpf(x), mp.mpf(n))
    return {"result": str(r), "x": x, "n": n, "dps": dps, "latex": rf"{x}^{{({n})}} = {r}"}


@math_command(
    name="mp_binomial",
    category="gamma",
    description="Binomial coefficient (n choose k)",
    args=[
        {"name": "n", "help": "Total items"},
        {"name": "k", "help": "Items to choose"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_binomial(n: str, k: str, dps: int = 50) -> dict:
    """Compute binomial coefficient to arbitrary precision.

    C(n,k) = n! / (k! * (n-k)!)
    """
    from mpmath import binomial, mp

    mp.dps = dps
    r = binomial(mp.mpf(n), mp.mpf(k))
    return {"result": str(r), "n": n, "k": k, "dps": dps, "latex": rf"\binom{{{n}}}{{{k}}} = {r}"}


@math_command(
    name="mp_beta",
    category="gamma",
    description="Beta function B(a, b)",
    args=[
        {"name": "a", "help": "First parameter"},
        {"name": "b", "help": "Second parameter"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_beta(a: str, b: str, dps: int = 50) -> dict:
    """Compute the beta function to arbitrary precision.

    B(a,b) = Gamma(a)*Gamma(b)/Gamma(a+b)
    """
    from mpmath import beta, mp

    mp.dps = dps
    r = beta(mp.mpf(a), mp.mpf(b))
    return {"result": str(r), "a": a, "b": b, "dps": dps, "latex": rf"B({a}, {b}) = {r}"}


@math_command(
    name="mp_betainc",
    category="gamma",
    description="Incomplete beta function",
    args=[
        {"name": "a", "help": "First parameter"},
        {"name": "b", "help": "Second parameter"},
        {"name": "x1", "help": "Lower limit (default 0)", "default": "0"},
        {"name": "x2", "help": "Upper limit (default 1)", "default": "1"},
        {"name": "--regularized", "action": "store_true", "help": "Return regularized form"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_betainc(
    a: str, b: str, x1: str = "0", x2: str = "1", regularized: bool = False, dps: int = 50
) -> dict:
    """Compute incomplete beta function to arbitrary precision.

    B(a,b;x1,x2) = integral from x1 to x2 of t^(a-1)*(1-t)^(b-1) dt
    """
    from mpmath import betainc, mp

    mp.dps = dps
    r = betainc(mp.mpf(a), mp.mpf(b), mp.mpf(x1), mp.mpf(x2), regularized=regularized)
    return {
        "result": str(r),
        "a": a,
        "b": b,
        "x1": x1,
        "x2": x2,
        "regularized": regularized,
        "dps": dps,
    }


@math_command(
    name="mp_gammainc",
    category="gamma",
    description="Incomplete gamma function",
    args=[
        {"name": "a", "help": "Parameter"},
        {"name": "z", "help": "Upper limit (or lower if --lower)"},
        {"name": "--regularized", "action": "store_true", "help": "Return regularized form"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_gammainc(a: str, z: str, regularized: bool = False, dps: int = 50) -> dict:
    """Compute incomplete gamma function to arbitrary precision.

    Gamma(a, z) = integral from z to inf of t^(a-1)*e^(-t) dt
    """
    from mpmath import gammainc, mp

    mp.dps = dps
    r = gammainc(mp.mpf(a), mp.mpf(z), regularized=regularized)
    return {
        "result": str(r),
        "a": a,
        "z": z,
        "regularized": regularized,
        "dps": dps,
        "latex": rf"\Gamma({a}, {z}) = {r}",
    }


@math_command(
    name="mp_digamma",
    category="gamma",
    description="Digamma function (psi(x) = d/dx ln(Gamma(x)))",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_digamma(x: str, dps: int = 50) -> dict:
    """Compute the digamma function to arbitrary precision.

    psi(x) = Gamma'(x)/Gamma(x) = d/dx ln(Gamma(x))
    """
    from mpmath import digamma, mp

    mp.dps = dps
    r = digamma(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\psi({x}) = {r}"}


@math_command(
    name="mp_polygamma",
    category="gamma",
    description="Polygamma function (n-th derivative of digamma)",
    args=[
        {"name": "n", "type": int, "help": "Order of derivative"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_polygamma(n: int, x: str, dps: int = 50) -> dict:
    """Compute the polygamma function to arbitrary precision.

    psi^(n)(x) = d^n/dx^n psi(x)
    """
    from mpmath import mp, psi

    mp.dps = dps
    r = psi(n, mp.mpf(x))
    return {"result": str(r), "n": n, "x": x, "dps": dps, "latex": rf"\psi^{{({n})}}({x}) = {r}"}


@math_command(
    name="mp_harmonic",
    category="gamma",
    description="Harmonic number H_n",
    args=[
        {"name": "n", "help": "Index (can be non-integer)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_harmonic(n: str, dps: int = 50) -> dict:
    """Compute harmonic number to arbitrary precision.

    H_n = 1 + 1/2 + 1/3 + ... + 1/n = psi(n+1) + gamma
    """
    from mpmath import harmonic, mp

    mp.dps = dps
    r = harmonic(mp.mpf(n))
    return {"result": str(r), "input": n, "dps": dps, "latex": rf"H_{{{n}}} = {r}"}


# =============================================================================
# ZETA FUNCTIONS (8 functions)
# =============================================================================


@math_command(
    name="mp_zeta",
    category="zeta",
    description="Riemann zeta function",
    args=[
        {"name": "s", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_zeta(s: str, dps: int = 50) -> dict:
    """Compute the Riemann zeta function to arbitrary precision.

    zeta(s) = sum(n=1 to inf) 1/n^s
    """
    from mpmath import mp, zeta

    mp.dps = dps
    r = zeta(mp.mpf(s))
    return {"result": str(r), "input": s, "dps": dps, "latex": rf"\zeta({s}) = {r}"}


@math_command(
    name="mp_altzeta",
    category="zeta",
    description="Dirichlet eta function (alternating zeta)",
    args=[
        {"name": "s", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_altzeta(s: str, dps: int = 50) -> dict:
    """Compute the alternating zeta (Dirichlet eta) function to arbitrary precision.

    eta(s) = sum(n=1 to inf) (-1)^(n-1)/n^s = (1 - 2^(1-s))*zeta(s)
    """
    from mpmath import altzeta, mp

    mp.dps = dps
    r = altzeta(mp.mpf(s))
    return {"result": str(r), "input": s, "dps": dps, "latex": rf"\eta({s}) = {r}"}


@math_command(
    name="mp_dirichlet",
    category="zeta",
    description="Dirichlet L-function",
    args=[
        {"name": "s", "help": "Argument"},
        {"name": "chi", "help": "Character as comma-separated values (e.g., '1,-1')"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_dirichlet(s: str, chi: str, dps: int = 50) -> dict:
    """Compute the Dirichlet L-function to arbitrary precision.

    L(s, chi) = sum(n=1 to inf) chi(n)/n^s
    """
    from mpmath import dirichlet, mp

    mp.dps = dps
    chi_vals = [int(c.strip()) for c in chi.split(",")]
    r = dirichlet(mp.mpf(s), chi_vals)
    return {"result": str(r), "s": s, "chi": chi_vals, "dps": dps}


@math_command(
    name="mp_polylog",
    category="zeta",
    description="Polylogarithm Li_s(z)",
    args=[
        {"name": "s", "help": "Order"},
        {"name": "z", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_polylog(s: str, z: str, dps: int = 50) -> dict:
    """Compute the polylogarithm to arbitrary precision.

    Li_s(z) = sum(k=1 to inf) z^k/k^s
    """
    from mpmath import mp, polylog

    mp.dps = dps
    r = polylog(mp.mpf(s), mp.mpf(z))
    return {
        "result": str(r),
        "s": s,
        "z": z,
        "dps": dps,
        "latex": rf"\text{{Li}}_{{{s}}}({z}) = {r}",
    }


@math_command(
    name="mp_lerchphi",
    category="zeta",
    description="Lerch transcendent Phi(z, s, a)",
    args=[
        {"name": "z", "help": "Argument z"},
        {"name": "s", "help": "Argument s"},
        {"name": "a", "help": "Argument a"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_lerchphi(z: str, s: str, a: str, dps: int = 50) -> dict:
    """Compute the Lerch transcendent to arbitrary precision.

    Phi(z, s, a) = sum(n=0 to inf) z^n/(n+a)^s
    """
    from mpmath import lerchphi, mp

    mp.dps = dps
    r = lerchphi(mp.mpf(z), mp.mpf(s), mp.mpf(a))
    return {
        "result": str(r),
        "z": z,
        "s": s,
        "a": a,
        "dps": dps,
        "latex": rf"\Phi({z}, {s}, {a}) = {r}",
    }


@math_command(
    name="mp_stieltjes",
    category="zeta",
    description="Stieltjes constant gamma_n",
    args=[
        {"name": "n", "type": int, "help": "Index (0 = Euler-Mascheroni constant)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_stieltjes(n: int, dps: int = 50) -> dict:
    """Compute the n-th Stieltjes constant to arbitrary precision.

    gamma_0 = Euler-Mascheroni constant
    gamma_n appears in Laurent expansion of zeta(s) around s=1
    """
    from mpmath import mp, stieltjes

    mp.dps = dps
    r = stieltjes(n)
    return {"result": str(r), "n": n, "dps": dps, "latex": rf"\gamma_{{{n}}} = {r}"}


@math_command(
    name="mp_primezeta",
    category="zeta",
    description="Prime zeta function P(s)",
    args=[
        {"name": "s", "help": "Argument (Re(s) > 1)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_primezeta(s: str, dps: int = 50) -> dict:
    """Compute the prime zeta function to arbitrary precision.

    P(s) = sum over primes p of 1/p^s
    """
    from mpmath import mp, primezeta

    mp.dps = dps
    r = primezeta(mp.mpf(s))
    return {"result": str(r), "input": s, "dps": dps, "latex": rf"P({s}) = {r}"}


@math_command(
    name="mp_secondzeta",
    category="zeta",
    description="Secondary zeta function Z(s)",
    args=[
        {"name": "s", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_secondzeta(s: str, dps: int = 50) -> dict:
    """Compute the secondary zeta function to arbitrary precision.

    Z(s) related to the functional equation of the Riemann zeta function.
    """
    from mpmath import mp, secondzeta

    mp.dps = dps
    r = secondzeta(mp.mpf(s))
    return {"result": str(r), "input": s, "dps": dps, "latex": rf"Z({s}) = {r}"}


# =============================================================================
# HYPERGEOMETRIC FUNCTIONS (11 functions)
# =============================================================================


@math_command(
    name="mp_hyp0f1",
    category="hypergeometric",
    description="Confluent hypergeometric limit function 0F1(; b; z)",
    args=[
        {"name": "b", "help": "Parameter b"},
        {"name": "z", "help": "Argument z"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_hyp0f1(b: str, z: str, dps: int = 50) -> dict:
    """Compute 0F1(; b; z) to arbitrary precision."""
    from mpmath import hyp0f1, mp

    mp.dps = dps
    r = hyp0f1(mp.mpf(b), mp.mpf(z))
    return {
        "result": str(r),
        "b": b,
        "z": z,
        "dps": dps,
        "latex": rf"{{}}_{0}F_{{1}}(; {b}; {z}) = {r}",
    }


@math_command(
    name="mp_hyp1f1",
    category="hypergeometric",
    description="Confluent hypergeometric function 1F1(a; b; z) (Kummer's M)",
    args=[
        {"name": "a", "help": "Parameter a"},
        {"name": "b", "help": "Parameter b"},
        {"name": "z", "help": "Argument z"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_hyp1f1(a: str, b: str, z: str, dps: int = 50) -> dict:
    """Compute 1F1(a; b; z) (Kummer's confluent hypergeometric M) to arbitrary precision."""
    from mpmath import hyp1f1, mp

    mp.dps = dps
    r = hyp1f1(mp.mpf(a), mp.mpf(b), mp.mpf(z))
    return {
        "result": str(r),
        "a": a,
        "b": b,
        "z": z,
        "dps": dps,
        "latex": rf"{{}}_{1}F_{{1}}({a}; {b}; {z}) = {r}",
    }


@math_command(
    name="mp_hyp1f2",
    category="hypergeometric",
    description="Hypergeometric function 1F2(a; b1, b2; z)",
    args=[
        {"name": "a", "help": "Parameter a"},
        {"name": "b1", "help": "Parameter b1"},
        {"name": "b2", "help": "Parameter b2"},
        {"name": "z", "help": "Argument z"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_hyp1f2(a: str, b1: str, b2: str, z: str, dps: int = 50) -> dict:
    """Compute 1F2(a; b1, b2; z) to arbitrary precision."""
    from mpmath import hyp1f2, mp

    mp.dps = dps
    r = hyp1f2(mp.mpf(a), mp.mpf(b1), mp.mpf(b2), mp.mpf(z))
    return {"result": str(r), "a": a, "b1": b1, "b2": b2, "z": z, "dps": dps}


@math_command(
    name="mp_hyp2f0",
    category="hypergeometric",
    description="Hypergeometric function 2F0(a1, a2; ; z)",
    args=[
        {"name": "a1", "help": "Parameter a1"},
        {"name": "a2", "help": "Parameter a2"},
        {"name": "z", "help": "Argument z"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_hyp2f0(a1: str, a2: str, z: str, dps: int = 50) -> dict:
    """Compute 2F0(a1, a2; ; z) to arbitrary precision."""
    from mpmath import hyp2f0, mp

    mp.dps = dps
    r = hyp2f0(mp.mpf(a1), mp.mpf(a2), mp.mpf(z))
    return {"result": str(r), "a1": a1, "a2": a2, "z": z, "dps": dps}


@math_command(
    name="mp_hyp2f1",
    category="hypergeometric",
    description="Gauss hypergeometric function 2F1(a, b; c; z)",
    args=[
        {"name": "a", "help": "Parameter a"},
        {"name": "b", "help": "Parameter b"},
        {"name": "c", "help": "Parameter c"},
        {"name": "z", "help": "Argument z"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_hyp2f1(a: str, b: str, c: str, z: str, dps: int = 50) -> dict:
    """Compute 2F1(a, b; c; z) (Gauss hypergeometric) to arbitrary precision."""
    from mpmath import hyp2f1, mp

    mp.dps = dps
    r = hyp2f1(mp.mpf(a), mp.mpf(b), mp.mpf(c), mp.mpf(z))
    return {
        "result": str(r),
        "a": a,
        "b": b,
        "c": c,
        "z": z,
        "dps": dps,
        "latex": rf"{{}}_{2}F_{{1}}({a}, {b}; {c}; {z}) = {r}",
    }


@math_command(
    name="mp_hyp2f2",
    category="hypergeometric",
    description="Hypergeometric function 2F2(a1, a2; b1, b2; z)",
    args=[
        {"name": "a1", "help": "Parameter a1"},
        {"name": "a2", "help": "Parameter a2"},
        {"name": "b1", "help": "Parameter b1"},
        {"name": "b2", "help": "Parameter b2"},
        {"name": "z", "help": "Argument z"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_hyp2f2(a1: str, a2: str, b1: str, b2: str, z: str, dps: int = 50) -> dict:
    """Compute 2F2(a1, a2; b1, b2; z) to arbitrary precision."""
    from mpmath import hyp2f2, mp

    mp.dps = dps
    r = hyp2f2(mp.mpf(a1), mp.mpf(a2), mp.mpf(b1), mp.mpf(b2), mp.mpf(z))
    return {"result": str(r), "a1": a1, "a2": a2, "b1": b1, "b2": b2, "z": z, "dps": dps}


@math_command(
    name="mp_hyp3f2",
    category="hypergeometric",
    description="Hypergeometric function 3F2(a1, a2, a3; b1, b2; z)",
    args=[
        {"name": "a1", "help": "Parameter a1"},
        {"name": "a2", "help": "Parameter a2"},
        {"name": "a3", "help": "Parameter a3"},
        {"name": "b1", "help": "Parameter b1"},
        {"name": "b2", "help": "Parameter b2"},
        {"name": "z", "help": "Argument z"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_hyp3f2(a1: str, a2: str, a3: str, b1: str, b2: str, z: str, dps: int = 50) -> dict:
    """Compute 3F2(a1, a2, a3; b1, b2; z) to arbitrary precision."""
    from mpmath import hyp3f2, mp

    mp.dps = dps
    r = hyp3f2(mp.mpf(a1), mp.mpf(a2), mp.mpf(a3), mp.mpf(b1), mp.mpf(b2), mp.mpf(z))
    return {"result": str(r), "a1": a1, "a2": a2, "a3": a3, "b1": b1, "b2": b2, "z": z, "dps": dps}


@math_command(
    name="mp_hyperu",
    category="hypergeometric",
    description="Confluent hypergeometric U(a, b, z) (Tricomi's function)",
    args=[
        {"name": "a", "help": "Parameter a"},
        {"name": "b", "help": "Parameter b"},
        {"name": "z", "help": "Argument z"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_hyperu(a: str, b: str, z: str, dps: int = 50) -> dict:
    """Compute U(a, b, z) (Tricomi's confluent hypergeometric) to arbitrary precision."""
    from mpmath import hyperu, mp

    mp.dps = dps
    r = hyperu(mp.mpf(a), mp.mpf(b), mp.mpf(z))
    return {
        "result": str(r),
        "a": a,
        "b": b,
        "z": z,
        "dps": dps,
        "latex": rf"U({a}, {b}, {z}) = {r}",
    }


@math_command(
    name="mp_hyper",
    category="hypergeometric",
    description="Generalized hypergeometric function pFq",
    args=[
        {"name": "a_params", "help": "Numerator parameters (comma-separated)"},
        {"name": "b_params", "help": "Denominator parameters (comma-separated)"},
        {"name": "z", "help": "Argument z"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_hyper(a_params: str, b_params: str, z: str, dps: int = 50) -> dict:
    """Compute generalized hypergeometric pFq to arbitrary precision.

    a_params and b_params are comma-separated lists of parameters.
    """
    from mpmath import hyper, mp

    mp.dps = dps
    a_list = [mp.mpf(x.strip()) for x in a_params.split(",") if x.strip()]
    b_list = [mp.mpf(x.strip()) for x in b_params.split(",") if x.strip()]
    r = hyper(a_list, b_list, mp.mpf(z))
    return {"result": str(r), "a": a_params, "b": b_params, "z": z, "dps": dps}


@math_command(
    name="mp_meijerg",
    category="hypergeometric",
    description="Meijer G-function",
    args=[
        {"name": "a1", "help": "Parameters a1 (comma-separated)"},
        {"name": "a2", "help": "Parameters a2 (comma-separated)"},
        {"name": "b1", "help": "Parameters b1 (comma-separated)"},
        {"name": "b2", "help": "Parameters b2 (comma-separated)"},
        {"name": "z", "help": "Argument z"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_meijerg(a1: str, a2: str, b1: str, b2: str, z: str, dps: int = 50) -> dict:
    """Compute the Meijer G-function to arbitrary precision.

    G^{m,n}_{p,q}(z | a1; a2 / b1; b2)
    """
    from mpmath import meijerg, mp

    mp.dps = dps

    def parse_list(s):
        return [mp.mpf(x.strip()) for x in s.split(",") if x.strip()] if s.strip() else []

    a1_list = parse_list(a1)
    a2_list = parse_list(a2)
    b1_list = parse_list(b1)
    b2_list = parse_list(b2)
    r = meijerg([a1_list, a2_list], [b1_list, b2_list], mp.mpf(z))
    return {"result": str(r), "a1": a1, "a2": a2, "b1": b1, "b2": b2, "z": z, "dps": dps}


@math_command(
    name="mp_appellf1",
    category="hypergeometric",
    description="Appell hypergeometric function F1(a, b1, b2, c, x, y)",
    args=[
        {"name": "a", "help": "Parameter a"},
        {"name": "b1", "help": "Parameter b1"},
        {"name": "b2", "help": "Parameter b2"},
        {"name": "c", "help": "Parameter c"},
        {"name": "x", "help": "Argument x"},
        {"name": "y", "help": "Argument y"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_appellf1(a: str, b1: str, b2: str, c: str, x: str, y: str, dps: int = 50) -> dict:
    """Compute Appell's hypergeometric F1 to arbitrary precision.

    F1(a, b1, b2, c, x, y) - two-variable hypergeometric function.
    """
    from mpmath import appellf1, mp

    mp.dps = dps
    r = appellf1(mp.mpf(a), mp.mpf(b1), mp.mpf(b2), mp.mpf(c), mp.mpf(x), mp.mpf(y))
    return {"result": str(r), "a": a, "b1": b1, "b2": b2, "c": c, "x": x, "y": y, "dps": dps}


# =============================================================================
# BESSEL FUNCTIONS (17 functions)
# =============================================================================


@math_command(
    name="mp_besselj",
    category="bessel",
    description="Bessel function of the first kind J_n(x)",
    args=[
        {"name": "n", "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_besselj(n: str, x: str, dps: int = 50) -> dict:
    """Compute Bessel function of the first kind to arbitrary precision."""
    from mpmath import besselj, mp

    mp.dps = dps
    r = besselj(mp.mpf(n), mp.mpf(x))
    return {"result": str(r), "n": n, "x": x, "dps": dps, "latex": rf"J_{{{n}}}({x}) = {r}"}


@math_command(
    name="mp_bessely",
    category="bessel",
    description="Bessel function of the second kind Y_n(x)",
    args=[
        {"name": "n", "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_bessely(n: str, x: str, dps: int = 50) -> dict:
    """Compute Bessel function of the second kind to arbitrary precision."""
    from mpmath import bessely, mp

    mp.dps = dps
    r = bessely(mp.mpf(n), mp.mpf(x))
    return {"result": str(r), "n": n, "x": x, "dps": dps, "latex": rf"Y_{{{n}}}({x}) = {r}"}


@math_command(
    name="mp_besseli",
    category="bessel",
    description="Modified Bessel function of the first kind I_n(x)",
    args=[
        {"name": "n", "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_besseli(n: str, x: str, dps: int = 50) -> dict:
    """Compute modified Bessel function of the first kind to arbitrary precision."""
    from mpmath import besseli, mp

    mp.dps = dps
    r = besseli(mp.mpf(n), mp.mpf(x))
    return {"result": str(r), "n": n, "x": x, "dps": dps, "latex": rf"I_{{{n}}}({x}) = {r}"}


@math_command(
    name="mp_besselk",
    category="bessel",
    description="Modified Bessel function of the second kind K_n(x)",
    args=[
        {"name": "n", "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_besselk(n: str, x: str, dps: int = 50) -> dict:
    """Compute modified Bessel function of the second kind to arbitrary precision."""
    from mpmath import besselk, mp

    mp.dps = dps
    r = besselk(mp.mpf(n), mp.mpf(x))
    return {"result": str(r), "n": n, "x": x, "dps": dps, "latex": rf"K_{{{n}}}({x}) = {r}"}


@math_command(
    name="mp_hankel1",
    category="bessel",
    description="Hankel function of the first kind H^(1)_n(x)",
    args=[
        {"name": "n", "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_hankel1(n: str, x: str, dps: int = 50) -> dict:
    """Compute Hankel function of the first kind to arbitrary precision.

    H^(1)_n(x) = J_n(x) + i*Y_n(x)
    """
    from mpmath import hankel1, mp

    mp.dps = dps
    r = hankel1(mp.mpf(n), mp.mpf(x))
    return {"result": str(r), "n": n, "x": x, "dps": dps, "latex": rf"H^{{(1)}}_{{{n}}}({x}) = {r}"}


@math_command(
    name="mp_hankel2",
    category="bessel",
    description="Hankel function of the second kind H^(2)_n(x)",
    args=[
        {"name": "n", "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_hankel2(n: str, x: str, dps: int = 50) -> dict:
    """Compute Hankel function of the second kind to arbitrary precision.

    H^(2)_n(x) = J_n(x) - i*Y_n(x)
    """
    from mpmath import hankel2, mp

    mp.dps = dps
    r = hankel2(mp.mpf(n), mp.mpf(x))
    return {"result": str(r), "n": n, "x": x, "dps": dps, "latex": rf"H^{{(2)}}_{{{n}}}({x}) = {r}"}


@math_command(
    name="mp_airyai",
    category="bessel",
    description="Airy function Ai(x)",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_airyai(x: str, dps: int = 50) -> dict:
    """Compute Airy function Ai to arbitrary precision."""
    from mpmath import airyai, mp

    mp.dps = dps
    r = airyai(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\text{{Ai}}({x}) = {r}"}


@math_command(
    name="mp_airybi",
    category="bessel",
    description="Airy function Bi(x)",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_airybi(x: str, dps: int = 50) -> dict:
    """Compute Airy function Bi to arbitrary precision."""
    from mpmath import airybi, mp

    mp.dps = dps
    r = airybi(mp.mpf(x))
    return {"result": str(r), "input": x, "dps": dps, "latex": rf"\text{{Bi}}({x}) = {r}"}


@math_command(
    name="mp_airyaizero",
    category="bessel",
    description="n-th zero of Airy function Ai",
    args=[
        {"name": "n", "type": int, "help": "Index (1-based)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_airyaizero(n: int, dps: int = 50) -> dict:
    """Compute n-th zero of Airy Ai function to arbitrary precision."""
    from mpmath import airyaizero, mp

    mp.dps = dps
    r = airyaizero(n)
    return {"result": str(r), "n": n, "dps": dps, "latex": rf"a_{{{n}}} = {r}"}


@math_command(
    name="mp_airybizero",
    category="bessel",
    description="n-th zero of Airy function Bi",
    args=[
        {"name": "n", "type": int, "help": "Index (1-based)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_airybizero(n: int, dps: int = 50) -> dict:
    """Compute n-th zero of Airy Bi function to arbitrary precision."""
    from mpmath import airybizero, mp

    mp.dps = dps
    r = airybizero(n)
    return {"result": str(r), "n": n, "dps": dps, "latex": rf"b_{{{n}}} = {r}"}


@math_command(
    name="mp_struveh",
    category="bessel",
    description="Struve function H_n(x)",
    args=[
        {"name": "n", "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_struveh(n: str, x: str, dps: int = 50) -> dict:
    """Compute Struve function H to arbitrary precision."""
    from mpmath import mp, struveh

    mp.dps = dps
    r = struveh(mp.mpf(n), mp.mpf(x))
    return {
        "result": str(r),
        "n": n,
        "x": x,
        "dps": dps,
        "latex": rf"\mathbf{{H}}_{{{n}}}({x}) = {r}",
    }


@math_command(
    name="mp_struvel",
    category="bessel",
    description="Modified Struve function L_n(x)",
    args=[
        {"name": "n", "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_struvel(n: str, x: str, dps: int = 50) -> dict:
    """Compute modified Struve function L to arbitrary precision."""
    from mpmath import mp, struvel

    mp.dps = dps
    r = struvel(mp.mpf(n), mp.mpf(x))
    return {
        "result": str(r),
        "n": n,
        "x": x,
        "dps": dps,
        "latex": rf"\mathbf{{L}}_{{{n}}}({x}) = {r}",
    }


@math_command(
    name="mp_kelvin",
    category="bessel",
    description="Kelvin functions (ber, bei, ker, kei)",
    args=[
        {"name": "n", "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_kelvin(n: str, x: str, dps: int = 50) -> dict:
    """Compute all four Kelvin functions to arbitrary precision.

    Returns ber_n(x), bei_n(x), ker_n(x), kei_n(x).
    """
    from mpmath import bei, ber, kei, ker, mp

    mp.dps = dps
    n_val = mp.mpf(n)
    x_val = mp.mpf(x)
    return {
        "ber": str(ber(n_val, x_val)),
        "bei": str(bei(n_val, x_val)),
        "ker": str(ker(n_val, x_val)),
        "kei": str(kei(n_val, x_val)),
        "n": n,
        "x": x,
        "dps": dps,
    }


@math_command(
    name="mp_ber",
    category="bessel",
    description="Kelvin function ber_n(x)",
    args=[
        {"name": "n", "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_ber(n: str, x: str, dps: int = 50) -> dict:
    """Compute Kelvin ber function to arbitrary precision.

    ber_n(x) = Re(J_n(x * e^(3*pi*i/4)))
    """
    from mpmath import ber, mp

    mp.dps = dps
    r = ber(mp.mpf(n), mp.mpf(x))
    return {
        "result": str(r),
        "n": n,
        "x": x,
        "dps": dps,
        "latex": rf"\text{{ber}}_{{{n}}}({x}) = {r}",
    }


@math_command(
    name="mp_bei",
    category="bessel",
    description="Kelvin function bei_n(x)",
    args=[
        {"name": "n", "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_bei(n: str, x: str, dps: int = 50) -> dict:
    """Compute Kelvin bei function to arbitrary precision.

    bei_n(x) = Im(J_n(x * e^(3*pi*i/4)))
    """
    from mpmath import bei, mp

    mp.dps = dps
    r = bei(mp.mpf(n), mp.mpf(x))
    return {
        "result": str(r),
        "n": n,
        "x": x,
        "dps": dps,
        "latex": rf"\text{{bei}}_{{{n}}}({x}) = {r}",
    }


@math_command(
    name="mp_ker",
    category="bessel",
    description="Kelvin function ker_n(x)",
    args=[
        {"name": "n", "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_ker(n: str, x: str, dps: int = 50) -> dict:
    """Compute Kelvin ker function to arbitrary precision.

    ker_n(x) = Re(K_n(x * e^(pi*i/4)))
    """
    from mpmath import ker, mp

    mp.dps = dps
    r = ker(mp.mpf(n), mp.mpf(x))
    return {
        "result": str(r),
        "n": n,
        "x": x,
        "dps": dps,
        "latex": rf"\text{{ker}}_{{{n}}}({x}) = {r}",
    }


@math_command(
    name="mp_kei",
    category="bessel",
    description="Kelvin function kei_n(x)",
    args=[
        {"name": "n", "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_kei(n: str, x: str, dps: int = 50) -> dict:
    """Compute Kelvin kei function to arbitrary precision.

    kei_n(x) = Im(K_n(x * e^(pi*i/4)))
    """
    from mpmath import kei, mp

    mp.dps = dps
    r = kei(mp.mpf(n), mp.mpf(x))
    return {
        "result": str(r),
        "n": n,
        "x": x,
        "dps": dps,
        "latex": rf"\text{{kei}}_{{{n}}}({x}) = {r}",
    }


# =============================================================================
# ORTHOGONAL POLYNOMIALS (10 functions)
# =============================================================================


@math_command(
    name="mp_legendre",
    category="ortho_poly",
    description="Legendre polynomial P_n(x)",
    args=[
        {"name": "n", "type": int, "help": "Degree"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_legendre(n: int, x: str, dps: int = 50) -> dict:
    """Compute Legendre polynomial P_n(x) to arbitrary precision."""
    from mpmath import legendre, mp

    mp.dps = dps
    r = legendre(n, mp.mpf(x))
    return {"result": str(r), "n": n, "x": x, "dps": dps, "latex": rf"P_{{{n}}}({x}) = {r}"}


@math_command(
    name="mp_legenp",
    category="ortho_poly",
    description="Associated Legendre function P_n^m(x)",
    args=[
        {"name": "n", "type": int, "help": "Degree"},
        {"name": "m", "type": int, "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_legenp(n: int, m: int, x: str, dps: int = 50) -> dict:
    """Compute associated Legendre function of the first kind P_n^m(x)."""
    from mpmath import legenp, mp

    mp.dps = dps
    r = legenp(n, m, mp.mpf(x))
    return {
        "result": str(r),
        "n": n,
        "m": m,
        "x": x,
        "dps": dps,
        "latex": rf"P_{{{n}}}^{{{m}}}({x}) = {r}",
    }


@math_command(
    name="mp_legenq",
    category="ortho_poly",
    description="Associated Legendre function Q_n^m(x)",
    args=[
        {"name": "n", "type": int, "help": "Degree"},
        {"name": "m", "type": int, "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_legenq(n: int, m: int, x: str, dps: int = 50) -> dict:
    """Compute associated Legendre function of the second kind Q_n^m(x)."""
    from mpmath import legenq, mp

    mp.dps = dps
    r = legenq(n, m, mp.mpf(x))
    return {
        "result": str(r),
        "n": n,
        "m": m,
        "x": x,
        "dps": dps,
        "latex": rf"Q_{{{n}}}^{{{m}}}({x}) = {r}",
    }


@math_command(
    name="mp_chebyt",
    category="ortho_poly",
    description="Chebyshev polynomial of the first kind T_n(x)",
    args=[
        {"name": "n", "type": int, "help": "Degree"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_chebyt(n: int, x: str, dps: int = 50) -> dict:
    """Compute Chebyshev polynomial of the first kind T_n(x)."""
    from mpmath import chebyt, mp

    mp.dps = dps
    r = chebyt(n, mp.mpf(x))
    return {"result": str(r), "n": n, "x": x, "dps": dps, "latex": rf"T_{{{n}}}({x}) = {r}"}


@math_command(
    name="mp_chebyu",
    category="ortho_poly",
    description="Chebyshev polynomial of the second kind U_n(x)",
    args=[
        {"name": "n", "type": int, "help": "Degree"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_chebyu(n: int, x: str, dps: int = 50) -> dict:
    """Compute Chebyshev polynomial of the second kind U_n(x)."""
    from mpmath import chebyu, mp

    mp.dps = dps
    r = chebyu(n, mp.mpf(x))
    return {"result": str(r), "n": n, "x": x, "dps": dps, "latex": rf"U_{{{n}}}({x}) = {r}"}


@math_command(
    name="mp_hermite",
    category="ortho_poly",
    description="Hermite polynomial H_n(x)",
    args=[
        {"name": "n", "type": int, "help": "Degree"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_hermite(n: int, x: str, dps: int = 50) -> dict:
    """Compute Hermite polynomial H_n(x) (physicist's convention)."""
    from mpmath import hermite, mp

    mp.dps = dps
    r = hermite(n, mp.mpf(x))
    return {"result": str(r), "n": n, "x": x, "dps": dps, "latex": rf"H_{{{n}}}({x}) = {r}"}


@math_command(
    name="mp_gegenbauer",
    category="ortho_poly",
    description="Gegenbauer (ultraspherical) polynomial C_n^a(x)",
    args=[
        {"name": "n", "type": int, "help": "Degree"},
        {"name": "a", "help": "Parameter alpha"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_gegenbauer(n: int, a: str, x: str, dps: int = 50) -> dict:
    """Compute Gegenbauer polynomial C_n^a(x)."""
    from mpmath import gegenbauer, mp

    mp.dps = dps
    r = gegenbauer(n, mp.mpf(a), mp.mpf(x))
    return {
        "result": str(r),
        "n": n,
        "a": a,
        "x": x,
        "dps": dps,
        "latex": rf"C_{{{n}}}^{{{a}}}({x}) = {r}",
    }


@math_command(
    name="mp_laguerre",
    category="ortho_poly",
    description="Generalized Laguerre polynomial L_n^a(x)",
    args=[
        {"name": "n", "type": int, "help": "Degree"},
        {"name": "a", "help": "Parameter alpha (0 for standard Laguerre)"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_laguerre(n: int, a: str, x: str, dps: int = 50) -> dict:
    """Compute generalized Laguerre polynomial L_n^a(x)."""
    from mpmath import laguerre, mp

    mp.dps = dps
    r = laguerre(n, mp.mpf(a), mp.mpf(x))
    return {
        "result": str(r),
        "n": n,
        "a": a,
        "x": x,
        "dps": dps,
        "latex": rf"L_{{{n}}}^{{{a}}}({x}) = {r}",
    }


@math_command(
    name="mp_jacobi",
    category="ortho_poly",
    description="Jacobi polynomial P_n^(a,b)(x)",
    args=[
        {"name": "n", "type": int, "help": "Degree"},
        {"name": "a", "help": "Parameter alpha"},
        {"name": "b", "help": "Parameter beta"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_jacobi(n: int, a: str, b: str, x: str, dps: int = 50) -> dict:
    """Compute Jacobi polynomial P_n^(a,b)(x)."""
    from mpmath import jacobi, mp

    mp.dps = dps
    r = jacobi(n, mp.mpf(a), mp.mpf(b), mp.mpf(x))
    return {
        "result": str(r),
        "n": n,
        "a": a,
        "b": b,
        "x": x,
        "dps": dps,
        "latex": rf"P_{{{n}}}^{{({a},{b})}}({x}) = {r}",
    }


@math_command(
    name="mp_spherharm",
    category="ortho_poly",
    description="Spherical harmonic Y_l^m(theta, phi)",
    args=[
        {"name": "l", "type": int, "help": "Degree"},
        {"name": "m", "type": int, "help": "Order"},
        {"name": "theta", "help": "Polar angle (radians)"},
        {"name": "phi", "help": "Azimuthal angle (radians)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_spherharm(l: int, m: int, theta: str, phi: str, dps: int = 50) -> dict:
    """Compute spherical harmonic Y_l^m(theta, phi)."""
    from mpmath import mp, spherharm

    mp.dps = dps
    r = spherharm(l, m, mp.mpf(theta), mp.mpf(phi))
    return {
        "result": str(r),
        "l": l,
        "m": m,
        "theta": theta,
        "phi": phi,
        "dps": dps,
        "latex": rf"Y_{{{l}}}^{{{m}}}({theta}, {phi}) = {r}",
    }


# =============================================================================
# ELLIPTIC FUNCTIONS (14 functions)
# =============================================================================


@math_command(
    name="mp_ellipk",
    category="elliptic",
    description="Complete elliptic integral of the first kind K(m)",
    args=[
        {"name": "m", "help": "Parameter (m = k^2 where k is the modulus)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_ellipk(m: str, dps: int = 50) -> dict:
    """Compute complete elliptic integral of the first kind K(m)."""
    from mpmath import ellipk, mp

    mp.dps = dps
    r = ellipk(mp.mpf(m))
    return {"result": str(r), "m": m, "dps": dps, "latex": rf"K({m}) = {r}"}


@math_command(
    name="mp_ellipe",
    category="elliptic",
    description="Complete elliptic integral of the second kind E(m)",
    args=[
        {"name": "m", "help": "Parameter (m = k^2 where k is the modulus)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_ellipe(m: str, dps: int = 50) -> dict:
    """Compute complete elliptic integral of the second kind E(m)."""
    from mpmath import ellipe, mp

    mp.dps = dps
    r = ellipe(mp.mpf(m))
    return {"result": str(r), "m": m, "dps": dps, "latex": rf"E({m}) = {r}"}


@math_command(
    name="mp_ellipf",
    category="elliptic",
    description="Incomplete elliptic integral of the first kind F(phi, m)",
    args=[
        {"name": "phi", "help": "Amplitude (radians)"},
        {"name": "m", "help": "Parameter"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_ellipf(phi: str, m: str, dps: int = 50) -> dict:
    """Compute incomplete elliptic integral of the first kind F(phi, m)."""
    from mpmath import ellipf, mp

    mp.dps = dps
    r = ellipf(mp.mpf(phi), mp.mpf(m))
    return {"result": str(r), "phi": phi, "m": m, "dps": dps, "latex": rf"F({phi}, {m}) = {r}"}


@math_command(
    name="mp_ellippi",
    category="elliptic",
    description="Complete elliptic integral of the third kind Pi(n, m)",
    args=[
        {"name": "n", "help": "Characteristic"},
        {"name": "m", "help": "Parameter"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_ellippi(n: str, m: str, dps: int = 50) -> dict:
    """Compute complete elliptic integral of the third kind Pi(n, m)."""
    from mpmath import ellippi, mp

    mp.dps = dps
    r = ellippi(mp.mpf(n), mp.mpf(m))
    return {"result": str(r), "n": n, "m": m, "dps": dps, "latex": rf"\Pi({n}, {m}) = {r}"}


@math_command(
    name="mp_elliprj",
    category="elliptic",
    description="Carlson symmetric elliptic integral R_J(x, y, z, p)",
    args=[
        {"name": "x", "help": "First argument"},
        {"name": "y", "help": "Second argument"},
        {"name": "z", "help": "Third argument"},
        {"name": "p", "help": "Fourth argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_elliprj(x: str, y: str, z: str, p: str, dps: int = 50) -> dict:
    """Compute Carlson symmetric elliptic integral R_J(x, y, z, p)."""
    from mpmath import elliprj, mp

    mp.dps = dps
    r = elliprj(mp.mpf(x), mp.mpf(y), mp.mpf(z), mp.mpf(p))
    return {
        "result": str(r),
        "x": x,
        "y": y,
        "z": z,
        "p": p,
        "dps": dps,
        "latex": rf"R_J({x}, {y}, {z}, {p}) = {r}",
    }


@math_command(
    name="mp_elliprf",
    category="elliptic",
    description="Carlson symmetric elliptic integral R_F(x, y, z)",
    args=[
        {"name": "x", "help": "First argument"},
        {"name": "y", "help": "Second argument"},
        {"name": "z", "help": "Third argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_elliprf(x: str, y: str, z: str, dps: int = 50) -> dict:
    """Compute Carlson symmetric elliptic integral R_F(x, y, z)."""
    from mpmath import elliprf, mp

    mp.dps = dps
    r = elliprf(mp.mpf(x), mp.mpf(y), mp.mpf(z))
    return {
        "result": str(r),
        "x": x,
        "y": y,
        "z": z,
        "dps": dps,
        "latex": rf"R_F({x}, {y}, {z}) = {r}",
    }


@math_command(
    name="mp_elliprc",
    category="elliptic",
    description="Carlson degenerate elliptic integral R_C(x, y)",
    args=[
        {"name": "x", "help": "First argument"},
        {"name": "y", "help": "Second argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_elliprc(x: str, y: str, dps: int = 50) -> dict:
    """Compute Carlson degenerate elliptic integral R_C(x, y)."""
    from mpmath import elliprc, mp

    mp.dps = dps
    r = elliprc(mp.mpf(x), mp.mpf(y))
    return {"result": str(r), "x": x, "y": y, "dps": dps, "latex": rf"R_C({x}, {y}) = {r}"}


@math_command(
    name="mp_elliprd",
    category="elliptic",
    description="Carlson symmetric elliptic integral R_D(x, y, z)",
    args=[
        {"name": "x", "help": "First argument"},
        {"name": "y", "help": "Second argument"},
        {"name": "z", "help": "Third argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_elliprd(x: str, y: str, z: str, dps: int = 50) -> dict:
    """Compute Carlson symmetric elliptic integral R_D(x, y, z)."""
    from mpmath import elliprd, mp

    mp.dps = dps
    r = elliprd(mp.mpf(x), mp.mpf(y), mp.mpf(z))
    return {
        "result": str(r),
        "x": x,
        "y": y,
        "z": z,
        "dps": dps,
        "latex": rf"R_D({x}, {y}, {z}) = {r}",
    }


@math_command(
    name="mp_elliprg",
    category="elliptic",
    description="Carlson symmetric elliptic integral R_G(x, y, z)",
    args=[
        {"name": "x", "help": "First argument"},
        {"name": "y", "help": "Second argument"},
        {"name": "z", "help": "Third argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_elliprg(x: str, y: str, z: str, dps: int = 50) -> dict:
    """Compute Carlson symmetric elliptic integral R_G(x, y, z)."""
    from mpmath import elliprg, mp

    mp.dps = dps
    r = elliprg(mp.mpf(x), mp.mpf(y), mp.mpf(z))
    return {
        "result": str(r),
        "x": x,
        "y": y,
        "z": z,
        "dps": dps,
        "latex": rf"R_G({x}, {y}, {z}) = {r}",
    }


@math_command(
    name="mp_agm",
    category="elliptic",
    description="Arithmetic-geometric mean AGM(a, b)",
    args=[
        {"name": "a", "help": "First argument"},
        {"name": "b", "help": "Second argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_agm(a: str, b: str, dps: int = 50) -> dict:
    """Compute the arithmetic-geometric mean AGM(a, b)."""
    from mpmath import agm, mp

    mp.dps = dps
    r = agm(mp.mpf(a), mp.mpf(b))
    return {"result": str(r), "a": a, "b": b, "dps": dps, "latex": rf"\text{{AGM}}({a}, {b}) = {r}"}


@math_command(
    name="mp_jtheta",
    category="elliptic",
    description="Jacobi theta function theta_n(z, q)",
    args=[
        {"name": "n", "type": int, "help": "Index (1, 2, 3, or 4)"},
        {"name": "z", "help": "Argument"},
        {"name": "q", "help": "Nome (|q| < 1)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_jtheta(n: int, z: str, q: str, dps: int = 50) -> dict:
    """Compute Jacobi theta function theta_n(z, q)."""
    from mpmath import jtheta, mp

    mp.dps = dps
    r = jtheta(n, mp.mpf(z), mp.mpf(q))
    return {
        "result": str(r),
        "n": n,
        "z": z,
        "q": q,
        "dps": dps,
        "latex": rf"\theta_{{{n}}}({z}, {q}) = {r}",
    }


@math_command(
    name="mp_qfrom",
    category="elliptic",
    description="Compute nome q from elliptic parameters",
    args=[
        {"name": "--m", "help": "Parameter m"},
        {"name": "--k", "help": "Modulus k"},
        {"name": "--tau", "help": "Half-period ratio tau"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_qfrom(m: str = None, k: str = None, tau: str = None, dps: int = 50) -> dict:
    """Compute nome q from elliptic parameters (m, k, or tau)."""
    from mpmath import mp, qfrom

    mp.dps = dps
    kwargs = {}
    if m is not None:
        kwargs["m"] = mp.mpf(m)
    if k is not None:
        kwargs["k"] = mp.mpf(k)
    if tau is not None:
        kwargs["tau"] = mp.mpc(tau)
    if not kwargs:
        return {"error": "Must provide one of: --m, --k, or --tau"}
    r = qfrom(**kwargs)
    return {"result": str(r), "params": {k: str(v) for k, v in kwargs.items()}, "dps": dps}


@math_command(
    name="mp_mfrom",
    category="elliptic",
    description="Compute parameter m from elliptic parameters",
    args=[
        {"name": "--q", "help": "Nome q"},
        {"name": "--k", "help": "Modulus k"},
        {"name": "--tau", "help": "Half-period ratio tau"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_mfrom(q: str = None, k: str = None, tau: str = None, dps: int = 50) -> dict:
    """Compute parameter m from elliptic parameters (q, k, or tau)."""
    from mpmath import mfrom, mp

    mp.dps = dps
    kwargs = {}
    if q is not None:
        kwargs["q"] = mp.mpf(q)
    if k is not None:
        kwargs["k"] = mp.mpf(k)
    if tau is not None:
        kwargs["tau"] = mp.mpc(tau)
    if not kwargs:
        return {"error": "Must provide one of: --q, --k, or --tau"}
    r = mfrom(**kwargs)
    return {"result": str(r), "params": {k: str(v) for k, v in kwargs.items()}, "dps": dps}


@math_command(
    name="mp_kleinj",
    category="elliptic",
    description="Klein j-invariant j(tau)",
    args=[
        {"name": "tau", "help": "Argument (complex, Im(tau) > 0)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_kleinj(tau: str, dps: int = 50) -> dict:
    """Compute Klein j-invariant j(tau)."""
    from mpmath import kleinj, mp

    mp.dps = dps
    r = kleinj(parse_complex(tau))
    return {"result": str(r), "tau": tau, "dps": dps, "latex": rf"j({tau}) = {r}"}


# =============================================================================
# ERROR/EXPONENTIAL INTEGRALS (16 functions)
# =============================================================================


@math_command(
    name="mp_erf",
    category="error_exp",
    description="Error function erf(x)",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_erf(x: str, dps: int = 50) -> dict:
    """Compute the error function erf(x)."""
    from mpmath import erf, mp

    mp.dps = dps
    r = erf(mp.mpf(x))
    return {"result": str(r), "x": x, "dps": dps, "latex": rf"\text{{erf}}({x}) = {r}"}


@math_command(
    name="mp_erfc",
    category="error_exp",
    description="Complementary error function erfc(x) = 1 - erf(x)",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_erfc(x: str, dps: int = 50) -> dict:
    """Compute the complementary error function erfc(x) = 1 - erf(x)."""
    from mpmath import erfc, mp

    mp.dps = dps
    r = erfc(mp.mpf(x))
    return {"result": str(r), "x": x, "dps": dps, "latex": rf"\text{{erfc}}({x}) = {r}"}


@math_command(
    name="mp_erfi",
    category="error_exp",
    description="Imaginary error function erfi(x) = -i*erf(ix)",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_erfi(x: str, dps: int = 50) -> dict:
    """Compute the imaginary error function erfi(x)."""
    from mpmath import erfi, mp

    mp.dps = dps
    r = erfi(mp.mpf(x))
    return {"result": str(r), "x": x, "dps": dps, "latex": rf"\text{{erfi}}({x}) = {r}"}


@math_command(
    name="mp_erfinv",
    category="error_exp",
    description="Inverse error function",
    args=[
        {"name": "x", "help": "Argument (-1 < x < 1)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_erfinv(x: str, dps: int = 50) -> dict:
    """Compute the inverse error function."""
    from mpmath import erfinv, mp

    mp.dps = dps
    r = erfinv(mp.mpf(x))
    return {"result": str(r), "x": x, "dps": dps, "latex": rf"\text{{erf}}^{{-1}}({x}) = {r}"}


@math_command(
    name="mp_npdf",
    category="error_exp",
    description="Standard normal probability density function",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--mu", "default": "0", "help": "Mean (default 0)"},
        {"name": "--sigma", "default": "1", "help": "Standard deviation (default 1)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_npdf(x: str, mu: str = "0", sigma: str = "1", dps: int = 50) -> dict:
    """Compute normal probability density function."""
    from mpmath import mp, npdf

    mp.dps = dps
    r = npdf(mp.mpf(x), mp.mpf(mu), mp.mpf(sigma))
    return {"result": str(r), "x": x, "mu": mu, "sigma": sigma, "dps": dps}


@math_command(
    name="mp_ncdf",
    category="error_exp",
    description="Standard normal cumulative distribution function",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--mu", "default": "0", "help": "Mean (default 0)"},
        {"name": "--sigma", "default": "1", "help": "Standard deviation (default 1)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_ncdf(x: str, mu: str = "0", sigma: str = "1", dps: int = 50) -> dict:
    """Compute normal cumulative distribution function."""
    from mpmath import mp, ncdf

    mp.dps = dps
    r = ncdf(mp.mpf(x), mp.mpf(mu), mp.mpf(sigma))
    return {"result": str(r), "x": x, "mu": mu, "sigma": sigma, "dps": dps}


@math_command(
    name="mp_ei",
    category="error_exp",
    description="Exponential integral Ei(x)",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_ei(x: str, dps: int = 50) -> dict:
    """Compute the exponential integral Ei(x)."""
    from mpmath import ei, mp

    mp.dps = dps
    r = ei(mp.mpf(x))
    return {"result": str(r), "x": x, "dps": dps, "latex": rf"\text{{Ei}}({x}) = {r}"}


@math_command(
    name="mp_li",
    category="error_exp",
    description="Logarithmic integral li(x)",
    args=[
        {"name": "x", "help": "Argument (x > 0)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_li(x: str, dps: int = 50) -> dict:
    """Compute the logarithmic integral li(x)."""
    from mpmath import li, mp

    mp.dps = dps
    r = li(mp.mpf(x))
    return {"result": str(r), "x": x, "dps": dps, "latex": rf"\text{{li}}({x}) = {r}"}


@math_command(
    name="mp_ci",
    category="error_exp",
    description="Cosine integral Ci(x)",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_ci(x: str, dps: int = 50) -> dict:
    """Compute the cosine integral Ci(x)."""
    from mpmath import ci, mp

    mp.dps = dps
    r = ci(mp.mpf(x))
    return {"result": str(r), "x": x, "dps": dps, "latex": rf"\text{{Ci}}({x}) = {r}"}


@math_command(
    name="mp_si",
    category="error_exp",
    description="Sine integral Si(x)",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_si(x: str, dps: int = 50) -> dict:
    """Compute the sine integral Si(x)."""
    from mpmath import mp, si

    mp.dps = dps
    r = si(mp.mpf(x))
    return {"result": str(r), "x": x, "dps": dps, "latex": rf"\text{{Si}}({x}) = {r}"}


@math_command(
    name="mp_chi",
    category="error_exp",
    description="Hyperbolic cosine integral Chi(x)",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_chi(x: str, dps: int = 50) -> dict:
    """Compute the hyperbolic cosine integral Chi(x)."""
    from mpmath import chi, mp

    mp.dps = dps
    r = chi(mp.mpf(x))
    return {"result": str(r), "x": x, "dps": dps, "latex": rf"\text{{Chi}}({x}) = {r}"}


@math_command(
    name="mp_shi",
    category="error_exp",
    description="Hyperbolic sine integral Shi(x)",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_shi(x: str, dps: int = 50) -> dict:
    """Compute the hyperbolic sine integral Shi(x)."""
    from mpmath import mp, shi

    mp.dps = dps
    r = shi(mp.mpf(x))
    return {"result": str(r), "x": x, "dps": dps, "latex": rf"\text{{Shi}}({x}) = {r}"}


@math_command(
    name="mp_fresnels",
    category="error_exp",
    description="Fresnel sine integral S(x)",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_fresnels(x: str, dps: int = 50) -> dict:
    """Compute the Fresnel sine integral S(x)."""
    from mpmath import fresnels, mp

    mp.dps = dps
    r = fresnels(mp.mpf(x))
    return {"result": str(r), "x": x, "dps": dps, "latex": rf"S({x}) = {r}"}


@math_command(
    name="mp_fresnelc",
    category="error_exp",
    description="Fresnel cosine integral C(x)",
    args=[
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_fresnelc(x: str, dps: int = 50) -> dict:
    """Compute the Fresnel cosine integral C(x)."""
    from mpmath import fresnelc, mp

    mp.dps = dps
    r = fresnelc(mp.mpf(x))
    return {"result": str(r), "x": x, "dps": dps, "latex": rf"C({x}) = {r}"}


@math_command(
    name="mp_expint",
    category="error_exp",
    description="Generalized exponential integral E_n(x)",
    args=[
        {"name": "n", "type": int, "help": "Order"},
        {"name": "x", "help": "Argument"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_expint(n: int, x: str, dps: int = 50) -> dict:
    """Compute generalized exponential integral E_n(x)."""
    from mpmath import expint, mp

    mp.dps = dps
    r = expint(n, mp.mpf(x))
    return {"result": str(r), "n": n, "x": x, "dps": dps, "latex": rf"E_{{{n}}}({x}) = {r}"}


# =============================================================================
# NUMBER THEORY (17 functions)
# =============================================================================


@math_command(
    name="mp_primepi",
    category="number_theory",
    description="Prime counting function pi(n)",
    args=[{"name": "n", "type": int, "help": "Upper limit"}],
)
def cmd_mp_primepi(n: int) -> dict:
    """Count the number of primes less than or equal to n."""
    from mpmath import primepi

    r = primepi(n)
    return {"result": int(r), "n": n, "latex": rf"\pi({n}) = {r}"}


def _is_prime(n: int) -> bool:
    """Simple primality test for internal use."""
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


@math_command(
    name="mp_prime",
    category="number_theory",
    description="n-th prime number",
    args=[{"name": "n", "type": int, "help": "Index (1-based)"}],
)
def cmd_mp_prime(n: int) -> dict:
    """Compute the n-th prime number (1-indexed)."""
    if n < 1:
        return {"error": "n must be >= 1", "n": n}
    count = 0
    candidate = 2
    while count < n:
        if _is_prime(candidate):
            count += 1
            if count == n:
                return {"result": candidate, "n": n, "latex": rf"p_{{{n}}} = {candidate}"}
        candidate += 1
    return {"error": "Unexpected error", "n": n}


@math_command(
    name="mp_isprime",
    category="number_theory",
    description="Primality test",
    args=[{"name": "n", "type": int, "help": "Integer to test"}],
)
def cmd_mp_isprime(n: int) -> dict:
    """Test if n is prime using trial division."""
    if n < 2:
        return {"result": False, "n": n}
    if n == 2:
        return {"result": True, "n": n}
    if n % 2 == 0:
        return {"result": False, "n": n}
    i = 3
    while i * i <= n:
        if n % i == 0:
            return {"result": False, "n": n}
        i += 2
    return {"result": True, "n": n}


@math_command(
    name="mp_nextprime",
    category="number_theory",
    description="Next prime after n",
    args=[{"name": "n", "type": int, "help": "Starting integer"}],
)
def cmd_mp_nextprime(n: int) -> dict:
    """Find the next prime number greater than n."""
    candidate = n + 1
    while not _is_prime(candidate):
        candidate += 1
    return {"result": candidate, "n": n}


@math_command(
    name="mp_prevprime",
    category="number_theory",
    description="Previous prime before n",
    args=[{"name": "n", "type": int, "help": "Starting integer"}],
)
def cmd_mp_prevprime(n: int) -> dict:
    """Find the previous prime number less than n."""
    if n <= 2:
        return {"error": "No prime less than 2", "n": n}
    candidate = n - 1
    while candidate > 1 and not _is_prime(candidate):
        candidate -= 1
    if candidate < 2:
        return {"error": "No prime less than n", "n": n}
    return {"result": candidate, "n": n}


def _moebius(n: int) -> int:
    """Compute Moebius function: 0 if n has squared factor, (-1)^k otherwise."""
    if n == 1:
        return 1
    num_factors = 0
    temp = n
    # Check for factor of 2
    if temp % 2 == 0:
        num_factors += 1
        temp //= 2
        if temp % 2 == 0:
            return 0  # 4 divides n
    # Check odd factors
    i = 3
    while i * i <= temp:
        if temp % i == 0:
            num_factors += 1
            temp //= i
            if temp % i == 0:
                return 0  # i^2 divides n
        i += 2
    if temp > 1:
        num_factors += 1
    return 1 if num_factors % 2 == 0 else -1


@math_command(
    name="mp_moebius",
    category="number_theory",
    description="Moebius function mu(n)",
    args=[{"name": "n", "type": int, "help": "Positive integer"}],
)
def cmd_mp_moebius(n: int) -> dict:
    """Compute the Moebius function mu(n)."""
    r = _moebius(n)
    return {"result": r, "n": n, "latex": rf"\mu({n}) = {r}"}


@math_command(
    name="mp_bernoulli",
    category="number_theory",
    description="Bernoulli number B_n",
    args=[
        {"name": "n", "type": int, "help": "Index"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_bernoulli(n: int, dps: int = 50) -> dict:
    """Compute the n-th Bernoulli number B_n."""
    from mpmath import bernoulli, mp

    mp.dps = dps
    r = bernoulli(n)
    return {"result": str(r), "n": n, "dps": dps, "latex": rf"B_{{{n}}} = {r}"}


@math_command(
    name="mp_euler_number",
    category="number_theory",
    description="Euler number E_n",
    args=[
        {"name": "n", "type": int, "help": "Index"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_euler_number(n: int, dps: int = 50) -> dict:
    """Compute the n-th Euler number E_n."""
    from mpmath import eulernum, mp

    mp.dps = dps
    r = eulernum(n)
    return {"result": str(r), "n": n, "dps": dps, "latex": rf"E_{{{n}}} = {r}"}


@math_command(
    name="mp_stirling1",
    category="number_theory",
    description="Stirling number of the first kind s(n, k)",
    args=[
        {"name": "n", "type": int, "help": "n parameter"},
        {"name": "k", "type": int, "help": "k parameter"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_stirling1(n: int, k: int, dps: int = 50) -> dict:
    """Compute Stirling number of the first kind s(n, k)."""
    from mpmath import mp, stirling1

    mp.dps = dps
    r = stirling1(n, k)
    return {"result": str(r), "n": n, "k": k, "dps": dps, "latex": rf"s({n}, {k}) = {r}"}


@math_command(
    name="mp_stirling2",
    category="number_theory",
    description="Stirling number of the second kind S(n, k)",
    args=[
        {"name": "n", "type": int, "help": "n parameter"},
        {"name": "k", "type": int, "help": "k parameter"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_stirling2(n: int, k: int, dps: int = 50) -> dict:
    """Compute Stirling number of the second kind S(n, k)."""
    from mpmath import mp, stirling2

    mp.dps = dps
    r = stirling2(n, k)
    return {"result": str(r), "n": n, "k": k, "dps": dps, "latex": rf"S({n}, {k}) = {r}"}


@math_command(
    name="mp_bell",
    category="number_theory",
    description="Bell number B_n",
    args=[
        {"name": "n", "type": int, "help": "Index"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_bell(n: int, dps: int = 50) -> dict:
    """Compute the n-th Bell number B_n."""
    from mpmath import bell, mp

    mp.dps = dps
    r = bell(n)
    return {"result": str(r), "n": n, "dps": dps, "latex": rf"B_{{{n}}} = {r}"}


def _npartitions(n: int) -> int:
    """Compute number of partitions of n using dynamic programming."""
    if n < 0:
        return 0
    if n == 0:
        return 1
    # p[i] will store number of partitions of i
    p = [0] * (n + 1)
    p[0] = 1
    for i in range(1, n + 1):
        for j in range(i, n + 1):
            p[j] += p[j - i]
    return p[n]


@math_command(
    name="mp_npartitions",
    category="number_theory",
    description="Number of partitions of n",
    args=[{"name": "n", "type": int, "help": "Non-negative integer"}],
)
def cmd_mp_npartitions(n: int) -> dict:
    """Compute the number of partitions of n."""
    r = _npartitions(n)
    return {"result": r, "n": n, "latex": rf"p({n}) = {r}"}


@math_command(
    name="mp_fibonacci",
    category="number_theory",
    description="Fibonacci number F_n",
    args=[
        {"name": "n", "type": int, "help": "Index"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_fibonacci(n: int, dps: int = 50) -> dict:
    """Compute the n-th Fibonacci number F_n."""
    from mpmath import fibonacci, mp

    mp.dps = dps
    r = fibonacci(n)
    return {"result": str(r), "n": n, "dps": dps, "latex": rf"F_{{{n}}} = {r}"}


@math_command(
    name="mp_lucas",
    category="number_theory",
    description="Lucas number L_n",
    args=[
        {"name": "n", "type": int, "help": "Index"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_lucas(n: int, dps: int = 50) -> dict:
    """Compute the n-th Lucas number L_n using L_n = F_{n-1} + F_{n+1}."""
    from mpmath import fibonacci, mp

    mp.dps = dps
    # L_n = F_{n-1} + F_{n+1}
    r = fibonacci(n - 1) + fibonacci(n + 1)
    return {"result": str(r), "n": n, "dps": dps, "latex": rf"L_{{{n}}} = {r}"}


@math_command(
    name="mp_gcd",
    category="number_theory",
    description="Greatest common divisor",
    args=[
        {"name": "a", "type": int, "help": "First integer"},
        {"name": "b", "type": int, "help": "Second integer"},
    ],
)
def cmd_mp_gcd(a: int, b: int) -> dict:
    """Compute the greatest common divisor of a and b."""
    from math import gcd

    r = gcd(a, b)
    return {"result": r, "a": a, "b": b, "latex": rf"\gcd({a}, {b}) = {r}"}


@math_command(
    name="mp_lcm",
    category="number_theory",
    description="Least common multiple",
    args=[
        {"name": "a", "type": int, "help": "First integer"},
        {"name": "b", "type": int, "help": "Second integer"},
    ],
)
def cmd_mp_lcm(a: int, b: int) -> dict:
    """Compute the least common multiple of a and b."""
    from math import lcm

    r = lcm(a, b)
    return {"result": r, "a": a, "b": b, "latex": rf"\text{{lcm}}({a}, {b}) = {r}"}


@math_command(
    name="mp_isqrt",
    category="number_theory",
    description="Integer square root",
    args=[{"name": "n", "type": int, "help": "Non-negative integer"}],
)
def cmd_mp_isqrt(n: int) -> dict:
    """Compute the integer square root of n (floor(sqrt(n)))."""
    from math import isqrt

    r = isqrt(n)
    return {"result": r, "n": n, "latex": rf"\lfloor\sqrt{{{n}}}\rfloor = {r}"}


# =============================================================================
# CALCULUS (25 functions)
# =============================================================================


@math_command(
    name="mp_diff",
    category="calculus",
    description="Numerical differentiation",
    args=[
        {"name": "func", "help": "Function expression (e.g. 'x**2')"},
        {"name": "x", "help": "Point to differentiate at"},
        {"name": "--n", "type": int, "default": 1, "help": "Derivative order"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_diff(func: str, x: str, n: int = 1, dps: int = 50) -> dict:
    """Numerical differentiation to arbitrary precision."""
    from mpmath import diff, mp

    mp.dps = dps
    f = parse_callable(func, library="mpmath")
    r = diff(f, mp.mpf(x), n=n)
    return {"result": str(r), "derivative_order": n, "dps": dps}


@math_command(
    name="mp_quad",
    category="calculus",
    description="Numerical integration (adaptive quadrature)",
    args=[
        {"name": "func", "help": "Function expression (e.g. 'x**2')"},
        {"name": "a", "help": "Lower bound"},
        {"name": "b", "help": "Upper bound"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_quad(func: str, a: str, b: str, dps: int = 50) -> dict:
    """Numerical integration using adaptive quadrature."""
    from mpmath import mp, quad

    mp.dps = dps
    f = parse_callable(func, library="mpmath")
    r = quad(f, [parse_bound(a), parse_bound(b)])
    return {"result": str(r), "interval": [a, b], "dps": dps}


@math_command(
    name="mp_quadgl",
    category="calculus",
    description="Gauss-Legendre quadrature",
    args=[
        {"name": "func", "help": "Function expression"},
        {"name": "a", "help": "Lower bound"},
        {"name": "b", "help": "Upper bound"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_quadgl(func: str, a: str, b: str, dps: int = 50) -> dict:
    """Numerical integration using Gauss-Legendre quadrature."""
    from mpmath import mp, quadgl

    mp.dps = dps
    f = parse_callable(func, library="mpmath")
    r = quadgl(f, [parse_bound(a), parse_bound(b)])
    return {"result": str(r), "method": "gauss-legendre", "dps": dps}


@math_command(
    name="mp_quadts",
    category="calculus",
    description="Tanh-sinh quadrature",
    args=[
        {"name": "func", "help": "Function expression"},
        {"name": "a", "help": "Lower bound"},
        {"name": "b", "help": "Upper bound"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_quadts(func: str, a: str, b: str, dps: int = 50) -> dict:
    """Numerical integration using tanh-sinh (double exponential) quadrature."""
    from mpmath import mp, quadts

    mp.dps = dps
    f = parse_callable(func, library="mpmath")
    r = quadts(f, [parse_bound(a), parse_bound(b)])
    return {"result": str(r), "method": "tanh-sinh", "dps": dps}


@math_command(
    name="mp_quadosc",
    category="calculus",
    description="Oscillatory quadrature (for sin/cos integrands)",
    args=[
        {"name": "func", "help": "Function expression"},
        {"name": "a", "help": "Lower bound"},
        {"name": "b", "help": "Upper bound (can be 'inf')"},
        {"name": "--omega", "type": float, "default": 1.0, "help": "Angular frequency"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_quadosc(func: str, a: str, b: str, omega: float = 1.0, dps: int = 50) -> dict:
    """Numerical integration for oscillatory integrands."""
    from mpmath import inf, mp, quadosc

    mp.dps = dps
    f = parse_callable(func, library="mpmath")
    b_val = inf if b.lower() == "inf" else mp.mpf(b)
    r = quadosc(f, [mp.mpf(a), b_val], omega=omega)
    return {"result": str(r), "omega": omega, "dps": dps}


@math_command(
    name="mp_limit",
    category="calculus",
    description="Numerical limit evaluation",
    args=[
        {"name": "func", "help": "Function expression"},
        {"name": "x0", "help": "Point to take limit at (can be 'inf')"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_limit(func: str, x0: str, dps: int = 50) -> dict:
    """Evaluate limit of function as x approaches x0."""
    from mpmath import inf, limit, mp

    mp.dps = dps
    f = parse_callable(func, library="mpmath")
    x0_val = inf if x0.lower() == "inf" else mp.mpf(x0)
    r = limit(f, x0_val)
    return {"result": str(r), "x0": x0, "dps": dps}


@math_command(
    name="mp_taylor",
    category="calculus",
    description="Taylor series coefficients",
    args=[
        {"name": "func", "help": "Function expression"},
        {"name": "x0", "help": "Expansion point"},
        {"name": "n", "type": int, "help": "Number of terms"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_taylor(func: str, x0: str, n: int, dps: int = 50) -> dict:
    """Compute Taylor series coefficients."""
    from mpmath import mp, taylor

    mp.dps = dps
    f = parse_callable(func, library="mpmath")
    coeffs = taylor(f, mp.mpf(x0), n)
    return {"coefficients": [str(c) for c in coeffs], "x0": x0, "n_terms": n, "dps": dps}


@math_command(
    name="mp_nsum",
    category="calculus",
    description="Numerical infinite series summation",
    args=[
        {"name": "func", "help": "Function expression f(n)"},
        {"name": "a", "type": int, "help": "Starting index"},
        {"name": "--b", "default": "inf", "help": "Ending index (default: inf)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_nsum(func: str, a: int, b: str = "inf", dps: int = 50) -> dict:
    """Numerical summation of infinite series."""
    from mpmath import inf, mp, nsum

    mp.dps = dps
    f = parse_callable(func, library="mpmath", variables=["n"])
    b_val = inf if b.lower() == "inf" else int(b)
    r = nsum(f, [a, b_val])
    return {"result": str(r), "range": [a, b], "dps": dps}


@math_command(
    name="mp_nprod",
    category="calculus",
    description="Numerical infinite product",
    args=[
        {"name": "func", "help": "Function expression f(n)"},
        {"name": "a", "type": int, "help": "Starting index"},
        {"name": "--b", "default": "inf", "help": "Ending index"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_nprod(func: str, a: int, b: str = "inf", dps: int = 50) -> dict:
    """Numerical evaluation of infinite products."""
    from mpmath import inf, mp, nprod

    mp.dps = dps
    f = parse_callable(func, library="mpmath", variables=["n"])
    b_val = inf if b.lower() == "inf" else int(b)
    r = nprod(f, [a, b_val])
    return {"result": str(r), "range": [a, b], "dps": dps}


@math_command(
    name="mp_sumem",
    category="calculus",
    description="Euler-Maclaurin summation",
    args=[
        {"name": "func", "help": "Function expression"},
        {"name": "a", "type": int, "help": "Starting index"},
        {"name": "b", "type": int, "help": "Ending index"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_sumem(func: str, a: int, b: int, dps: int = 50) -> dict:
    """Euler-Maclaurin summation formula."""
    from mpmath import mp, sumem

    mp.dps = dps
    f = parse_callable(func, library="mpmath", variables=["n"])
    r = sumem(f, [a, b])
    return {"result": str(r), "range": [a, b], "dps": dps}


@math_command(
    name="mp_findroot",
    category="calculus",
    description="Find root of function",
    args=[
        {"name": "func", "help": "Function expression"},
        {"name": "x0", "help": "Initial guess"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_findroot(func: str, x0: str, dps: int = 50) -> dict:
    """Find root of function using Newton's method."""
    from mpmath import findroot, mp

    mp.dps = dps
    f = parse_callable(func, library="mpmath")
    r = findroot(f, mp.mpf(x0))
    return {"result": str(r), "initial_guess": x0, "dps": dps}


@math_command(
    name="mp_secant",
    category="calculus",
    description="Find root using secant method",
    args=[
        {"name": "func", "help": "Function expression"},
        {"name": "x0", "help": "First initial guess"},
        {"name": "x1", "help": "Second initial guess"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_secant(func: str, x0: str, x1: str, dps: int = 50) -> dict:
    """Find root using secant method."""
    from mpmath import findroot, mp

    mp.dps = dps
    f = parse_callable(func, library="mpmath")
    r = findroot(f, (mp.mpf(x0), mp.mpf(x1)), solver="secant")
    return {"result": str(r), "initial_guesses": [x0, x1], "dps": dps}


@math_command(
    name="mp_polyroots",
    category="calculus",
    description="Find all roots of polynomial",
    args=[
        {"name": "coeffs", "help": "Polynomial coefficients [a_n, ..., a_1, a_0]"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_polyroots(coeffs: str, dps: int = 50) -> dict:
    """Find all roots of polynomial given coefficients."""
    import ast

    from mpmath import mp, polyroots

    mp.dps = dps
    c = ast.literal_eval(coeffs)
    roots = polyroots(c)
    return {"roots": [str(r) for r in roots], "dps": dps}


@math_command(
    name="mp_fourier",
    category="calculus",
    description="Fourier series coefficients",
    args=[
        {"name": "func", "help": "Function expression"},
        {"name": "n", "type": int, "help": "Number of terms"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_fourier(func: str, n: int, dps: int = 50) -> dict:
    """Compute Fourier series coefficients."""
    from mpmath import fourier, mp

    mp.dps = dps
    f = parse_callable(func, library="mpmath")
    cs, ss = fourier(f, [-mp.pi, mp.pi], n)
    return {
        "cos_coeffs": [str(c) for c in cs],
        "sin_coeffs": [str(s) for s in ss],
        "n_terms": n,
        "dps": dps,
    }


@math_command(
    name="mp_fourierval",
    category="calculus",
    description="Evaluate Fourier series at point",
    args=[
        {"name": "cos_coeffs", "help": "Cosine coefficients as list"},
        {"name": "sin_coeffs", "help": "Sine coefficients as list"},
        {"name": "x", "help": "Point to evaluate at"},
        {
            "name": "--interval",
            "default": "[-pi,pi]",
            "help": "Interval [a,b] for Fourier series (default: [-pi,pi])",
        },
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_fourierval(
    cos_coeffs: str, sin_coeffs: str, x: str, interval: str = "[-pi,pi]", dps: int = 50
) -> dict:
    """Evaluate Fourier series at a point."""
    import ast

    from mpmath import fourierval, mp

    mp.dps = dps
    cs = [mp.mpf(c) for c in ast.literal_eval(cos_coeffs)]
    ss = [mp.mpf(s) for s in ast.literal_eval(sin_coeffs)]
    # Parse interval, replacing 'pi' with actual pi value
    interval_str = interval.replace("pi", str(mp.pi))
    ab = ast.literal_eval(interval_str)
    ab = [mp.mpf(a) for a in ab]
    # fourierval(series, interval, x) - note the argument order!
    r = fourierval((cs, ss), ab, mp.mpf(x))
    return {"result": str(r), "x": x, "interval": interval, "dps": dps}


@math_command(
    name="mp_odefun",
    category="calculus",
    description="Solve ODE y' = f(x,y) numerically",
    args=[
        {"name": "func", "help": "RHS function f(x,y)"},
        {"name": "x0", "help": "Initial x"},
        {"name": "y0", "help": "Initial y"},
        {"name": "x1", "help": "Target x"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_odefun(func: str, x0: str, y0: str, x1: str, dps: int = 50) -> dict:
    """Solve first-order ODE y' = f(x,y)."""
    from mpmath import mp, odefun

    mp.dps = dps
    f = parse_callable(func, library="mpmath", variables=["x", "y"])
    sol = odefun(f, mp.mpf(x0), mp.mpf(y0))
    r = sol(mp.mpf(x1))
    return {"result": str(r), "x0": x0, "y0": y0, "x1": x1, "dps": dps}


@math_command(
    name="mp_chebyfit",
    category="calculus",
    description="Chebyshev interpolation fit from data",
    args=[
        {"name": "func", "help": "Function expression"},
        {"name": "interval", "help": "Interval as [a,b]"},
        {"name": "n", "type": int, "help": "Number of points"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_chebyfit(func: str, interval: str, n: int, dps: int = 50) -> dict:
    """Chebyshev interpolation."""
    import ast

    from mpmath import chebyfit, mp

    mp.dps = dps
    f = parse_callable(func, library="mpmath")
    iv = ast.literal_eval(interval)
    poly, err = chebyfit(f, iv, n, error=True)
    return {"polynomial_callable": "returned", "error_estimate": str(err), "n": n, "dps": dps}


@math_command(
    name="mp_pade",
    category="calculus",
    description="Pade approximant coefficients",
    args=[
        {"name": "coeffs", "help": "Taylor series coefficients as list"},
        {"name": "m", "type": int, "help": "Numerator degree"},
        {"name": "n", "type": int, "help": "Denominator degree"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_pade(coeffs: str, m: int, n: int, dps: int = 50) -> dict:
    """Compute Pade approximant from Taylor coefficients."""
    import ast

    from mpmath import mp, pade

    mp.dps = dps
    c = [mp.mpf(x) for x in ast.literal_eval(coeffs)]
    p, q = pade(c, m, n)
    return {
        "numerator_coeffs": [str(x) for x in p],
        "denominator_coeffs": [str(x) for x in q],
        "degrees": [m, n],
        "dps": dps,
    }


@math_command(
    name="mp_nint",
    category="calculus",
    description="Numerical integration (alias for quad)",
    args=[
        {"name": "func", "help": "Function expression"},
        {"name": "a", "help": "Lower bound"},
        {"name": "b", "help": "Upper bound"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_nint(func: str, a: str, b: str, dps: int = 50) -> dict:
    """Numerical integration (alias for quad)."""
    from mpmath import mp, quad

    mp.dps = dps
    f = parse_callable(func, library="mpmath")
    r = quad(f, [parse_bound(a), parse_bound(b)])
    return {"result": str(r), "interval": [a, b], "dps": dps}


@math_command(
    name="mp_taylor_series",
    category="calculus",
    description="Generate Taylor series as symbolic expression",
    args=[
        {"name": "func", "help": "Function expression"},
        {"name": "x0", "help": "Expansion point"},
        {"name": "n", "type": int, "help": "Number of terms"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_taylor_series(func: str, x0: str, n: int, dps: int = 50) -> dict:
    """Generate Taylor series expansion."""
    from mpmath import mp, taylor

    mp.dps = dps
    f = parse_callable(func, library="mpmath")
    coeffs = taylor(f, mp.mpf(x0), n)
    terms = []
    for i, c in enumerate(coeffs):
        if c != 0:
            if i == 0:
                terms.append(str(c))
            elif i == 1:
                terms.append(f"{c}*(x-{x0})")
            else:
                terms.append(f"{c}*(x-{x0})^{i}")
    return {
        "series": " + ".join(terms) if terms else "0",
        "coefficients": [str(c) for c in coeffs],
        "dps": dps,
    }


@math_command(
    name="mp_diff_chain",
    category="calculus",
    description="Differentiate composite function (chain rule)",
    args=[
        {"name": "outer", "help": "Outer function f"},
        {"name": "inner", "help": "Inner function g"},
        {"name": "x", "help": "Point to evaluate at"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_diff_chain(outer: str, inner: str, x: str, dps: int = 50) -> dict:
    """Compute derivative of f(g(x)) using chain rule."""
    from mpmath import diff, mp

    mp.dps = dps
    f = parse_callable(outer, library="mpmath")
    g = parse_callable(inner, library="mpmath")
    gx = g(mp.mpf(x))
    f_prime_gx = diff(f, gx)
    g_prime_x = diff(g, mp.mpf(x))
    r = f_prime_gx * g_prime_x
    return {
        "result": str(r),
        "f_prime_at_gx": str(f_prime_gx),
        "g_prime_at_x": str(g_prime_x),
        "dps": dps,
    }


@math_command(
    name="mp_diffs",
    category="calculus",
    description="All derivatives up to order n",
    args=[
        {"name": "func", "help": "Function expression"},
        {"name": "x", "help": "Point to evaluate at"},
        {"name": "n", "type": int, "help": "Maximum order"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_diffs(func: str, x: str, n: int, dps: int = 50) -> dict:
    """Compute all derivatives up to order n."""
    from mpmath import diff, mp

    mp.dps = dps
    f = parse_callable(func, library="mpmath")
    derivs = [str(diff(f, mp.mpf(x), k)) for k in range(n + 1)]
    return {"derivatives": derivs, "x": x, "max_order": n, "dps": dps}


@math_command(
    name="mp_diffs_prod",
    category="calculus",
    description="Derivative of product f*g (product rule)",
    args=[
        {"name": "f", "help": "First function"},
        {"name": "g", "help": "Second function"},
        {"name": "x", "help": "Point to evaluate at"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_diffs_prod(f: str, g: str, x: str, dps: int = 50) -> dict:
    """Compute derivative of f*g using product rule."""
    from mpmath import diff, mp

    mp.dps = dps
    func_f = parse_callable(f, library="mpmath")
    func_g = parse_callable(g, library="mpmath")
    xv = mp.mpf(x)
    f_val = func_f(xv)
    g_val = func_g(xv)
    f_prime = diff(func_f, xv)
    g_prime = diff(func_g, xv)
    r = f_prime * g_val + f_val * g_prime
    return {
        "result": str(r),
        "f_prime_g": str(f_prime * g_val),
        "f_g_prime": str(f_val * g_prime),
        "dps": dps,
    }


@math_command(
    name="mp_diffs_exp",
    category="calculus",
    description="Derivative of exponential f^g",
    args=[
        {"name": "base", "help": "Base function f"},
        {"name": "exponent", "help": "Exponent function g"},
        {"name": "x", "help": "Point to evaluate at"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_diffs_exp(base: str, exponent: str, x: str, dps: int = 50) -> dict:
    """Compute derivative of f^g (logarithmic differentiation)."""
    from mpmath import diff, log, mp

    mp.dps = dps
    f = parse_callable(base, library="mpmath")
    g = parse_callable(exponent, library="mpmath")
    xv = mp.mpf(x)
    fv = f(xv)
    gv = g(xv)
    f_prime = diff(f, xv)
    g_prime = diff(g, xv)
    r = (fv**gv) * (g_prime * log(fv) + gv * f_prime / fv)
    return {"result": str(r), "dps": dps}


# =============================================================================
# LINEAR ALGEBRA (26 functions)
# =============================================================================


@math_command(
    name="mp_matrix",
    category="mp_linalg",
    description="Create mpmath matrix from data",
    args=[
        {"name": "data", "help": "Matrix data as nested list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_matrix(data: str, dps: int = 50) -> dict:
    """Create an mpmath matrix from nested list data."""
    import ast

    from mpmath import matrix, mp

    mp.dps = dps
    d = ast.literal_eval(data)
    M = matrix(d)
    return {"rows": M.rows, "cols": M.cols, "matrix": str(M), "dps": dps}


@math_command(
    name="mp_eye",
    category="mp_linalg",
    description="Identity matrix of size n",
    args=[
        {"name": "n", "type": int, "help": "Matrix size"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_eye(n: int, dps: int = 50) -> dict:
    """Create identity matrix of size n."""
    from mpmath import eye, mp

    mp.dps = dps
    M = eye(n)
    return {"size": n, "matrix": str(M), "dps": dps}


@math_command(
    name="mp_zeros",
    category="mp_linalg",
    description="Zero matrix of size m x n",
    args=[
        {"name": "m", "type": int, "help": "Number of rows"},
        {"name": "n", "type": int, "help": "Number of columns"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_zeros(m: int, n: int, dps: int = 50) -> dict:
    """Create zero matrix of size m x n."""
    from mpmath import mp, zeros

    mp.dps = dps
    M = zeros(m, n)
    return {"shape": [m, n], "matrix": str(M), "dps": dps}


@math_command(
    name="mp_ones",
    category="mp_linalg",
    description="Matrix of ones of size m x n",
    args=[
        {"name": "m", "type": int, "help": "Number of rows"},
        {"name": "n", "type": int, "help": "Number of columns"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_ones(m: int, n: int, dps: int = 50) -> dict:
    """Create matrix of ones of size m x n."""
    from mpmath import mp, ones

    mp.dps = dps
    M = ones(m, n)
    return {"shape": [m, n], "matrix": str(M), "dps": dps}


@math_command(
    name="mp_diag",
    category="mp_linalg",
    description="Diagonal matrix from list of values",
    args=[
        {"name": "values", "help": "Diagonal values as list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_diag(values: str, dps: int = 50) -> dict:
    """Create diagonal matrix from list of values."""
    import ast

    from mpmath import diag, mp

    mp.dps = dps
    v = [mp.mpf(x) for x in ast.literal_eval(values)]
    M = diag(v)
    return {"size": len(v), "matrix": str(M), "dps": dps}


@math_command(
    name="mp_det",
    category="mp_linalg",
    description="Matrix determinant (arbitrary precision)",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_det(matrix: str, dps: int = 50) -> dict:
    """Compute matrix determinant to arbitrary precision."""
    from mpmath import det, mp
    from mpmath import matrix as mp_matrix

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    r = det(M)
    return {"result": str(r), "dps": dps}


@math_command(
    name="mp_lu",
    category="mp_linalg",
    description="LU decomposition",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_lu(matrix: str, dps: int = 50) -> dict:
    """Compute LU decomposition."""
    from mpmath import lu, mp
    from mpmath import matrix as mp_matrix

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    P, L, U = lu(M)
    return {"P": str(P), "L": str(L), "U": str(U), "dps": dps}


@math_command(
    name="mp_lu_solve",
    category="mp_linalg",
    description="Solve linear system using LU decomposition",
    args=[
        {"name": "matrix", "help": "Coefficient matrix"},
        {"name": "b", "help": "Right-hand side vector"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_lu_solve(matrix: str, b: str, dps: int = 50) -> dict:
    """Solve linear system Ax = b using LU decomposition."""
    import ast

    from mpmath import lu_solve, mp
    from mpmath import matrix as mp_matrix

    mp.dps = dps
    A = mp_matrix(parse_matrix(matrix).tolist())
    b_vec = mp_matrix([mp.mpf(x) for x in ast.literal_eval(b)])
    x = lu_solve(A, b_vec)
    return {"solution": [str(xi) for xi in x], "dps": dps}


@math_command(
    name="mp_qr",
    category="mp_linalg",
    description="QR decomposition",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_qr(matrix: str, dps: int = 50) -> dict:
    """Compute QR decomposition."""
    from mpmath import matrix as mp_matrix
    from mpmath import mp, qr

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    Q, R = qr(M)
    return {"Q": str(Q), "R": str(R), "dps": dps}


@math_command(
    name="mp_cholesky",
    category="mp_linalg",
    description="Cholesky decomposition (for positive definite matrix)",
    args=[
        {"name": "matrix", "help": "Positive definite matrix"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_cholesky(matrix: str, dps: int = 50) -> dict:
    """Compute Cholesky decomposition A = L*L^T."""
    from mpmath import cholesky, mp
    from mpmath import matrix as mp_matrix

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    L = cholesky(M)
    return {"L": str(L), "dps": dps}


@math_command(
    name="mp_svd",
    category="mp_linalg",
    description="Singular value decomposition",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_svd(matrix: str, dps: int = 50) -> dict:
    """Compute singular value decomposition A = U*S*V^T."""
    from mpmath import matrix as mp_matrix
    from mpmath import mp, svd

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    U, S, V = svd(M)
    return {"U": str(U), "S": [str(s) for s in S], "V": str(V), "dps": dps}


@math_command(
    name="mp_norm",
    category="mp_linalg",
    description="Vector norm",
    args=[
        {"name": "vector", "help": "Vector as list"},
        {"name": "--p", "type": float, "default": 2.0, "help": "Norm order (default: 2)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_norm(vector: str, p: float = 2.0, dps: int = 50) -> dict:
    """Compute p-norm of vector."""
    import ast

    from mpmath import matrix as mp_matrix
    from mpmath import mp, norm

    mp.dps = dps
    v = mp_matrix([mp.mpf(x) for x in ast.literal_eval(vector)])
    r = norm(v, p)
    return {"result": str(r), "p": p, "dps": dps}


@math_command(
    name="mp_mnorm",
    category="mp_linalg",
    description="Matrix norm",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "--p", "default": "2", "help": "Norm type: 1, 2, inf, or fro"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_mnorm(matrix: str, p: str = "2", dps: int = 50) -> dict:
    """Compute matrix norm."""
    from mpmath import inf, mnorm, mp
    from mpmath import matrix as mp_matrix

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    p_val = inf if p.lower() == "inf" else p
    r = mnorm(M, p_val)
    return {"result": str(r), "norm_type": p, "dps": dps}


@math_command(
    name="mp_cond",
    category="mp_linalg",
    description="Matrix condition number",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_cond(matrix: str, dps: int = 50) -> dict:
    """Compute condition number of matrix."""
    from mpmath import matrix as mp_matrix
    from mpmath import mp, svd

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    _, S, _ = svd(M)
    s_max = max(S)
    s_min = min(s for s in S if s > 0)
    cond = s_max / s_min
    return {"result": str(cond), "sigma_max": str(s_max), "sigma_min": str(s_min), "dps": dps}


@math_command(
    name="mp_inverse",
    category="mp_linalg",
    description="Matrix inverse",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_inverse(matrix: str, dps: int = 50) -> dict:
    """Compute matrix inverse."""
    from mpmath import inverse, mp
    from mpmath import matrix as mp_matrix

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    M_inv = inverse(M)
    return {"result": str(M_inv), "dps": dps}


@math_command(
    name="mp_eig",
    category="mp_linalg",
    description="Eigenvalues and eigenvectors (general matrix)",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_eig(matrix: str, dps: int = 50) -> dict:
    """Compute eigenvalues and eigenvectors."""
    from mpmath import eig, mp
    from mpmath import matrix as mp_matrix

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    E, EL, ER = eig(M, left=True, right=True)
    return {
        "eigenvalues": [str(e) for e in E],
        "left_eigenvectors": str(EL),
        "right_eigenvectors": str(ER),
        "dps": dps,
    }


@math_command(
    name="mp_eigsy",
    category="mp_linalg",
    description="Eigenvalues of symmetric real matrix",
    args=[
        {"name": "matrix", "help": "Symmetric matrix"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_eigsy(matrix: str, dps: int = 50) -> dict:
    """Compute eigenvalues of symmetric real matrix."""
    from mpmath import eigsy, mp
    from mpmath import matrix as mp_matrix

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    E, Q = eigsy(M)
    return {"eigenvalues": [str(e) for e in E], "eigenvectors": str(Q), "dps": dps}


@math_command(
    name="mp_eighe",
    category="mp_linalg",
    description="Eigenvalues of Hermitian matrix",
    args=[
        {"name": "matrix", "help": "Hermitian matrix"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_eighe(matrix: str, dps: int = 50) -> dict:
    """Compute eigenvalues of Hermitian matrix."""
    from mpmath import eighe, mp
    from mpmath import matrix as mp_matrix

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    E, Q = eighe(M)
    return {"eigenvalues": [str(e) for e in E], "eigenvectors": str(Q), "dps": dps}


@math_command(
    name="mp_hessenberg",
    category="mp_linalg",
    description="Hessenberg decomposition",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_hessenberg(matrix: str, dps: int = 50) -> dict:
    """Compute Hessenberg form A = Q*H*Q^T."""
    from mpmath import hessenberg, mp
    from mpmath import matrix as mp_matrix

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    A, Q = hessenberg(M)
    return {"H": str(A), "Q": str(Q), "dps": dps}


@math_command(
    name="mp_schur",
    category="mp_linalg",
    description="Schur decomposition",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_schur(matrix: str, dps: int = 50) -> dict:
    """Compute Schur decomposition A = Q*T*Q^T."""
    from mpmath import matrix as mp_matrix
    from mpmath import mp, schur

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    T, Q = schur(M)
    return {"T": str(T), "Q": str(Q), "dps": dps}


@math_command(
    name="mp_expm",
    category="mp_linalg",
    description="Matrix exponential",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_expm(matrix: str, dps: int = 50) -> dict:
    """Compute matrix exponential exp(A)."""
    from mpmath import expm, mp
    from mpmath import matrix as mp_matrix

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    R = expm(M)
    return {"result": str(R), "dps": dps}


@math_command(
    name="mp_logm",
    category="mp_linalg",
    description="Matrix logarithm",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_logm(matrix: str, dps: int = 50) -> dict:
    """Compute matrix logarithm log(A)."""
    from mpmath import logm, mp
    from mpmath import matrix as mp_matrix

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    R = logm(M)
    return {"result": str(R), "dps": dps}


@math_command(
    name="mp_sqrtm",
    category="mp_linalg",
    description="Matrix square root",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_sqrtm(matrix: str, dps: int = 50) -> dict:
    """Compute matrix square root sqrt(A)."""
    from mpmath import matrix as mp_matrix
    from mpmath import mp, sqrtm

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    R = sqrtm(M)
    return {"result": str(R), "dps": dps}


@math_command(
    name="mp_powm",
    category="mp_linalg",
    description="Matrix power",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "n", "help": "Power (can be fractional)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_powm(matrix: str, n: str, dps: int = 50) -> dict:
    """Compute matrix power A^n."""
    from mpmath import matrix as mp_matrix
    from mpmath import mp, powm

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    R = powm(M, mp.mpf(n))
    return {"result": str(R), "power": n, "dps": dps}


@math_command(
    name="mp_sinm",
    category="mp_linalg",
    description="Matrix sine",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_sinm(matrix: str, dps: int = 50) -> dict:
    """Compute matrix sine sin(A)."""
    from mpmath import matrix as mp_matrix
    from mpmath import mp, sinm

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    R = sinm(M)
    return {"result": str(R), "dps": dps}


@math_command(
    name="mp_cosm",
    category="mp_linalg",
    description="Matrix cosine",
    args=[
        {"name": "matrix", "help": "Matrix as nested list"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_cosm(matrix: str, dps: int = 50) -> dict:
    """Compute matrix cosine cos(A)."""
    from mpmath import cosm, mp
    from mpmath import matrix as mp_matrix

    mp.dps = dps
    M = mp_matrix(parse_matrix(matrix).tolist())
    R = cosm(M)
    return {"result": str(R), "dps": dps}


# =============================================================================
# UTILITY (17 functions)
# =============================================================================


@math_command(
    name="mp_nstr",
    category="mp_utility",
    description="Format number as string with specified digits",
    args=[
        {"name": "x", "help": "Number to format"},
        {"name": "n", "type": int, "help": "Number of digits"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places for computation"},
    ],
)
def cmd_mp_nstr(x: str, n: int, dps: int = 50) -> dict:
    """Format mpf number as string with n significant digits."""
    from mpmath import mp, nstr

    mp.dps = dps
    r = nstr(mp.mpf(x), n)
    return {"result": r, "digits": n}


@math_command(
    name="mp_nprint",
    category="mp_utility",
    description="Return formatted number string",
    args=[
        {"name": "x", "help": "Number to format"},
        {"name": "--n", "type": int, "default": 6, "help": "Number of digits"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_nprint(x: str, n: int = 6, dps: int = 50) -> dict:
    """Return formatted representation of number."""
    from mpmath import mp, nstr

    mp.dps = dps
    r = nstr(mp.mpf(x), n)
    return {"result": r, "digits": n}


@math_command(
    name="mp_identify",
    category="mp_utility",
    description="Identify number as simple formula",
    args=[
        {"name": "x", "help": "Number to identify"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_identify(x: str, dps: int = 50) -> dict:
    """Attempt to identify number as closed-form expression."""
    from mpmath import identify, mp

    mp.dps = dps
    r = identify(mp.mpf(x))
    return {"result": r if r else "No identification found", "input": x}


@math_command(
    name="mp_pslq",
    category="mp_utility",
    description="PSLQ integer relation algorithm",
    args=[
        {"name": "values", "help": "List of numbers to find relation"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_pslq(values: str, dps: int = 50) -> dict:
    """Find integer relation using PSLQ algorithm."""
    import ast

    from mpmath import mp, pslq

    mp.dps = dps
    v = [mp.mpf(x) for x in ast.literal_eval(values)]
    r = pslq(v)
    return {"relation": [int(x) for x in r] if r else None, "dps": dps}


@math_command(
    name="mp_fprod",
    category="mp_utility",
    description="Product of iterable",
    args=[
        {"name": "values", "help": "List of values to multiply"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_fprod(values: str, dps: int = 50) -> dict:
    """Compute product of list of numbers."""
    import ast

    from mpmath import fprod, mp

    mp.dps = dps
    v = [mp.mpf(x) for x in ast.literal_eval(values)]
    r = fprod(v)
    return {"result": str(r), "count": len(v), "dps": dps}


@math_command(
    name="mp_fsum",
    category="mp_utility",
    description="Accurate sum of iterable",
    args=[
        {"name": "values", "help": "List of values to sum"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_fsum(values: str, dps: int = 50) -> dict:
    """Compute accurate sum of list of numbers."""
    import ast

    from mpmath import fsum, mp

    mp.dps = dps
    v = [mp.mpf(x) for x in ast.literal_eval(values)]
    r = fsum(v)
    return {"result": str(r), "count": len(v), "dps": dps}


@math_command(
    name="mp_almosteq",
    category="mp_utility",
    description="Test if two numbers are almost equal",
    args=[
        {"name": "a", "help": "First number"},
        {"name": "b", "help": "Second number"},
        {"name": "--rel_eps", "type": float, "default": 1e-15, "help": "Relative tolerance"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_almosteq(a: str, b: str, rel_eps: float = 1e-15, dps: int = 50) -> dict:
    """Test if two numbers are approximately equal."""
    from mpmath import almosteq, mp

    mp.dps = dps
    r = almosteq(mp.mpf(a), mp.mpf(b), rel_eps=rel_eps)
    return {"result": r, "a": a, "b": b, "rel_eps": rel_eps}


@math_command(
    name="mp_chop",
    category="mp_utility",
    description="Remove small real/imaginary parts",
    args=[
        {"name": "x", "help": "Number to chop"},
        {"name": "--tol", "type": float, "default": 1e-15, "help": "Tolerance"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_chop(x: str, tol: float = 1e-15, dps: int = 50) -> dict:
    """Remove tiny real/imaginary parts (round near-zero to zero)."""
    from mpmath import chop, mp, mpc

    mp.dps = dps
    if "j" in x.lower() or "i" in x.lower():
        xv = mpc(x.replace("i", "j"))
    else:
        xv = mp.mpf(x)
    r = chop(xv, tol=tol)
    return {"result": str(r), "tolerance": tol}


@math_command(
    name="mp_floor",
    category="mp_utility",
    description="Floor function (greatest integer <= x)",
    args=[
        {"name": "x", "help": "Number"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_floor(x: str, dps: int = 50) -> dict:
    """Compute floor of number."""
    from mpmath import floor, mp

    mp.dps = dps
    r = floor(mp.mpf(x))
    return {"result": str(r), "input": x}


@math_command(
    name="mp_ceil",
    category="mp_utility",
    description="Ceiling function (least integer >= x)",
    args=[
        {"name": "x", "help": "Number"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_ceil(x: str, dps: int = 50) -> dict:
    """Compute ceiling of number."""
    from mpmath import ceil, mp

    mp.dps = dps
    r = ceil(mp.mpf(x))
    return {"result": str(r), "input": x}


@math_command(
    name="mp_sign",
    category="mp_utility",
    description="Sign of number (-1, 0, or 1)",
    args=[
        {"name": "x", "help": "Number"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_sign(x: str, dps: int = 50) -> dict:
    """Compute sign of number."""
    from mpmath import mp, sign

    mp.dps = dps
    r = sign(mp.mpf(x))
    return {"result": str(r), "input": x}


@math_command(
    name="mp_arg",
    category="mp_utility",
    description="Argument (phase) of complex number",
    args=[
        {"name": "z", "help": "Complex number"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_arg(z: str, dps: int = 50) -> dict:
    """Compute argument (phase angle) of complex number."""
    from mpmath import arg, mp

    mp.dps = dps
    zv = parse_complex(z)
    r = arg(zv)
    return {"result": str(r), "input": z}


@math_command(
    name="mp_re",
    category="mp_utility",
    description="Real part of complex number",
    args=[
        {"name": "z", "help": "Complex number"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_re(z: str, dps: int = 50) -> dict:
    """Extract real part of complex number."""
    from mpmath import mp, re

    mp.dps = dps
    zv = parse_complex(z)
    r = re(zv)
    return {"result": str(r), "input": z}


@math_command(
    name="mp_im",
    category="mp_utility",
    description="Imaginary part of complex number",
    args=[
        {"name": "z", "help": "Complex number"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_im(z: str, dps: int = 50) -> dict:
    """Extract imaginary part of complex number."""
    from mpmath import im, mp

    mp.dps = dps
    zv = parse_complex(z)
    r = im(zv)
    return {"result": str(r), "input": z}


@math_command(
    name="mp_conj",
    category="mp_utility",
    description="Complex conjugate",
    args=[
        {"name": "z", "help": "Complex number"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_conj(z: str, dps: int = 50) -> dict:
    """Compute complex conjugate."""
    from mpmath import conj, mp

    mp.dps = dps
    zv = parse_complex(z)
    r = conj(zv)
    return {"result": str(r), "input": z}


@math_command(
    name="mp_fabs",
    category="mp_utility",
    description="Absolute value (magnitude)",
    args=[
        {"name": "x", "help": "Number (real or complex)"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_fabs(x: str, dps: int = 50) -> dict:
    """Compute absolute value / magnitude."""
    from mpmath import fabs, mp, mpc

    mp.dps = dps
    if "j" in x.lower() or "i" in x.lower():
        xv = mpc(x.replace("i", "j"))
    else:
        xv = mp.mpf(x)
    r = fabs(xv)
    return {"result": str(r), "input": x}


@math_command(
    name="mp_mag",
    category="mp_utility",
    description="Magnitude (floor of log2 of absolute value)",
    args=[
        {"name": "x", "help": "Number"},
        {"name": "--dps", "type": int, "default": 50, "help": "Decimal places"},
    ],
)
def cmd_mp_mag(x: str, dps: int = 50) -> dict:
    """Compute magnitude (floor of binary exponent)."""
    from mpmath import mag, mp

    mp.dps = dps
    r = mag(mp.mpf(x))
    return {"result": r, "input": x}


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    parser = create_main_parser(
        "mpmath_compute",
        "mpmath arbitrary-precision CLI - 221 functions across 17 categories",
        epilog="""
Examples:
    # Get pi to 100 decimal places
    %(prog)s pi --dps 100

    # Square root of 2 to 100 decimal places
    %(prog)s mp_sqrt "2" --dps 100

    # Trig functions
    %(prog)s mp_sin "1" --dps 50
    %(prog)s mp_atan2 "1" "1" --dps 50

    # Hyperbolic functions
    %(prog)s mp_sinh "1" --dps 50

    # Gamma functions
    %(prog)s mp_gamma "5" --dps 50
    %(prog)s mp_factorial "10" --dps 50
    %(prog)s mp_binomial "10" "5" --dps 50

    # Zeta functions
    %(prog)s mp_zeta "2" --dps 50
    %(prog)s mp_polylog "2" "0.5" --dps 50

    # Hypergeometric functions
    %(prog)s mp_hyp2f1 "1" "2" "3" "0.5" --dps 50

    # Bessel functions
    %(prog)s mp_besselj "0" "1" --dps 50
    %(prog)s mp_airyai "1" --dps 50

Categories:
    precision (4): set_dps, get_dps, set_prec, get_prec
    constants (14): pi, e, euler, catalan, phi, khinchin, glaisher,
                    apery, mertens, twinprime, degree, inf, nan, j
    elementary (10): mp_sqrt, mp_cbrt, mp_root, mp_exp, mp_expm1,
                     mp_log, mp_log10, mp_log1p, mp_power, mp_lambertw
    trigonometric (12): mp_sin, mp_cos, mp_tan, mp_sec, mp_csc, mp_cot,
                        mp_asin, mp_acos, mp_atan, mp_atan2, mp_sinpi, mp_cospi
    hyperbolic (6): mp_sinh, mp_cosh, mp_tanh, mp_asinh, mp_acosh, mp_atanh
    gamma (14): mp_gamma, mp_rgamma, mp_loggamma, mp_factorial, mp_fac2,
                mp_rf, mp_ff, mp_binomial, mp_beta, mp_betainc, mp_gammainc,
                mp_digamma, mp_polygamma, mp_harmonic
    zeta (8): mp_zeta, mp_altzeta, mp_dirichlet, mp_polylog, mp_lerchphi,
              mp_stieltjes, mp_primezeta, mp_secondzeta
    hypergeometric (11): mp_hyp0f1, mp_hyp1f1, mp_hyp1f2, mp_hyp2f0, mp_hyp2f1,
                         mp_hyp2f2, mp_hyp3f2, mp_hyperu, mp_hyper, mp_meijerg,
                         mp_appellf1
    bessel (17): mp_besselj, mp_bessely, mp_besseli, mp_besselk, mp_hankel1,
                 mp_hankel2, mp_airyai, mp_airybi, mp_airyaizero, mp_airybizero,
                 mp_struveh, mp_struvel, mp_kelvin, mp_ber, mp_bei, mp_ker, mp_kei
    ortho_poly (10): mp_legendre, mp_legenp, mp_legenq, mp_chebyt, mp_chebyu,
                     mp_hermite, mp_gegenbauer, mp_laguerre, mp_jacobi, mp_spherharm
    elliptic (14): mp_ellipk, mp_ellipe, mp_ellipf, mp_ellippi, mp_elliprj,
                   mp_elliprf, mp_elliprc, mp_elliprd, mp_elliprg, mp_agm,
                   mp_jtheta, mp_qfrom, mp_mfrom, mp_kleinj
    error_exp (16): mp_erf, mp_erfc, mp_erfi, mp_erfinv, mp_erfcinv, mp_npdf,
                    mp_ncdf, mp_ei, mp_li, mp_ci, mp_si, mp_chi, mp_shi,
                    mp_fresnels, mp_fresnelc, mp_expint
    number_theory (17): mp_primepi, mp_prime, mp_isprime, mp_nextprime, mp_prevprime,
                        mp_moebius, mp_bernoulli, mp_euler_number, mp_stirling1,
                        mp_stirling2, mp_bell, mp_npartitions, mp_fibonacci,
                        mp_lucas, mp_gcd, mp_lcm, mp_isqrt
""",
    )
    sys.exit(main_cli(parser, get_registry()))
