"""Pytest configuration for unit tests."""

import os
import sys
import shutil
from pathlib import Path

# For mutation testing: ensure dependency modules are available in mutants/scripts
PROJECT_ROOT = Path("/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit")
ORIGINAL_SCRIPTS = PROJECT_ROOT / "scripts"
MUTANT_SCRIPTS = PROJECT_ROOT / "mutants" / "scripts"

# Copy dependency files if we're in mutation testing mode
if MUTANT_SCRIPTS.exists():
    for dep_file in ["sympy_compute.py", "z3_solve.py"]:
        src = ORIGINAL_SCRIPTS / dep_file
        dst = MUTANT_SCRIPTS / dep_file
        if src.exists() and not dst.exists():
            shutil.copy(src, dst)

    # Copy entire agentica directory for pattern imports
    src_agentica = ORIGINAL_SCRIPTS / "agentica"
    dst_agentica = MUTANT_SCRIPTS / "agentica"
    if src_agentica.exists() and not dst_agentica.exists():
        shutil.copytree(src_agentica, dst_agentica)
