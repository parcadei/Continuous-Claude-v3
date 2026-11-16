#!/bin/bash
set -e

cd /Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit
uv run pytest tests/integration/test_security_e2e.py -v
