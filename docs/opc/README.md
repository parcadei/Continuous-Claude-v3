# OPC (Opinionated/Overpowered Claude) Documentation

This directory contains the authoritative documentation for OPC v3.

## Quick Start

```bash
# Run Claude in isolated mode (won't conflict with your global setup)
CLAUDE_CONFIG_DIR=/tmp/opc-dev claude
```

See [ISOLATED_SETUP.md](./ISOLATED_SETUP.md) for full details.

## Documentation Structure

```
docs/opc/
├── README.md                    # This file
├── ISOLATED_SETUP.md            # How to run Claude in isolation
├── spec/
│   ├── 00-architecture.md       # Master architecture decisions (113+)
│   ├── 01-agents.md             # 18 agent roster (5 leads, 13 workers)
│   ├── 02-patterns.md           # 11 orchestration patterns
│   ├── 03-routing.md            # Keyword + Haiku fallback
│   ├── 04-erotetic.md           # Erotetic logic (gates BLOCK)
│   ├── 05-spawn.md              # SpawnQueue + SpawnCoordinator
│   ├── 06-handoff.md            # Extended HandoffState
│   ├── 07-protocol.md           # MESSAGE_PROTOCOL.md
│   ├── 08-lifecycle.md          # Agent start/stop, cleanup
│   ├── 09-security.md           # Trust, sandboxing, audit
│   └── 10-deployment.md         # Docker, setup wizard
└── guides/
    ├── EROTETIC_THEORY.md       # Formal IEL foundations
    ├── EROTETIC_BLOG.md         # "Why questions beat guessing"
    └── EROTETIC_GUIDE.md        # Practical usage
```

## Master Spec

All 113+ decisions are documented in:
- **Full spec:** `~/.claude/plans/concurrent-juggling-cook.md`
- **Architecture ref:** `docs/refactor/00-architecture-decisions.md`

## Key Files to Copy

When building OPC, copy these from this repo:
```
.claude/agents/           # 18 agent definitions
.claude/skills/           # Skill library
.claude/hooks/            # Hook implementations
scripts/agentica_patterns/ # 11 patterns
docker-compose.yml        # Backend services
```

## Philosophy

> "The goal isn't to do work inside the chat window; it's to orchestrate work."

- No small changes - everything is a workflow
- Erotetic gates BLOCK until unknowns resolved
- Workflows compose: /onboard → /plan → /implement → /review
