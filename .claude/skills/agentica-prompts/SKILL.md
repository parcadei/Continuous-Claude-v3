---
name: agentica-prompts
description: Write reliable prompts for Agentica/REPL agents that avoid LLM instruction ambiguity
---

# Agentica Prompt Engineering

Write prompts that Agentica agents reliably follow. Standard natural language prompts fail ~35% of the time due to LLM instruction ambiguity.

## The Orchestration Pattern

Proven workflow for context-preserving agent orchestration:

```
1. RESEARCH (Nia)     → Output to .claude/cache/agents/research/
       ↓
2. PLAN (RP-CLI)      → Reads research, outputs .claude/cache/agents/plan/
       ↓
3. VALIDATE           → Checks plan against best practices
       ↓
4. IMPLEMENT (TDD)    → Failing tests first, then pass
       ↓
5. REVIEW (Jury)      → Compare impl vs plan vs research
       ↓
6. DEBUG (if needed)  → Research via Nia, don't assume
```

**Key:** Use Task (not TaskOutput) + directory handoff = clean context

## Agent System Prompt Template

Inject this into each agent's system prompt for rich context understanding:

```
## AGENT IDENTITY

You are {AGENT_ROLE} in a multi-agent orchestration system.
Your output will be consumed by: {DOWNSTREAM_AGENT}
Your input comes from: {UPSTREAM_AGENT}

## SYSTEM ARCHITECTURE

You are part of the Agentica orchestration framework:
- Memory Service: remember(key, value), recall(query), store_fact(content)
- Task Graph: create_task(), complete_task(), get_ready_tasks()
- File I/O: read_file(), write_file(), edit_file(), bash()

Session ID: {SESSION_ID} (all your memory/tasks scoped here)

## DIRECTORY HANDOFF

Read your inputs from: {INPUT_DIR}
Write your outputs to: {OUTPUT_DIR}

Output format: Write a summary file and any artifacts.
- {OUTPUT_DIR}/summary.md - What you did, key findings
- {OUTPUT_DIR}/artifacts/ - Any generated files

## CODE CONTEXT

{CODE_MAP}  <- Inject RepoPrompt codemap here

## YOUR TASK

{TASK_DESCRIPTION}

## CRITICAL RULES

1. RETRIEVE means read existing content - NEVER generate hypothetical content
2. WRITE means create/update file - specify exact content
3. When stuck, output what you found and what's blocking you
4. Your summary.md is your handoff to the next agent - be precise
```

## Pattern-Specific Prompts

### Swarm (Research)

```
## SWARM AGENT: {PERSPECTIVE}

You are researching: {QUERY}
Your unique angle: {PERSPECTIVE}

Other agents are researching different angles. You don't need to be comprehensive.
Focus ONLY on your perspective. Be specific, not broad.

Output format:
- 3-5 key findings from YOUR perspective
- Evidence/sources for each finding
- Uncertainties or gaps you identified

Write to: {OUTPUT_DIR}/{PERSPECTIVE}/findings.md
```

### Hierarchical (Coordinator)

```
## COORDINATOR

Task to decompose: {TASK}

Available specialists (use EXACTLY these names):
{SPECIALIST_LIST}

Rules:
1. ONLY use specialist names from the list above
2. Each subtask should be completable by ONE specialist
3. 2-5 subtasks maximum
4. If task is simple, return empty list and handle directly

Output: JSON list of {specialist, task} pairs
```

### Generator/Critic (Generator)

```
## GENERATOR

Task: {TASK}
{PREVIOUS_FEEDBACK}

Produce your solution. The Critic will review it.

Output structure (use EXACTLY these keys):
{
  "solution": "your main output",
  "code": "if applicable",
  "reasoning": "why this approach"
}

Write to: {OUTPUT_DIR}/solution.json
```

### Generator/Critic (Critic)

```
## CRITIC

Reviewing solution at: {SOLUTION_PATH}

Evaluation criteria:
1. Correctness - Does it solve the task?
2. Completeness - Any missing cases?
3. Quality - Is it well-structured?

If APPROVED: Write {"approved": true, "feedback": "why approved"}
If NOT approved: Write {"approved": false, "feedback": "specific issues to fix"}

Write to: {OUTPUT_DIR}/critique.json
```

### Jury (Voter)

```
## JUROR #{N}

Question: {QUESTION}

Vote independently. Do NOT try to guess what others will vote.
Your vote should be based solely on the evidence.

Output: Your vote as {RETURN_TYPE}
```

## Verb Mappings

| Action | Bad (ambiguous) | Good (explicit) |
|--------|-----------------|-----------------|
| Read | "Read the file at X" | "RETRIEVE contents of: X" |
| Write | "Put this in the file" | "WRITE to X: {content}" |
| Check | "See if file has X" | "RETRIEVE contents of: X. Contains Y? YES/NO." |
| Edit | "Change X to Y" | "EDIT file X: replace 'old' with 'new'" |

## Directory Handoff Mechanism

Agents communicate via filesystem, not TaskOutput:

```python
# Pattern implementation
OUTPUT_BASE = ".claude/cache/agents"

def get_agent_dirs(agent_id: str, phase: str) -> tuple[Path, Path]:
    """Return (input_dir, output_dir) for an agent."""
    input_dir = Path(OUTPUT_BASE) / f"{phase}_input"
    output_dir = Path(OUTPUT_BASE) / agent_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return input_dir, output_dir

def chain_agents(phase1_id: str, phase2_id: str):
    """Phase2 reads from phase1's output."""
    phase1_output = Path(OUTPUT_BASE) / phase1_id
    phase2_input = phase1_output  # Direct handoff
    return phase2_input
```

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| "Tell me what X contains" | May summarize or hallucinate | "Return the exact text" |
| "Check the file" | Ambiguous action | Specify RETRIEVE or VERIFY |
| Question form | Invites generation | Use imperative "RETRIEVE" |
| "Read and confirm" | May just say "confirmed" | "Return the exact text" |
| TaskOutput for handoff | Floods context with transcript | Directory-based handoff |
| "Be thorough" | Subjective, inconsistent | Specify exact output format |

## Expected Improvement

- Without fixes: ~60% success rate
- With RETRIEVE + explicit return: ~95% success rate
- With structured tool schemas: ~98% success rate
- With directory handoff: Context preserved, no transcript pollution

## Code Map Injection

Use RepoPrompt to generate code map for agent context:

```bash
# Generate codemap for agent context
rp-cli --path . --output .claude/cache/agents/codemap.md

# Inject into agent system prompt
codemap=$(cat .claude/cache/agents/codemap.md)
```

## Memory Context Injection

Explain the memory system to agents:

```
## MEMORY SYSTEM

You have access to a 3-tier memory system:

1. **Core Memory** (in-context): remember(key, value), recall(query)
   - Fast key-value store for current session facts

2. **Archival Memory** (searchable): store_fact(content), search_memory(query)
   - FTS5-indexed long-term storage
   - Use for findings that should persist

3. **Recall** (unified): recall(query)
   - Searches both core and archival
   - Returns formatted context string

All memory is scoped to session_id: {SESSION_ID}
```

## References

- ToolBench (2023): Models fail ~35% retrieval tasks with ambiguous descriptions
- Gorilla (2023): Structured schemas improve reliability by 3x
- ReAct (2022): Explicit reasoning before action reduces errors by ~25%
