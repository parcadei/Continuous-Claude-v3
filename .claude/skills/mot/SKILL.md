---
name: mot
description: System health check (MOT) for skills, agents, hooks, and memory
allowed-tools: [Read, Bash, Glob, Grep]
---

# MOT - System Health Check

Run comprehensive health checks on all Claude Code components.

## Usage

```
/mot              # Full audit (all categories)
/mot skills       # Just skills
/mot agents       # Just agents
/mot hooks        # Just hooks
/mot memory       # Just memory system
/mot --fix        # Auto-fix simple issues
/mot --quick      # P0 checks only (fast)
```

## Audit Process

### Phase 1: Skills Audit
```bash
# Count skills
echo "=== SKILLS ==="
SKILL_COUNT=$(find .claude/skills -name "SKILL.md" | wc -l | xargs)
echo "Found $SKILL_COUNT skill files"

# Check frontmatter parsing
FAIL=0
for skill in $(find .claude/skills -name "SKILL.md"); do
  if ! head -1 "$skill" | grep -q "^---$"; then
    echo "FAIL: No frontmatter: $skill"
    FAIL=$((FAIL+1))
  fi
done
echo "Frontmatter: $((SKILL_COUNT - FAIL)) pass, $FAIL fail"

# Check name matches directory
FAIL=0
for skill in $(find .claude/skills -name "SKILL.md"); do
  dir=$(basename $(dirname "$skill"))
  name=$(grep "^name:" "$skill" 2>/dev/null | head -1 | cut -d: -f2 | xargs)
  if [ -n "$name" ] && [ "$dir" != "$name" ]; then
    echo "FAIL: Name mismatch $dir vs $name"
    FAIL=$((FAIL+1))
  fi
done
echo "Name consistency: $((SKILL_COUNT - FAIL)) pass, $FAIL fail"
```

### Phase 2: Agents Audit
```bash
echo "=== AGENTS ==="
AGENT_COUNT=$(ls .claude/agents/*.md 2>/dev/null | wc -l | xargs)
echo "Found $AGENT_COUNT agent files"

# Check required fields
FAIL=0
for agent in .claude/agents/*.md; do
  [ -f "$agent" ] || continue

  # Check name field exists
  if ! grep -q "^name:" "$agent"; then
    echo "FAIL: Missing name: $agent"
    FAIL=$((FAIL+1))
    continue
  fi

  # Check model is valid
  model=$(grep "^model:" "$agent" | head -1 | cut -d: -f2 | xargs)
  case "$model" in
    opus|sonnet|haiku) ;;
    *) echo "FAIL: Invalid model '$model': $agent"; FAIL=$((FAIL+1)) ;;
  esac
done
echo "Agent validation: $((AGENT_COUNT - FAIL)) pass, $FAIL fail"

# Check for dangling references (agents that reference non-existent agents)
echo "Checking agent cross-references..."
for agent in .claude/agents/*.md; do
  [ -f "$agent" ] || continue
  # Find subagent_type references
  refs=$(grep -oE 'subagent_type[=:]["'\'']*([a-z-]+)' "$agent" 2>/dev/null | sed 's/.*["'\'']//' | sed 's/["'\'']$//')
  for ref in $refs; do
    if [ ! -f ".claude/agents/$ref.md" ]; then
      echo "WARN: $agent references non-existent agent: $ref"
    fi
  done
done
```

### Phase 3: Hooks Audit
```bash
echo "=== HOOKS ==="

# Check TypeScript source count
TS_COUNT=$(ls .claude/hooks/src/*.ts 2>/dev/null | wc -l | xargs)
echo "Found $TS_COUNT TypeScript source files"

# Check bundles exist
BUNDLE_COUNT=$(ls .claude/hooks/dist/*.mjs 2>/dev/null | wc -l | xargs)
echo "Found $BUNDLE_COUNT built bundles"

# Check shell wrappers are executable
FAIL=0
for sh in .claude/hooks/*.sh; do
  [ -f "$sh" ] || continue
  if [ ! -x "$sh" ]; then
    echo "FAIL: Not executable: $sh"
    FAIL=$((FAIL+1))
  fi
done
SH_COUNT=$(ls .claude/hooks/*.sh 2>/dev/null | wc -l | xargs)
echo "Shell wrappers: $((SH_COUNT - FAIL)) executable, $FAIL need chmod +x"

# Check hooks registered in settings.json exist
echo "Checking registered hooks..."
FAIL=0
# Extract hook commands from settings.json and verify files exist
grep -oE '"command":\s*"[^"]*\.sh"' .claude/settings.json 2>/dev/null | \
  sed 's/.*"\([^"]*\.sh\)".*/\1/' | \
  sed 's|\$CLAUDE_PROJECT_DIR|.claude|g' | \
  sed "s|\$HOME|$HOME|g" | \
  sort -u | while read hook; do
    # Resolve to actual path
    resolved=$(echo "$hook" | sed 's|^\./||')
    if [ ! -f "$resolved" ] && [ ! -f "./$resolved" ]; then
      echo "WARN: Registered hook not found: $hook"
    fi
  done
```

### Phase 4: Memory Audit
```bash
echo "=== MEMORY SYSTEM ==="

# Check DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
  echo "FAIL: DATABASE_URL not set"
else
  echo "PASS: DATABASE_URL is set"

  # Test connection
  if psql "$DATABASE_URL" -c "SELECT 1" > /dev/null 2>&1; then
    echo "PASS: PostgreSQL reachable"

    # Check pgvector
    if psql "$DATABASE_URL" -c "SELECT extname FROM pg_extension WHERE extname='vector'" 2>/dev/null | grep -q vector; then
      echo "PASS: pgvector extension installed"
    else
      echo "FAIL: pgvector extension not installed"
    fi

    # Check table exists
    if psql "$DATABASE_URL" -c "\d archival_memory" > /dev/null 2>&1; then
      echo "PASS: archival_memory table exists"

      # Count learnings
      COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM archival_memory" 2>/dev/null | xargs)
      echo "INFO: $COUNT learnings stored"
    else
      echo "FAIL: archival_memory table missing"
    fi
  else
    echo "FAIL: PostgreSQL not reachable"
  fi
fi

# Check Python dependencies
echo "Checking Python dependencies..."
(cd opc && uv run python -c "import psycopg2; import pgvector; import sentence_transformers" 2>/dev/null) && \
  echo "PASS: Python dependencies available" || \
  echo "WARN: Some Python dependencies missing"
```

### Phase 5: Cross-Reference Audit
```bash
echo "=== CROSS-REFERENCES ==="

# Check skills reference valid agents
echo "Checking skill → agent references..."
FAIL=0
for skill in $(find .claude/skills -name "SKILL.md"); do
  refs=$(grep -oE 'subagent_type[=:]["'\'']*([a-z-]+)' "$skill" 2>/dev/null | sed 's/.*["'\'']//' | sed 's/["'\'']$//')
  for ref in $refs; do
    if [ -n "$ref" ] && [ ! -f ".claude/agents/$ref.md" ]; then
      echo "FAIL: $skill references missing agent: $ref"
      FAIL=$((FAIL+1))
    fi
  done
done
echo "Skill→Agent refs: $FAIL broken"
```

## Auto-Fix (--fix flag)

If `--fix` is specified, automatically fix:

1. **Make shell wrappers executable**
   ```bash
   chmod +x .claude/hooks/*.sh
   ```

2. **Rebuild hooks if TypeScript newer than bundles**
   ```bash
   cd .claude/hooks && npm run build
   ```

3. **Create missing cache directories**
   ```bash
   mkdir -p .claude/cache/agents/{scout,kraken,oracle,spark}
   mkdir -p .claude/cache/mot
   ```

## Output Format

Write full report to `.claude/cache/mot/report-{timestamp}.md`:

```markdown
# MOT Health Report
Generated: {timestamp}

## Summary
| Category | Pass | Fail | Warn |
|----------|------|------|------|
| Skills   | 204  | 2    | 0    |
| Agents   | 47   | 1    | 3    |
| Hooks    | 58   | 2    | 1    |
| Memory   | 4    | 0    | 1    |
| X-Refs   | 0    | 0    | 2    |

## Issues Found

### P0 - Critical
- [FAIL] Hook build failed: tldr-context-inject.ts

### P1 - High
- [FAIL] Agent references missing: scot → scout (typo)

### P2 - Medium
- [WARN] 3 hooks need rebuild (dist older than src)

### P3 - Low
- [INFO] VOYAGE_API_KEY not set (using local BGE)
```

## Exit Codes

- `0` - All P0/P1 checks pass
- `1` - Any P0/P1 failure
- `2` - Only P2/P3 warnings

## Quick Mode (--quick)

Only run P0 checks:
1. Frontmatter parses
2. Hooks build
3. Shell wrappers executable
4. PostgreSQL reachable
