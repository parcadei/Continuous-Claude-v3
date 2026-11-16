# Hooks and Skills for Agent Orchestration

> **Reference**: See `00-architecture-decisions.md` for authoritative routing and agent decisions.

## Executive Summary

The codebase already has a sophisticated hook and skill system for agent orchestration routing. The infrastructure includes:
- **Agent routing layer**: Keyword matching + LLM fallback (NOT erotetic-based)
- **task-router.ts**: PreToolUse hook that intercepts Task calls and routes to Agentica patterns
- **Pattern-aware SubagentStart/Stop hooks**: Route based on PATTERN_TYPE env var (only for Leads spawning Workers)
- **11 pattern modules**: Fully implemented handlers for swarm, jury, pipeline, hierarchical, etc.
- **skill-rules.json**: Trigger system for skill activation (but NO pattern-specific triggers yet)

The gap: **skill-rules.json lacks triggers for pattern keywords** ("swarm", "jury", "hierarchical"). Adding these would enable natural language routing.

---

## Layer 0: Agent Routing

> **Per architecture decision**: Routing uses keyword matching + LLM fallback, NOT erotetic logic.

Agent routing happens BEFORE UserPromptSubmit hooks. This is the first decision point.

### Routing Table (from 00-architecture-decisions.md)

| Activity | Trigger Words | Agent |
|----------|---------------|-------|
| implement, large | implement, build, create, develop | Kraken |
| implement, small | fix, patch, tweak | Spark |
| document | document, write docs, explain | Scribe |
| debug | debug, investigate, trace | Sleuth |
| security | security, vulnerability, audit | Aegis |
| performance | performance, optimize, profile | Profiler |
| test, unit | unit test, test function | Arbiter |
| test, e2e | e2e test, integration test | Atlas |
| research, external | research, look up, find docs | Oracle |
| research, internal | explore codebase, find code | Scout |
| research, repo | analyze repo, understand project | Pathfinder |
| plan, feature | plan feature, design, architect | Architect |
| plan, refactor | plan refactor, migrate, restructure | Phoenix |
| review, build | review plan, check design | Sentinel |
| review, change | review refactor, validate migration | Warden |
| session | session analysis, what happened | Chronicler |
| deploy | deploy, release, publish | Herald |

### Routing Engine

```
User Input
    |
    v
1. Keyword Match (instant, covers 80% of cases)
    |
    +--> Match found --> Route to agent
    |
    v
2. LLM Classification (~500ms fallback)
    |
    +--> Route to agent
```

**NOT erotetic**: Erotetic logic is for parameter extraction AFTER routing, not for selecting which agent handles the task.

---

## Current Hook Inventory

### Registered Hooks (from .claude/settings.json)

| Hook | Event | Command | Purpose | Agent Orchestration? |
|------|-------|---------|---------|---------------------|
| pre-compact-continuity.sh | PreCompact | Global | Save state before compaction | No |
| session_start.sh (braintrust) | SessionStart | Global | Tracing init | No |
| session-start-continuity.sh | SessionStart (resume/compact/clear) | Global | Load ledger on resume | No |
| skill-activation-prompt.sh | UserPromptSubmit | Global | Inject skill suggestions | **Yes** (skill triggers) |
| user_prompt_submit.sh (braintrust) | UserPromptSubmit | Global | Tracing | No |
| typescript-preflight.sh | PostToolUse (Edit/Write) | Global | Type checking | No |
| handoff-index.sh | PostToolUse (Write) | Global | Index handoffs | No |
| post-tool-use-tracker.sh | PostToolUse (Edit/MultiEdit/Write/Bash) | Global | Track tool usage | No |
| post_tool_use.sh (braintrust) | PostToolUse (*) | Global | Tracing | No |
| stop_hook.sh (braintrust) | Stop | Global | Tracing | No |
| **subagent-start.sh** | SubagentStart | **Project** | Pattern-aware agent routing (Leads only) | **YES** |
| **subagent-stop.sh** | SubagentStop | **Project** | Pattern-aware completion (Leads only) | **YES** |
| session-end-cleanup.sh | SessionEnd | Global | Cleanup | No |
| session-outcome.sh | SessionEnd | Global | Record outcome | No |
| session_end.sh (braintrust) | SessionEnd | Global | Tracing | No |

### Missing Hooks (exist in .claude/hooks/ but NOT registered in settings.json)

| Hook | File | Purpose | Should Register? |
|------|------|---------|------------------|
| **task-router.sh** | .claude/hooks/task-router.sh | Intercept Task tool for pattern routing | **YES - critical** |
| composition-gate.sh | .claude/hooks/composition-gate.sh | Validate pattern algebra | YES |
| resource-gate.sh | .claude/hooks/resource-gate.sh | Check system resources | YES |
| erotetic-clarification.sh | .claude/hooks/erotetic-clarification.sh | Block when unknowns exist (keyword-based, not Z3) | YES |
| stop-coordinator.sh | .claude/hooks/stop-coordinator.sh | Coordinate stop across patterns | YES |
| skill-router.sh | .claude/hooks/skill-router.sh | Route to skills | Maybe (may be superseded) |

---

## Pattern Modules Analysis

Located at: `.claude/hooks/src/patterns/`

| Pattern Module | SubagentStart | SubagentStop | PreToolUse | PostToolUse | Stop |
|----------------|---------------|--------------|------------|-------------|------|
| swarm.ts | Logs join | Auto-broadcasts "done", checks quorum | Injects broadcasts from others | Tracks Task spawn | Blocks until all complete |
| jury.ts | Injects isolation context | Marks vote complete | Blocks Read in strict mode | No-op | Waits for all jurors |
| hierarchical.ts | Context injection | Notifies coordinator | - | - | - |
| pipeline.ts | Stage context | Stage completion | - | - | - |
| generator-critic.ts | Role context | Iteration tracking | - | - | - |
| map-reduce.ts | Mapper/reducer context | Mapper completion | - | - | - |
| blackboard.ts | - | - | - | - | - |
| circuit-breaker.ts | Circuit state | Primary/fallback tracking | - | - | - |
| chain-of-responsibility.ts | Priority context | Handler completion | - | - | - |
| adversarial.ts | Role context | Round completion | - | - | - |
| event-driven.ts | Pub/sub context | Role completion | - | - | - |

### Pattern Detection

From `.claude/hooks/src/shared/pattern-router.ts`:

```typescript
export const SUPPORTED_PATTERNS = [
  'swarm', 'jury', 'pipeline', 'generator_critic',
  'hierarchical', 'map_reduce', 'blackboard',
  'circuit_breaker', 'chain_of_responsibility',
  'adversarial', 'event_driven',
] as const;

export function detectPattern(): string | null {
  return process.env.PATTERN_TYPE || null;
}
```

Pattern is detected from `PATTERN_TYPE` environment variable, set by the orchestrator.

---

## Skill Rules Analysis

### Current Structure

From `.claude/skills/skill-rules.json`:

```json
{
  "version": "1.0",
  "skills": {
    "compound-learnings": { "promptTriggers": { "keywords": [...], "intentPatterns": [...] } },
    "implement_plan": { ... },
    ...
  },
  "agents": {
    "rp-explorer": { ... },
    "research-agent": { ... },
    "plan-agent": { ... },
    ...
  }
}
```

### Missing Pattern Triggers

**The skill-rules.json has NO triggers for orchestration patterns.** This is a gap.

Proposed additions:

```json
{
  "agentica-swarm": {
    "type": "orchestration",
    "enforcement": "suggest",
    "priority": "high",
    "description": "Parallel exploration with multiple perspectives (research, analysis)",
    "promptTriggers": {
      "keywords": [
        "swarm", "run swarm", "spawn swarm",
        "explore from multiple angles", "multiple perspectives",
        "parallel exploration", "research in parallel"
      ],
      "intentPatterns": [
        "(run|spawn|use).*swarm",
        "(parallel|multiple).*?(research|explore|analyze)",
        "(explore|investigate).*?(angles|perspectives)"
      ]
    }
  },
  "agentica-jury": {
    "type": "orchestration",
    "enforcement": "suggest",
    "priority": "high",
    "description": "Independent voting for high-stakes validation",
    "promptTriggers": {
      "keywords": [
        "jury", "jury pattern", "run jury",
        "independent vote", "consensus", "validation panel",
        "high stakes decision", "multiple validators"
      ],
      "intentPatterns": [
        "(run|use|spawn).*jury",
        "(independent|multiple).*?vote",
        "(validate|verify).*?(consensus|panel)",
        "high.*?stakes.*?(decision|validation)"
      ]
    }
  },
  "agentica-hierarchical": {
    "type": "orchestration",
    "enforcement": "suggest",
    "priority": "high",
    "description": "Coordinator-specialist hierarchy for implementation tasks",
    "promptTriggers": {
      "keywords": [
        "hierarchical", "hierarchical pattern",
        "coordinator", "specialists",
        "break down task", "delegate to specialists"
      ],
      "intentPatterns": [
        "(run|use|spawn).*hierarchical",
        "coordinator.*specialist",
        "(break|divide).*?(task|work).*?(delegate|specialists)"
      ]
    }
  }
}
```

### Existing Related Skills

| Skill | Location | Relevance |
|-------|----------|-----------|
| agentica-spawn | .claude/skills/agentica-spawn/SKILL.md | Pattern execution guide |
| agentica-sdk | .claude/skills/agentica-sdk/SKILL.md | SDK reference |
| agentica-infrastructure | .claude/skills/agentica-infrastructure/SKILL.md | Infrastructure APIs |
| implement_plan | .claude/skills/implement_plan/SKILL.md | Suggests orchestration |
| plan-agent (agent) | .claude/agents/ | Creates plans |

---

## Task Router Deep Dive

### How task-router.ts Works

File: `.claude/hooks/src/task-router.ts`

```
User: "Research authentication patterns"
                    │
                    ▼
    ┌─────────────────────────────────┐
    │  PreToolUse Hook (Task tool)    │
    │    task-router.sh               │
    │        │                        │
    │        ▼                        │
    │    task-router.ts               │
    └─────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────┐
    │ 1. Extract prompt from Task     │
    │ 2. Check isSimpleTask()         │
    │    - <100 chars? → continue     │
    │    - "quick check"? → continue  │
    └─────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────┐
    │ 3. Call unified_gate.py via uv  │
    │    - Gate 1: Erotetic check     │
    │    - Gate 2: Resources check    │
    │    - Gate 3: Composition check  │
    │    - Pattern inference          │
    └─────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
    Gate Failure          Gate Success
        │                       │
        ▼                       ▼
    ┌─────────────────┐  ┌─────────────────────────────┐
    │ Block with      │  │ Pattern + Confidence?       │
    │ clarification/  │  │   confidence >= 0.7?        │
    │ resource/       │  │     → Block + suggest:      │
    │ composition     │  │       agentica_dispatch.py  │
    │ error           │  │   confidence < 0.7?         │
    │                 │  │     → continue (vanilla)    │
    └─────────────────┘  └─────────────────────────────┘
```

### Key Code Sections

**Pattern Detection via unified_gate.py:**

```typescript
// task-router.ts lines 69-175
function callUnifiedGate(prompt: string, sessionId: string): GateResult | null {
  const pythonCode = `
    from scripts.agentica_patterns.unified_gate import orchestrate_with_gates
    result = await orchestrate_with_gates(prompt, session_id)
    print(json.dumps({
      'success': result.get('success'),
      'pattern_used': result.get('pattern_used'),
      'confidence': result.get('confidence', 0.5),
      ...
    }))
  `;
  // Spawns Python via uv run
}
```

**Routing Decision:**

```typescript
// task-router.ts lines 294-316
if (patternUsed && confidence >= CONFIDENCE_THRESHOLD) {
  const output: HookOutput = {
    result: 'block',
    reason: `Task blocked - routing to Agentica ${patternUsed} pattern.
    Run this instead:
    uv run python scripts/agentica_dispatch.py --prompt '${prompt}' --pattern ${pattern}
    `
  };
}
```

---

## Proposed Routing Flow

> **Reference**: See `00-architecture-decisions.md` Section 18 (Routing Table) for agent selection.

### User Says "Run a Swarm on This Task"

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Layer 0: Agent Routing (keyword match + LLM fallback)                    │
│                                                                          │
│   Input: "Run a swarm to research auth patterns"                         │
│                                                                          │
│   1. Keyword match: "research" → Oracle/Scout/Pathfinder                 │
│   2. If no match: LLM classification (~500ms)                            │
│   3. NOT erotetic - erotetic is for parameter extraction, not routing    │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Layer 1: UserPromptSubmit Hook (skill-activation-prompt.sh)              │
│                                                                          │
│   Input: "Run a swarm to research auth patterns"                         │
│                                                                          │
│   1. Match against skill-rules.json                                      │
│   2. Find "agentica-swarm" trigger: "(run|spawn|use).*swarm"             │
│   3. Inject system message:                                              │
│      "Consider using /agentica-swarm skill for parallel exploration"     │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Layer 2: Claude Decides to Use Task Tool                                 │
│                                                                          │
│   Claude processes user request and decides:                             │
│   Task("Research auth patterns with multiple perspectives")              │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Layer 3: PreToolUse Hook (task-router.sh) **NEEDS REGISTRATION**         │
│                                                                          │
│   1. Intercept Task tool call                                            │
│   2. Call unified_gate.py:                                               │
│      - Erotetic gate (unknowns? keyword-based detection)                 │
│      - Resource gate (can we launch?)                                    │
│      - Composition gate (valid algebra?)                                 │
│      - Pattern inference → "swarm" (confidence: 0.85)                    │
│   3. Block vanilla Task, return:                                         │
│      "Run: uv run python scripts/agentica_dispatch.py                    │
│       --prompt 'Research auth patterns' --pattern swarm"                 │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Layer 4: Claude Executes Bash Command                                    │
│                                                                          │
│   Bash("uv run python scripts/agentica_dispatch.py ...")                 │
│                                                                          │
│   agentica_dispatch.py:                                                  │
│   - Calls orchestrate_with_gates()                                       │
│   - OrchestrationLayer spawns agents with PATTERN_TYPE=swarm             │
│   - Returns aggregated output                                            │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Layer 5: SubagentStart/Stop Hooks (Leads spawning Workers ONLY)          │
│                                                                          │
│   **Only fires for Lead agents (Kraken, Architect, etc.) spawning        │
│   Worker agents. Workers cannot spawn, so no hooks fire for them.**      │
│                                                                          │
│   For each spawned worker:                                               │
│   - SubagentStart: detectPattern() → 'swarm' → swarm.onSubagentStart()   │
│   - SubagentStop: → swarm.onSubagentStop() → broadcast 'done'            │
│   - Stop: → swarm.onStop() → check quorum                                │
└──────────────────────────────────────────────────────────────────────────┘
```

### Leads vs Workers (from 00-architecture-decisions.md)

| Type | Agents | Can Spawn? | SubagentStart/Stop fires? |
|------|--------|------------|---------------------------|
| **Lead** | Kraken, Architect, Phoenix, Herald, Maestro | Yes | Yes (when they spawn workers) |
| **Worker** | All others | No | No (they don't spawn) |

---

## New Components Needed

### 1. Register task-router Hook

**Add to .claude/settings.json:**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Task",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/task-router.sh",
            "timeout": 35
          }
        ]
      }
    ]
  }
}
```

### 2. Add Pattern Triggers to skill-rules.json

```json
{
  "agentica-swarm": {
    "type": "orchestration",
    "enforcement": "suggest",
    "priority": "high",
    "description": "Spawn parallel research swarm",
    "promptTriggers": {
      "keywords": ["swarm", "run swarm", "spawn swarm", "parallel exploration"],
      "intentPatterns": ["(run|spawn|use).*swarm", "parallel.*(research|explore)"]
    }
  },
  "agentica-jury": {
    "type": "orchestration",
    "enforcement": "suggest",
    "priority": "high",
    "description": "Spawn validation jury panel",
    "promptTriggers": {
      "keywords": ["jury", "jury pattern", "validation panel", "independent vote"],
      "intentPatterns": ["(run|use).*jury", "independent.*vote"]
    }
  },
  "agentica-hierarchical": {
    "type": "orchestration",
    "enforcement": "suggest",
    "priority": "high",
    "description": "Spawn coordinator-specialist hierarchy",
    "promptTriggers": {
      "keywords": ["hierarchical", "coordinator", "specialists", "delegate"],
      "intentPatterns": ["(run|use).*hierarchical", "coordinator.*specialist"]
    }
  }
}
```

### 3. Create Pattern Skills (Optional)

For each pattern, create a skill in `.claude/skills/agentica-<pattern>/SKILL.md`:

```markdown
---
name: agentica-swarm
description: Spawn parallel research swarm with multiple perspectives
---

# Agentica Swarm

Use when user wants parallel exploration from multiple angles.

## When to Use
- "Run a swarm on this"
- "Research from multiple perspectives"
- "Explore this in parallel"

## Command
\`\`\`bash
uv run python scripts/agentica_dispatch.py \
  --prompt "Your task description" \
  --pattern swarm
\`\`\`

## Environment Variables Set
- `PATTERN_TYPE=swarm`
- `SWARM_ID=<unique-id>`
- `AGENT_ID=<per-agent-id>`
```

---

## Implementation Sketch

### Step 1: Register task-router.sh

```bash
# Edit .claude/settings.json
# Add PreToolUse hook entry for Task matcher
```

### Step 2: Add skill triggers

```bash
# Edit .claude/skills/skill-rules.json
# Add agentica-swarm, agentica-jury, agentica-hierarchical entries
```

### Step 3: Test the flow

```bash
# 1. Say "run a swarm to research auth"
# 2. Verify skill suggestion appears
# 3. Verify Task is blocked
# 4. Verify agentica_dispatch.py runs
# 5. Verify PATTERN_TYPE is set for agents
```

---

## Current State Summary

| Component | Status | Gap |
|-----------|--------|-----|
| task-router.ts | Exists, complete | **Not registered in settings.json** |
| Pattern modules (11) | Complete | None |
| SubagentStart/Stop hooks | Registered | None |
| unified_gate.py | Complete | None |
| agentica_dispatch.py | Complete | None |
| skill-rules.json | Complete structure | **No pattern triggers** |
| Pattern skills | Partial (agentica-spawn exists) | Need individual pattern skills |

## Recommended Actions

1. **Critical**: Register task-router.sh in settings.json PreToolUse
2. **High**: Add pattern triggers to skill-rules.json
3. **Medium**: Create individual pattern skill files
4. **Low**: Add register-missing-hooks.sh script to automate setup
