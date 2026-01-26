#!/usr/bin/env python3
"""Toggle math features on or off.

Cross-platform script for Windows, macOS, and Linux.

USAGE:
    # Install math features
    uv run python scripts/setup/math_features.py --install

    # Check if math features are installed
    uv run python scripts/setup/math_features.py --status

    # Verify all math imports work
    uv run python scripts/setup/math_features.py --verify
"""

import argparse
import subprocess
import sys


def check_status() -> dict[str, bool]:
    """Check which math packages are installed."""
    packages = {
        "sympy": False,
        "z3": False,
        "pint": False,
        "scipy": False,
        "numpy": False,
        "mpmath": False,
    }

    for pkg in packages:
        try:
            __import__(pkg)
            packages[pkg] = True
        except ImportError:
            packages[pkg] = False

    return packages


def install_math() -> bool:
    """Install math extra dependencies."""
    print("Installing math features...")
    print("  This includes: sympy, z3-solver, pint, scipy, numpy, mpmath")
    print("  Note: z3-solver is ~35MB\n")

    try:
        result = subprocess.run(
            ["uv", "sync", "--extra", "math"],
            timeout=300,  # 5 min timeout
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("ERROR: Installation timed out")
        return False
    except FileNotFoundError:
        print("ERROR: 'uv' not found. Please install uv first:")
        print("  curl -LsSf https://astral.sh/uv/install.sh | sh")
        return False


def verify_imports() -> dict[str, str]:
    """Verify math imports and run quick tests."""
    results = {}

    # SymPy - test actual computation
    try:
        import sympy

        x = sympy.Symbol("x")
        solutions = sympy.solve(x**2 - 4, x)
        results["sympy"] = f"OK - v{sympy.__version__}, solved x²-4 = {solutions}"
    except Exception as e:
        results["sympy"] = f"FAIL - {e}"

    # Z3 - test SAT solving
    try:
        import z3

        x = z3.Int("x")
        s = z3.Solver()
        s.add(x > 0, x < 10)
        if s.check() == z3.sat:
            m = s.model()
            results["z3"] = f"OK - SAT, x={m[x]}"
        else:
            results["z3"] = "WARN - import OK but solver returned unsat"
    except Exception as e:
        results["z3"] = f"FAIL - {e}"

    # Pint - test unit conversion
    try:
        import pint

        ureg = pint.UnitRegistry()
        meters = 5 * ureg.meter
        feet = meters.to("feet")
        results["pint"] = f"OK - 5m = {feet.magnitude:.2f}ft"
    except Exception as e:
        results["pint"] = f"FAIL - {e}"

    # mpmath - test arbitrary precision
    try:
        import mpmath

        mpmath.mp.dps = 30
        pi = str(mpmath.pi)[:15]
        results["mpmath"] = f"OK - π = {pi}..."
    except Exception as e:
        results["mpmath"] = f"FAIL - {e}"

    # scipy - test import
    try:
        import scipy

        results["scipy"] = f"OK - v{scipy.__version__}"
    except Exception as e:
        results["scipy"] = f"FAIL - {e}"

    # numpy - test import
    try:
        import numpy

        results["numpy"] = f"OK - v{numpy.__version__}"
    except Exception as e:
        results["numpy"] = f"FAIL - {e}"

    return results


def show_lean_setup():
    """Show Lean 4 + Godel-Prover setup instructions."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║              LEAN 4 + GODEL-PROVER SETUP GUIDE                   ║
╚══════════════════════════════════════════════════════════════════╝

STEP 1: Install Lean 4 + Mathlib
────────────────────────────────
# Install elan (Lean version manager)
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh

# Verify installation
lean --version   # Should show Lean 4.x.x

# Create a new Mathlib project (or use existing)
lake new my-proofs math
cd my-proofs
lake exe cache get   # Download precompiled Mathlib (faster)


STEP 2: Install LMStudio for AI Tactic Suggestions
──────────────────────────────────────────────────
1. Download LMStudio:
   https://lmstudio.ai/
   (Available for Windows, macOS, Linux)

2. In LMStudio:
   - Click "Search" in the left sidebar
   - Search for "Goedel-Prover"
   - Download "Goedel-Prover-V2-8B" (or similar 8B variant)
   - Wait for download to complete (~5GB)

3. Start the server:
   - Go to "Local Server" tab
   - Select the Goedel-Prover model
   - Click "Start Server"
   - Default endpoint: http://127.0.0.1:1234


STEP 3: Configure (Optional)
────────────────────────────
# Custom LMStudio endpoint (if not using default port)
export LMSTUDIO_BASE_URL=http://127.0.0.1:5000

# Add to your shell profile for persistence (.zshrc, .bashrc, or config.fish):
# For zsh/bash: echo 'export LMSTUDIO_BASE_URL=http://127.0.0.1:1234' >> ~/.zshrc
# For fish:     set -gx LMSTUDIO_BASE_URL http://127.0.0.1:1234 (add to config.fish)


HOW IT WORKS
────────────
When you write/edit .lean files, the compiler-in-the-loop hook:
1. Runs `lean` compiler on save
2. Detects errors and `sorry` placeholders
3. Sends context to Godel-Prover for tactic suggestions
4. Returns suggestions in Claude's response

The hook gracefully degrades if LMStudio isn't running.


VERIFY SETUP
────────────
# Test Lean works
echo 'example : 1 + 1 = 2 := rfl' > test.lean && lean test.lean

# Test LMStudio (should return model list)
curl http://127.0.0.1:1234/v1/models
""")


def main():
    parser = argparse.ArgumentParser(
        description="Toggle math features on or off",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Install math features
    uv run python scripts/setup/math_features.py --install

    # Check status
    uv run python scripts/setup/math_features.py --status

    # Verify everything works
    uv run python scripts/setup/math_features.py --verify

    # Show Lean 4 + Godel-Prover setup guide
    uv run python scripts/setup/math_features.py --lean

Platform Support:
    All math packages have pre-built wheels for:
    - Windows (x86_64)
    - macOS (x86_64, arm64)
    - Linux (x86_64, aarch64)
""",
    )
    parser.add_argument("--install", action="store_true", help="Install math dependencies")
    parser.add_argument("--status", action="store_true", help="Check which packages are installed")
    parser.add_argument("--verify", action="store_true", help="Verify imports and run quick tests")
    parser.add_argument(
        "--lean", action="store_true", help="Show Lean 4 + Godel-Prover setup guide"
    )

    args = parser.parse_args()

    if not any([args.install, args.status, args.verify, args.lean]):
        parser.print_help()
        return

    if args.lean:
        show_lean_setup()
        return

    if args.status:
        print("Math Package Status:")
        print("-" * 40)
        status = check_status()
        for pkg, installed in status.items():
            icon = "✓" if installed else "✗"
            print(f"  {icon} {pkg}")

        all_installed = all(status.values())
        print("-" * 40)
        if all_installed:
            print("All math packages installed!")
        else:
            missing = [p for p, i in status.items() if not i]
            print(f"Missing: {', '.join(missing)}")
            print("Install with: uv sync --extra math")

    if args.install:
        if install_math():
            print("\n✓ Math features installed successfully!")
            print("Run --verify to test everything works")
        else:
            print("\n✗ Installation failed")
            sys.exit(1)

    if args.verify:
        print("Verifying Math Features:")
        print("-" * 40)
        results = verify_imports()
        all_ok = True
        for pkg, result in results.items():
            if result.startswith("OK"):
                print(f"  ✓ {pkg}: {result}")
            elif result.startswith("WARN"):
                print(f"  ⚠ {pkg}: {result}")
            else:
                print(f"  ✗ {pkg}: {result}")
                all_ok = False

        print("-" * 40)
        if all_ok:
            print("All math features working!")
        else:
            print("Some features have issues. Try reinstalling:")
            print("  uv sync --extra math --reinstall")


if __name__ == "__main__":
    main()
