#!/bin/bash
# Install tldr-code (llm-tldr) with system-wide symlink
# Run this after uv pip install llm-tldr

set -e

TLRD_BIN="$HOME/.venv/bin/tldr"
SYMLINK="/usr/local/bin/tldr"

if [ ! -f "$TLRD_BIN" ]; then
    echo "Installing llm-tldr..."
    uv pip install llm-tldr
fi

if [ -f "$TLRD_BIN" ]; then
    echo "Creating symlink at $SYMLINK..."
    sudo ln -sf "$TLRD_BIN" "$SYMLINK"
    echo "Done! Run 'tldr --help' to verify."
else
    echo "Error: tldr binary not found at $TLRD_BIN"
    exit 1
fi
