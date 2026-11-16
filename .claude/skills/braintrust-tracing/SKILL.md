---
name: braintrust-tracing
description: Braintrust tracing for Claude Code - hook architecture, sub-agent correlation, debugging
---

# Braintrust Tracing for Claude Code

Comprehensive guide to tracing Claude Code sessions in Braintrust, including sub-agent correlation.

## Architecture Overview

```
                         PARENT SESSION
                    +---------------------+
                    |  SessionStart       |
                    |  (creates root)     |
                    +----------+----------+
                               |
                    +----------v----------+
                    |  UserPromptSubmit   |
                    |  (creates Turn)     |
                    +----------+----------+
                               |
          +--------------------+--------------------+
          |                    |                    |
+---------v--------+  +--------v--------+  +--------v--------+
| PostToolUse      |  | PostToolUse     |  | PreToolUse      |
| (Read span)      |  | (Edit span)     |  | (Task - inject) |
+------------------+  +-----------------+  +--------+--------+
                                                    |
                                         +----------v----------+
                                         |   SUB-AGENT         |
                                         |   SessionStart      |
                                         |   (NEW root_span_id)|
                                         +----------+----------+
                                                    |
                                         +----------v----------+
                                         |   SubagentStop      |
                                         |   (has session_id)  |
                                         +---------------------+
```

## Hook Event Flow

| Hook | Trigger | Creates | Key Fields |
|------|---------|---------|------------|
| **SessionStart** | Session begins | Root span | `session_id`, `root_span_id` |
| **UserPromptSubmit** | User sends prompt | Turn span | `prompt`, `turn_number` |
| **PreToolUse** | Before tool runs | (modifies Task prompts) | `tool_input.prompt` |
| **PostToolUse** | After tool runs | Tool span | `tool_name`, `input`, `output` |
| **Stop** | Turn completes | LLM spans | `model`, `tokens`, `tool_calls` |
| **SubagentStop** | Sub-agent finishes | (no span) | `session_id` of sub-agent |
| **SessionEnd** | Session ends | (finalizes root) | `turn_count`, `tool_count` |

## Trace Hierarchy

```
Session (task span) - root_span_id = session_id
|
+-- Turn 1 (task span)
|   |
|   +-- claude-sonnet (llm span) - model call with tool_use
|   +-- Read (tool span)
|   +-- Edit (tool span)
|   +-- claude-sonnet (llm span) - response after tools
|
+-- Turn 2 (task span)
|   |
|   +-- claude-sonnet (llm span)
|   +-- Task (tool span) -----> [Sub-agent session - SEPARATE trace]
|   +-- claude-sonnet (llm span)
|
+-- Turn 3 ...
```

## Sub-Agent Tracing: What Works and What Doesn't

### What Doesn't Work

**SessionStart doesn't receive the Task prompt.**

We tried injecting trace context into Task prompts via PreToolUse:

```bash
# PreToolUse hook injects:
[BRAINTRUST_TRACE_CONTEXT]
{"root_span_id": "abc", "parent_span_id": "xyz", "project_id": "123"}
[/BRAINTRUST_TRACE_CONTEXT]
```

But SessionStart only receives session metadata, not the modified prompt. The injected context is lost.

### What DOES Work

**Task spans in parent session contain everything:**
- `agentId` - identifier for the sub-agent run
- `totalTokens`, `totalToolUseCount` - metrics
- `content` - full agent response/summary
- `tool_input.prompt` - original task prompt
- `tool_input.subagent_type` - agent type (e.g., "research-agent")

**SubagentStop hook receives the sub-agent's `session_id`:**
- This equals the sub-agent's orphaned trace `root_span_id`
- Allows correlation between parent Task span and child trace

### The Correlation Pattern

**Current state:** Sub-agents create orphaned traces (new `root_span_id`).

**Correlation method:**
1. Query parent session's Task spans for agent metadata
2. Match `agentId` or timing with orphaned traces
3. Sub-agent's `session_id` = its trace's `root_span_id`

**Future solution (not yet implemented):**
```
SubagentStop fires -> writes session_id to temp file
PostToolUse (Task) -> reads temp file -> adds child_session_id to Task span metadata
```

This would link: `Task.agentId` + `Task.child_session_id` -> orphaned trace `root_span_id`

## State Management

### Per-Session State Files

```
~/.claude/state/braintrust_sessions/
  {session_id}.json       # Per-session state
```

Each session file contains:
```json
{
  "root_span_id": "abc-123",
  "project_id": "proj-456",
  "turn_count": 5,
  "tool_count": 23,
  "current_turn_span_id": "turn-789",
  "current_turn_start": 1703456789,
  "started": "2025-12-24T10:00:00.000Z",
  "is_subagent": false
}
```

### Global State
```
~/.claude/state/braintrust_global.json   # Cached project_id
~/.claude/state/braintrust_hook.log      # Debug log
```

## Debugging Commands

### Check if Tracing is Active
```bash
# View hook logs in real-time
tail -f ~/.claude/state/braintrust_hook.log

# Check if session has state
cat ~/.claude/state/braintrust_sessions/*.json | jq -s '.'

# Verify environment
echo "TRACE_TO_BRAINTRUST=$TRACE_TO_BRAINTRUST"
echo "BRAINTRUST_API_KEY=${BRAINTRUST_API_KEY:+set}"
```

### Query Braintrust Directly
```bash
# List recent sessions
uv run python -m runtime.harness scripts/braintrust_analyze.py --sessions 5

# Analyze last session
uv run python -m runtime.harness scripts/braintrust_analyze.py --last-session

# Replay specific session
uv run python -m runtime.harness scripts/braintrust_analyze.py --replay <session-id>

# Find sub-agent traces (orphaned roots)
uv run python -m runtime.harness scripts/braintrust_analyze.py --agent-stats
```

### Debug Hook Execution
```bash
# Enable verbose logging
export BRAINTRUST_CC_DEBUG=true

# Test hooks manually
echo '{"session_id":"test-123","type":"resume"}' | \
  bash .claude/plugins/braintrust-tracing/hooks/session_start.sh

# Test PreToolUse (Task injection)
echo '{"session_id":"test-123","tool_name":"Task","tool_input":{"prompt":"test"}}' | \
  bash .claude/plugins/braintrust-tracing/hooks/pre_tool_use.sh
```

### Troubleshooting Checklist

1. **No traces appearing:**
   - Check `TRACE_TO_BRAINTRUST=true` in `.claude/settings.local.json`
   - Verify API key: `echo $BRAINTRUST_API_KEY`
   - Check logs: `tail -20 ~/.claude/state/braintrust_hook.log`

2. **Sub-agents not linking:**
   - This is expected - sub-agents create orphaned traces
   - Use `--agent-stats` to find agent activity
   - Correlate via timing or `agentId` in parent Task span

3. **Missing spans:**
   - Check `current_turn_span_id` in session state
   - Ensure Stop hook runs (turn finalization)
   - Look for "Failed to create" errors in log

4. **State corruption:**
   - Remove session state: `rm ~/.claude/state/braintrust_sessions/*.json`
   - Clear global cache: `rm ~/.claude/state/braintrust_global.json`

## Key Files

| File | Purpose |
|------|---------|
| `.claude/plugins/braintrust-tracing/hooks/common.sh` | Shared utilities, API, state management |
| `.claude/plugins/braintrust-tracing/hooks/session_start.sh` | Creates root span, handles sub-agent context |
| `.claude/plugins/braintrust-tracing/hooks/user_prompt_submit.sh` | Creates Turn spans per user message |
| `.claude/plugins/braintrust-tracing/hooks/pre_tool_use.sh` | Injects trace context into Task prompts |
| `.claude/plugins/braintrust-tracing/hooks/post_tool_use.sh` | Creates tool spans, captures agent/skill metadata |
| `.claude/plugins/braintrust-tracing/hooks/stop_hook.sh` | Creates LLM spans, finalizes Turns |
| `.claude/plugins/braintrust-tracing/hooks/session_end.sh` | Finalizes session, triggers learning extraction |
| `scripts/braintrust_analyze.py` | Query and analyze traced sessions |
| `~/.claude/state/braintrust_sessions/` | Per-session state files |
| `~/.claude/state/braintrust_hook.log` | Debug log |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TRACE_TO_BRAINTRUST` | Yes | - | Set to `"true"` to enable |
| `BRAINTRUST_API_KEY` | Yes | - | API key for Braintrust |
| `BRAINTRUST_CC_PROJECT` | No | `claude-code` | Project name |
| `BRAINTRUST_CC_DEBUG` | No | `false` | Verbose logging |
| `BRAINTRUST_API_URL` | No | `https://api.braintrust.dev` | API endpoint |

## Session Learnings

### What We Learned About Sub-Agent Tracing (Dec 2025)

**Attempted:** Inject trace context via PreToolUse into Task prompts.

**Result:** Failed - SessionStart only receives session metadata, not the prompt.

**Discovery:** Task spans already contain rich sub-agent data:
- `metadata.agent_type` - agent type from `subagent_type`
- `metadata.skill_name` - skill from Skill tool
- `tool_input` - full prompt sent to agent
- `tool_output` - agent response

**Current correlation path:**
1. Parent session Task span has `agentId` and timing
2. Sub-agent creates orphaned trace with `root_span_id = session_id`
3. SubagentStop provides the sub-agent's `session_id`
4. Manual correlation: match timing or use `session_id` link

**Future work:** Write `child_session_id` to Task span metadata from PostToolUse after SubagentStop.

## What We Learned About Sub-Agent Correlation

### The Problem

- Sub-agents spawned via Task tool create orphaned Braintrust traces
- Parent session has Task spans with `agentId`, sub-agent has separate `session_id`
- No built-in link between them

### What DOESN'T Work

**1. Prompt injection via PreToolUse**

SessionStart hook only receives session metadata (`session_id`, `type`, `cwd`), NOT the prompt. Injected trace context is never seen.

The hook receives:
```json
{
  "session_id": "...",
  "type": "start|resume|compact|clear",
  "cwd": "...",
  "env": {...}
}
```

No prompt field exists - context injection is impossible at SessionStart.

**2. SubagentStop → PostToolUse file handoff**

Race condition. These are independent async hooks with no timing guarantees:
- SubagentStop fires when sub-agent session ends
- PostToolUse (Task) fires when Task tool completes
- No ordering guarantee between them
- Writing to a correlation file creates a race

**3. PreToolUse correlation files**

SessionStart can't access the `task_span_id` because it has no context about which Task spawned it. PreToolUse modifies prompts but doesn't create a reliably accessible state file that SessionStart can find.

### What DOES Work

**Post-hoc matching for dataset building:**

Parent session Task spans contain:
- `agentId` - identifier for the sub-agent run
- `totalTokens`, `totalToolUseCount` - aggregated metrics
- `content` - full agent response/summary
- `tool_input.prompt` - original task prompt
- `tool_input.subagent_type` - agent type (e.g., "research-agent")
- Start/end timestamps

Sub-agent sessions contain:
- `session_id` (equals orphaned trace `root_span_id`)
- Start/end timestamps
- All internal spans and tool calls

**Correlation strategy:**
1. Export parent session traces (query parent `root_span_id`)
2. Export sub-agent traces (query all sessions created within parent's time window)
3. Match by:
   - Timing: Task span end ≈ sub-agent session end
   - Metadata: `subagent_type` from Task prompt
   - IDs: SubagentStop hook provides `session_id` (can be captured and logged)

### Architecture Insight

SessionStart input is intentionally minimal - it contains no prompt or tool context:

```typescript
interface SessionStartInput {
  session_id: string;
  type: "start" | "resume" | "compact" | "clear";
  cwd: string;
  env: { [key: string]: string };
  // NO: prompt, tool_context, task_span_id, parent_span_id
}
```

This design boundary prevents real-time correlation at hook time.

### Recommendation

For building agent run datasets with sub-agent correlation:

1. **In-session logging:** Capture SubagentStop `session_id` in logs or state
2. **Post-session export:** Query Braintrust API for parent and sub-agent traces
3. **Offline correlation:** Match traces by timing and metadata in a script
4. **Don't try real-time linking:** Hooks don't have necessary context

Example script pattern:
```bash
# 1. Export parent session
braintrust_analyze.py --replay <parent-session-id> > parent_traces.json

# 2. Query for orphaned sub-agent traces (those created during parent's time window)
braintrust_analyze.py --agent-stats > all_agent_traces.json

# 3. Correlate in Python:
#    - Parent Task spans -> agentId, timestamps, subagent_type
#    - Orphaned traces -> root_span_id, timestamps
#    - Match by timing and type
```

This approach is reliable, testable, and doesn't require hooks to maintain implicit state.
