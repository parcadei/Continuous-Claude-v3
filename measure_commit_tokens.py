#!/usr/bin/env python3
"""
Measure token compression for commit skill v6.0 conversion.

Usage:
    python measure_commit_tokens.py
"""
import tiktoken

def main():
    enc = tiktoken.encoding_for_model('gpt-4')

    # Read original prose version
    with open('.claude/skills/commit/SKILL.md', 'r') as f:
        prose = f.read()

    # Read v6.0 version
    with open('.claude/skills/commit/SKILL.v6.md', 'r') as f:
        v6 = f.read()

    prose_tokens = len(enc.encode(prose))
    v6_tokens = len(enc.encode(v6))
    compression = ((prose_tokens - v6_tokens) / prose_tokens) * 100

    print(f"commit skill:")
    print(f"Prose: {prose_tokens} tokens")
    print(f"v6.0: {v6_tokens} tokens")
    print(f"Compression: {compression:.1f}%")

if __name__ == "__main__":
    main()
