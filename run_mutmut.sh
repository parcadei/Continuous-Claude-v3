#!/bin/bash
# Script to run mutation testing with proper setup
PROJECT_DIR="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit"
cd "$PROJECT_DIR"

# Clean previous runs
rm -rf mutants/ .mutmut-cache

# Run mutmut to generate mutants
uv run mutmut run 2>&1 | head -20

# After mutants are generated, copy dependency files
if [ -d "$PROJECT_DIR/mutants/scripts" ]; then
    echo "Copying dependency files to mutants/scripts..."
    cp "$PROJECT_DIR/scripts/sympy_compute.py" "$PROJECT_DIR/mutants/scripts/"
    cp "$PROJECT_DIR/scripts/z3_solve.py" "$PROJECT_DIR/mutants/scripts/"
    echo "Dependencies copied."
fi

# Continue the mutation run
uv run mutmut run 2>&1
