#!/usr/bin/env python3
"""
Basic verification that erotetic_verifier module loads correctly.

Run with: uv run python test_erotetic_basic.py
"""

import sys


def test_module_import():
    """Test that the module is importable."""
    try:
        from scripts.agentica import erotetic_verifier
        print("✓ Module imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Module import failed: {e}")
        return False


def test_function_import():
    """Test that verify_resolution function exists."""
    try:
        from scripts.agentica.erotetic_verifier import verify_resolution
        print("✓ verify_resolution function imported")
        assert callable(verify_resolution), "verify_resolution is not callable"
        print("✓ verify_resolution is callable")
        return True
    except ImportError as e:
        print(f"✗ Function import failed: {e}")
        return False
    except AssertionError as e:
        print(f"✗ Assertion failed: {e}")
        return False


def test_type_import():
    """Test that VerificationResult type exists."""
    try:
        from scripts.agentica.erotetic_verifier import VerificationResult
        print("✓ VerificationResult type imported")
        return True
    except ImportError as e:
        print(f"✗ Type import failed: {e}")
        return False


def test_cli_help():
    """Test that CLI --help works."""
    import subprocess
    try:
        result = subprocess.run(
            ["uv", "run", "python", "-m", "scripts.agentica.erotetic_verifier", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("✓ CLI --help works")
            if "--context" in result.stdout:
                print("✓ CLI shows --context argument")
            return True
        else:
            print(f"✗ CLI --help failed with code {result.returncode}")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"✗ CLI test failed: {e}")
        return False


def main():
    """Run all basic tests."""
    print("=" * 60)
    print("Erotetic Verifier - Basic Verification")
    print("=" * 60)

    tests = [
        ("Module Import", test_module_import),
        ("Function Import", test_function_import),
        ("Type Import", test_type_import),
        ("CLI Help", test_cli_help),
    ]

    results = []
    for name, test_fn in tests:
        print(f"\n{name}:")
        results.append(test_fn())

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    if passed == total:
        print("\n✓ All basic tests passed!")
        print("\nNext steps:")
        print("1. Run unit tests: uv run pytest tests/unit/test_erotetic_verifier.py -v")
        print("2. Start Claude proxy: uv run python scripts/agentica/claude_proxy.py")
        print("3. Run E2E tests: uv run pytest tests/integration/test_erotetic_e2e.py -v")
        return 0
    else:
        print("\n✗ Some tests failed. Check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
