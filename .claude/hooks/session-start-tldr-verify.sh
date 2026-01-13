#!/bin/bash
# Session start verification for tldr-code
# Silent on success, warns if tldr exists but is not llm-tldr

# Check if tldr symlink exists
if [ ! -L /usr/local/bin/tldr ] && [ ! -f /usr/local/bin/tldr ]; then
    # Not installed - silent, don't fail session
    exit 0
fi

# Run verification
result=$(/usr/local/bin/tldr --help 2>&1)
if echo "$result" | grep -q "Token-efficient code analysis"; then
    # Correct llm-tldr - silent success
    exit 0
else
    # Warning if tldr exists but is not llm-tldr
    echo "[tldr-code] Warning: /usr/local/bin/tldr is not llm-tldr"
    exit 0  # Don't fail session, just warn
fi
