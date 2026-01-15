# CodeRabbit Reviews Archive

This directory contains PR reviews from both origin and fork repositories.
**Purpose**: Reference dataset for comparing code review quality across LLMs.

> **Note**: Most reviews are from CodeRabbit bot, but some files may include human reviews for completeness.

## Data Structure

Each JSON file contains:
- `commit_id`: Exact commit SHA reviewed
- `submitted_at`: Review timestamp (ISO 8601)
- `body`: Full review markdown with:
  - Actionable comments count
  - Nitpick comments count
  - Files processed
  - Specific line references and suggestions
- `html_url`: Direct link to review on GitHub

## Origin (parcadei/Continuous-Claude-v3)

| PR | State | Author | Title | Reviews | Last Commit |
|----|-------|--------|-------|---------|-------------|
| #100 | MERGED | MiaoDX | fix: Skills use wrong Python venv - add CLAUDE_OPC_DIR setup | [2](origin-pr-100.json) | See JSON |
| #101 | OPEN | MiaoDX | feat: make TLDR hooks optional with user control | [2](origin-pr-101.json) | See JSON |
| #103 | CLOSED | francis-io | Fix tldr-stats skill to work globally across all projects | [1](origin-pr-103.json) | See JSON |
| #17 | MERGED | flashwing-nwrp | Fix: Setup wizard fails when run directly as script | [1](origin-pr-17.json) | See JSON |
| #19 | OPEN | GrigoryEvko | Add cross-platform update script for Continuous Claude v3 | [1](origin-pr-19.json) | See JSON |
| #23 | MERGED | d46 | fix: setup wizard Docker daemon retry and compose file paths | [2](origin-pr-23.json) | See JSON |
| #30 | MERGED | artile | fix: hooks execute from project root instead of hooks directory | [2](origin-pr-30.json) | See JSON |
| #32 | CLOSED | carmandale | fix: wrap hook commands in bash -c for paths with spaces | [1](origin-pr-32.json) | See JSON |
| #33 | CLOSED | anth0nylawrence | optimized skills | [1](origin-pr-33.json) | See JSON |
| #4 | CLOSED | parcadei | Agentica Integration: Multi-Agent Patterns & Code Quality Fixes | [1](origin-pr-4.json) | See JSON |
| #44 | CLOSED | sustinbebustin | fix: rename scripts/math to scripts/mathtools to avoid stdlib shadowing | [1](origin-pr-44.json) | See JSON |
| #47 | OPEN | carmandale | fix: wrap hook commands in bash -c for paths with spaces | [1](origin-pr-47.json) | See JSON |
| #61 | CLOSED | D3CK3R | feat: Port 8t0 features + smart-search-router Option 2 + daemon improvements | [1](origin-pr-61.json) | See JSON |
| #76 | MERGED | ClementWalter | fix: use uv scripts for Python hooks instead of Node.js wrapper | [10](origin-pr-76.json) | See JSON |
| #79 | MERGED | MiaoDX | fix: Correct script paths in skills (mcp/ and core/ subdirectories) | [1](origin-pr-79.json) | See JSON |
| #82 | OPEN | ClementWalter | fix: add missing frontmatter to skills and fix model reference | [2](origin-pr-82.json) | See JSON |
| #83 | MERGED | marcodelpin | fix: persist session ID across hooks via file | [7](origin-pr-83.json) | See JSON |
| #84 | MERGED | ClementWalter | feat: add symlink installation mode for contributors | [15](origin-pr-84.json) | See JSON |
| #85 | CLOSED | marcodelpin | docs: Add remote database setup documentation | [2](origin-pr-85.json) | See JSON |
| #95 | MERGED | MiaoDX | fix: install scripts/mcp/ for external research tools | [1](origin-pr-95.json) | See JSON |
| #97 | MERGED | marcodelpin | feat: add Ollama embedding provider with fallback | [3](origin-pr-97.json) | See JSON |
| #102 | MERGED | parcadei | fix: use unique output filenames to prevent parallel agent collision | [2](origin-pr-102.json) | See JSON |
| #88 | CLOSED | parcadei | fix: use CLAUDE_CONFIG_DIR for tldr_stats.py | [2](origin-pr-88.json) | See JSON |
| #48 | MERGED | UAEpro | Fix formatting of description in SKILL.md | [1](origin-pr-48.json) | See JSON |
| #45 | MERGED | ASRagab | (refactor): Adding Frontmatter to agents and updating contribution guidelines | [1](origin-pr-45.json) | See JSON |
| #38 | CLOSED | OCWC22 | Claude/repo review sponsors fl8 jq | [2](origin-pr-38.json) | See JSON |
| #20 | MERGED | parcadei | fix: add CLAUDE_OPC_DIR env var support for global hook installation | [1](origin-pr-20.json) | See JSON |

## Fork (marcodelpin/Continuous-Claude-v3)

| PR | State | Author | Title | Reviews | Last Commit |
|----|-------|--------|-------|---------|-------------|
| #1 | CLOSED | marcodelpin | feat: add Ollama embedding provider with fallback | [4](fork-pr-1.json) | See JSON |
| #2 | CLOSED | marcodelpin | docs: Add remote database setup documentation | [2](fork-pr-2.json) | See JSON |
| #3 | CLOSED | marcodelpin | fix: persist session ID across hooks via file | [1](fork-pr-3.json) | See JSON |
| #4 | CLOSED | marcodelpin | fix: session heartbeat updates project on ID reuse | [1](fork-pr-4.json) | See JSON |
| #5 | CLOSED | marcodelpin | feat: add Ollama embedding provider with fallback | [1](fork-pr-5.json) | See JSON |
| #10 | CLOSED | marcodelpin | feat: add Ollama embedding provider with fallback | [1](fork-pr-10.json) | See JSON |
| #11 | CLOSED | marcodelpin | feat: add Ollama embedding provider with fallback | [2](fork-pr-11.json) | See JSON |
| #12 | CLOSED | marcodelpin | fix: use per-project session ID file to prevent collision | [1](fork-pr-12.json) | See JSON |
| #13 | CLOSED | marcodelpin | feat: Complete PostgreSQL implementation for all cc-v3 tables | [2](fork-pr-13.json) | See JSON |
| #14 | CLOSED | marcodelpin | feat: Complete PostgreSQL implementation for all cc-v3 tables | [2](fork-pr-14.json) | See JSON |

## Review Detail Index

### High-Value Reviews (10+ comments or significant architectural feedback)

| PR | File | Actionable | Nitpick | Key Topics |
|----|------|------------|---------|------------|
| origin-pr-76 | [JSON](origin-pr-76.json) | 4+ | 4+ | PEP 723, uv run, hook launcher, shebang strategy |
| origin-pr-84 | [JSON](origin-pr-84.json) | 15+ | - | Symlink installation, contributor workflow |
| origin-pr-83 | [JSON](origin-pr-83.json) | 7 | - | Session ID persistence, file-based state |
| origin-pr-19 | [JSON](origin-pr-19.json) | 6 | 4 | Cross-platform update script, deep merge, conflict analysis |

### Review Categories

**Security/Error Handling:**
- origin-pr-76: Resource leaks, bare except handling, partial executable paths
- fork-pr-11: Retry logic, error wrapping, transient failure handling

**Architecture/Patterns:**
- origin-pr-19: Deep merge strategy, conflict resolution, plugin merging
- origin-pr-84: Installation modes, symlink vs copy patterns

**Code Quality:**
- origin-pr-76: PEP 723 metadata consistency, Python version requirements
- origin-pr-17: sys.path injection normalization

## Statistics

Generated: 2026-01-15T10:05:00+01:00

### By Repository
- **Origin**: 27 PRs with reviews
- **Fork**: 10 PRs with reviews

### Total Reviews
113 reviews across 37 PRs

> **Note**: Update counts when adding new reviews: `ls origin-pr-*.json | wc -l` and `ls fork-pr-*.json | wc -l`

## JSON Field Reference

Each review JSON contains these key fields for comparison:

```json
{
  "commit_id": "abc123...",      // Exact commit SHA reviewed
  "submitted_at": "2026-01-...", // ISO timestamp
  "state": "COMMENTED",          // Review state
  "body": "**Actionable comments posted: N**\n...",  // Full markdown
  "html_url": "https://github.com/..."  // Direct link
}
```

### Extracting Metrics

```bash
# Count actionable comments in a review
jq -r '.[].body' origin-pr-76.json | grep -o "Actionable comments posted: [0-9]*"

# Get commit SHA
jq -r '.[].commit_id' origin-pr-76.json

# Get files reviewed
jq -r '.[].body' origin-pr-76.json | grep -o "Files selected for processing ([0-9]*)"
```
