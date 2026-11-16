#!/usr/bin/env python3
"""
CLI wrapper for z3_erotetic.check_evocation.

Usage:
    echo '{"framework": "UNKNOWN", "auth_method": "jwt"}' | python scripts/z3_erotetic_cli.py

    python scripts/z3_erotetic_cli.py --props '{"framework": "UNKNOWN"}'
"""
import argparse
import json
import sys
from pathlib import Path

# Add parent dir to path for relative import
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.z3_erotetic import check_evocation


def main():
    parser = argparse.ArgumentParser(description="Z3 Erotetic E(X,Q) CLI")
    parser.add_argument("--props", help="JSON dict of propositions")
    args = parser.parse_args()

    if args.props:
        props = json.loads(args.props)
    else:
        # Read from stdin
        props = json.load(sys.stdin)

    result = check_evocation(props)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
