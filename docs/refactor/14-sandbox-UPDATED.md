# Sandbox Environment

**Reference:** See [00-architecture-decisions.md](./00-architecture-decisions.md) for authoritative Round 3 decisions (113+ total decisions).

## Overview

Isolated execution environment for agent development, testing, and experimentation without affecting production workflows.

## Goals

1. **Safe Experimentation**: Test new agents/hooks/skills without breaking production
2. **Reproducible Testing**: Consistent environment across development cycles
3. **Easy Reset**: Quick cleanup between experiments
4. **Production Parity**: Similar enough to catch real issues

## Architecture

### Sandbox Locations

```
.claude/sandbox/
  agents/         # Test agent definitions
  hooks/          # Test hooks
  skills/         # Test skills
  cache/          # Isolated cache (auto-cleaned)
  settings.json   # Sandbox-specific settings
  .gitignore      # Prevent accidental commits
```

### Activation Pattern

```bash
# Enter sandbox mode
export CLAUDE_SANDBOX=1
export CLAUDE_PROJECT_DIR=$PWD/.claude/sandbox

# Run Claude with sandbox config
claude --project .claude/sandbox
```

### Settings Override

Sandbox `settings.json` inherits from production but overrides:
- Cache paths → `.claude/sandbox/cache/`
- Logging → verbose (DEBUG level)
- Agent discovery → `.claude/sandbox/agents/`

## Workflow Integration

### /onboard Workflow (Sandbox as Learning Environment)

When onboarding new users via `/onboard`:

1. **Initial Setup**: Creates sandbox with core 18 agents
   ```
   .claude/sandbox/
     agents/       # All 18 core agents for tutorial
     skills/       # Core skills (continuity, commit, etc.)
     hooks/        # Essential hooks (session-start, etc.)
   ```

2. **Tutorial Mode**: Safe environment for learning
   - User experiments with agent orchestration
   - Practice Maestro → Routing → Lead Agent pattern
   - No production pollution from learning mistakes

3. **Graduation**: After tutorial completion
   - User promoted to production environment
   - Sandbox remains for future experimentation

### /plan Workflow (Sandbox for Planning Research)

When creating plans via `/plan`:

1. **Research Phase**: Sandbox isolation for exploration
   - Scout/Surveyor agents analyze codebase
   - Research artifacts stay in sandbox
   - Multiple plan iterations don't pollute production

2. **Plan Validation**: Test feasibility in sandbox
   - Spawn test agents to validate assumptions
   - Check for blockers before committing to plan
   - Prototype key components if needed

3. **Plan Finalization**: Approved plan moves to production
   - Final plan → `thoughts/shared/plans/`
   - Sandbox research artifacts archived or discarded

### /implement Workflow (Sandbox for Prototyping)

When implementing via `/implement`:

1. **Prototype Phase**: Initial implementation in sandbox
   - Test agent coordination patterns
   - Validate tool usage sequences
   - Debug without production side effects

2. **Production Run**: Validated implementation
   - Clean production context (no prototype debris)
   - Clear success criteria from plan
   - Production ledger tracking

3. **Rollback Safety**: Sandbox preserves working state
   - Compare production vs sandbox implementations
   - Debug production failures against sandbox baseline

### /review Workflow (Sandbox for Review Iterations)

When reviewing via `/review`:

1. **Review Phase**: Isolated review environment
   - Critic/Judge agents generate feedback
   - Multiple review rounds stay in sandbox
   - Review artifacts don't pollute production cache

2. **Production Integration**: Approved changes
   - Review outcomes → production ledger
   - Review artifacts → `docs/archive/reviews/`
   - Production state updated with review decisions

## Routing Philosophy Integration

Sandbox supports the **Maestro → Routing → Lead Agent** pattern:

1. **Maestro** (main conversation): Decides to use sandbox for prototyping
2. **Routing Layer**: Routes to appropriate sandbox agents
3. **Lead Agent**: Executes in sandbox with keyword + Haiku fallback

Example flow:
```
User: "Can you prototype the new auth middleware?"
  ↓
Maestro: "Use sandbox for prototyping, route to Architect"
  ↓
Routing: "Architect agent (keyword: design patterns) or Haiku fallback"
  ↓
Architect (in sandbox): Prototypes design, safe to iterate
```

## Use Cases

### 1. Agent Development

**Scenario**: Testing new agent definition

```bash
# Create agent in sandbox
cat > .claude/sandbox/agents/test-agent.md << 'EOF'
---
name: test-agent
description: Experimental agent
---
# Test Agent
[agent prompt]
EOF

# Test with sandbox mode
CLAUDE_SANDBOX=1 claude
> Task(subagent_type="test-agent", ...)
```

### 2. Hook Development

**Scenario**: Testing pre-tool-use hook

```bash
# Write hook in sandbox
cat > .claude/sandbox/hooks/test-hook.sh << 'EOF'
#!/bin/bash
echo '{"result": "block", "message": "Test block"}'
EOF

# Register in sandbox settings
# Test behavior without affecting production
```

### 3. Skill Iteration

**Scenario**: Refining skill triggers

```bash
# Copy skill to sandbox
cp .claude/skills/my-skill/SKILL.md .claude/sandbox/skills/

# Modify triggers
# Test with various inputs
# Once validated, copy back to production
```

## Workflow Commands

### Setup Sandbox

```bash
# One-time setup
.claude/scripts/setup-sandbox.sh

# Creates:
# - .claude/sandbox/ structure
# - Default settings.json
# - Copies core 18 agents + skills + hooks
```

### Enter Sandbox

```bash
# Shell function (add to ~/.bashrc)
claude-sandbox() {
  export CLAUDE_SANDBOX=1
  export CLAUDE_PROJECT_DIR=$PWD/.claude/sandbox
  claude "$@"
}

# Usage
claude-sandbox
```

### Reset Sandbox

```bash
# Clean cache only (keep definitions)
rm -rf .claude/sandbox/cache/

# Full reset (restore to defaults)
.claude/scripts/reset-sandbox.sh
```

### Promote to Production

```bash
# Copy tested agent to production
cp .claude/sandbox/agents/my-agent.md .claude/agents/

# Update production settings if needed
```

## Safety Guardrails

### 1. Explicit Activation

Sandbox NEVER activates automatically:
- Requires `CLAUDE_SANDBOX=1` env var
- CLI must explicitly point to sandbox
- No accidental production pollution

### 2. Visual Indicators

When in sandbox mode:
- CLI prompt shows `[SANDBOX]`
- Logs prefix with `[SANDBOX]`
- StatusLine shows sandbox indicator

### 3. Data Isolation

Sandbox cannot:
- Write to production cache
- Modify production ledgers
- Pollute production agent state

### 4. .gitignore Protection

Sandbox `.gitignore`:
```
cache/
*.log
*.tmp
```

Prevents committing sandbox artifacts.

## Testing Strategy

### Unit Tests

Test sandbox activation:
```typescript
test('sandbox mode isolates cache', () => {
  process.env.CLAUDE_SANDBOX = '1';
  const cache = getCachePath();
  expect(cache).toContain('.claude/sandbox/cache');
});
```

### Integration Tests

Test sandbox workflow:
```bash
# test_sandbox_workflow.sh
export CLAUDE_SANDBOX=1
claude --project .claude/sandbox --eval "test command"
# Verify no production artifacts created
[ ! -f .claude/cache/test.log ] || exit 1
```

## Monitoring

### Sandbox Metrics

Track:
- Experiments run in sandbox vs production
- Sandbox → production promotion rate
- Sandbox cache size over time

### Alerts

Warn if:
- Sandbox cache exceeds 1GB (cleanup needed)
- Sandbox definitions diverge from production >7 days
- Sandbox mode accidentally used in CI/CD

## Migration Path

### Phase 1: Basic Sandbox
- Directory structure
- Settings override
- Manual activation

### Phase 2: Workflow Integration
- `/onboard` tutorial mode with 18 core agents
- `/plan` research isolation
- `/implement` prototyping support
- `/review` review iteration isolation

### Phase 3: Automation
- CLI commands (`claude-sandbox`, `promote-agent`)
- Automatic cleanup (cache TTL)
- Sandbox metrics dashboard

## Known Limitations

1. **Not a Full VM**: Sandbox shares system resources, not fully isolated
2. **Manual Promotion**: No automatic sync production ↔ sandbox
3. **No Version Control**: Sandbox state is ephemeral (by design)

## Future Enhancements

1. **Snapshot/Restore**: Save sandbox state for reproducible experiments
2. **Diff Tool**: Compare sandbox vs production agents/hooks/skills
3. **Template Library**: Pre-configured sandbox setups for common tasks
4. **Multi-Sandbox**: Support multiple named sandboxes (dev/staging/test)

## Related Decisions

From [00-architecture-decisions.md](./00-architecture-decisions.md):

- **Workflow Integration**: /onboard, /plan, /implement, /review use sandbox for isolation
- **18 Core Agents**: Sandbox includes all 18 for tutorial/testing (Maestro, Scout, Architect, etc.)
- **SpawnQueue**: Sandbox agents use same SpawnQueue infrastructure as production
- **Routing Philosophy**: Maestro → Routing → Lead Agent pattern applies in sandbox
- **Keyword + Haiku Fallback**: Sandbox routing supports both keyword matching and Haiku fallback
- **Archive Pattern**: Sandbox artifacts → `docs/archive/sandbox-experiments/`

## References

- [Agent Orchestration](./05-agent-orchestration.md) - Agent spawning patterns
- [Testing Strategy](./21-testing-strategy.md) - Overall testing approach
- [Setup Wizard](./11-setup-wizard.md) - Initial sandbox creation
- [Temporal Archival](./20-temporal-archival.md) - Archiving sandbox experiments
- [Architecture Map](./01-architecture-map.md) - Maestro → Routing → Lead Agent flow
