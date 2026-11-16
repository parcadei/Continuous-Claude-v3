# Quick Start

This runbook gets you from zero to a working local instance of the upgraded system. It also shows the minimal smoke tests for the key subsystems.

## Quick Start Flow

```
[Install] → [Start Agentica + Proxy] → [Run Flywheel] → [Run Memory] → [Run Analysis]
```

Smoke test ladder:

```
Flywheel (dry-run) → Temporal memory (record/summarize) → Braintrust analysis
```

## 1) Install dependencies

```bash
uv sync
```

If you need optional extras:
```bash
uv sync --extra agentica
```

Optional tooling:
```bash
uv pip install tiktoken jq
```

## 2) Start Agentica + Claude proxy

Terminal 1 (proxy):
```bash
uv run python scripts/agentica_patterns/claude_proxy.py --port 8080
```

Terminal 2 (agentica server):
```bash
cd workspace/agentica-research/agentica-server
INFERENCE_ENDPOINT_URL=http://localhost:8080/v1/chat/completions uv run agentica-server --port 2345
```

Optional watcher (agent logs):
```bash
uv run python scripts/agentica_patterns/watch_agents.py --watch --logs
```

### Environment variables (common)

- `S_M_BASE_URL` → Agentica server base URL (e.g., `http://localhost:2345`)
- `BRAINTRUST_API_KEY` → Braintrust queries (if using backfill or analysis)
- `RAGIE_API_KEY` → Ragie (if doing research or book retrieval)

## 3) Run the flywheel (skill conversion)

Dry-run (no writes):
```bash
S_M_BASE_URL=http://localhost:2345 \
  uv run python scripts/run_flywheel.py --skill .claude/skills/commit \
  --prompt "commit my changes" --dry-run
```

Persist (writes updated SKILL.md):
```bash
S_M_BASE_URL=http://localhost:2345 \
  uv run python scripts/run_flywheel.py --skill .claude/skills/_sandbox/test-skill \
  --prompt "deploy to aws" --persist
```

Flywheel loop (concept):
```
Prose skill → infer params → verify → diff → persist → learn
```

## 4) Run temporal memory

Record facts:
```bash
uv run python -m scripts.temporal_memory.cli record \
  --session quickstart --turn 1 --facts '{"phase":"init","db":"sqlite"}'
```

Summarize:
```bash
uv run python -m scripts.temporal_memory.cli summarize --session quickstart --budget 200
```

Temporal summary output structure:
```
Open Questions | Invariants | Current State | Pending Goals | Transitions
```

## 5) Run Braintrust analysis

```bash
uv run python -m runtime.harness scripts/braintrust_analyze.py --last-session
```

## 6) Validate a v6.0 skill

```bash
uv run python scripts/validate_skill_v6.py .claude/skills/braintrust-analyze/SKILL.v6.md
```

## 7) Optional: Test jq-in-Python transforms

```bash
uv run python workspace/test_jq_tokens.py
```

## What this proves

- Skill routing and clarification work end-to-end.
- The flywheel can infer and persist typed parameters.
- Temporal memory can summarize and hand off state.
- Braintrust analysis can run from CLI.
- v6.0 skills validate via schema.

## Next reading

- Skills: `../02-Architecture/Skills-System.md`
- Memory: `../02-Architecture/Memory-System.md`
- Experiments: `../04-Experiments/Experiments-and-Metrics.md`
