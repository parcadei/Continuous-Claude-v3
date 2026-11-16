---
description: Implement technical plans from thoughts/shared/plans with verification
---

# Implement Plan

You are tasked with implementing an approved technical plan from `thoughts/shared/plans/`. These plans contain phases with specific changes and success criteria.

## Execution Modes

You have two execution modes:

### Mode 1: Direct Implementation (Default)
For small plans (3 or fewer tasks) or when user requests direct implementation.
- You implement each phase yourself
- Context accumulates in main conversation
- Use this for quick, focused implementations

### Mode 2: Agent Orchestration (Recommended for larger plans)
For plans with 4+ tasks or when context preservation is critical.
- You act as a thin orchestrator
- Agents execute each task and create handoffs
- Compaction-resistant: handoffs persist even if context compacts
- Use this for multi-phase implementations

**To use agent orchestration mode**, say: "I'll use agent orchestration for this plan" and follow the Agent Orchestration section below.

---

## Getting Started

When given a plan path:
- Read the plan completely and check for any existing checkmarks (- [x])
- Read the original ticket and all files mentioned in the plan
- **Read files fully** - never use limit/offset parameters, you need complete context
- Think deeply about how the pieces fit together
- Create a todo list to track your progress
- Start implementing if you understand what needs to be done

If no plan path provided, ask for one.

## Implementation Philosophy

Plans are carefully designed, but reality can be messy. Your job is to:
- Follow the plan's intent while adapting to what you find
- Implement each phase fully before moving to the next
- Verify your work makes sense in the broader codebase context
- Update checkboxes in the plan as you complete sections

When things don't match the plan exactly, think about why and communicate clearly. The plan is your guide, but your judgment matters too.

If you encounter a mismatch:
- STOP and think deeply about why the plan can't be followed
- Present the issue clearly:
  ```
  Issue in Phase [N]:
  Expected: [what the plan says]
  Found: [actual situation]
  Why this matters: [explanation]

  How should I proceed?
  ```

## Verification Approach

After implementing a phase:
- Run the success criteria checks (usually `make check test` covers everything)
- Fix any issues before proceeding
- Update your progress in both the plan and your todos
- Check off completed items in the plan file itself using Edit
- **Pause for human verification**: After completing all automated verification for a phase, pause and inform the human that the phase is ready for manual testing. Use this format:
  ```
  Phase [N] Complete - Ready for Manual Verification

  Automated verification passed:
  - [List automated checks that passed]

  Please perform the manual verification steps listed in the plan:
  - [List manual verification items from the plan]

  Let me know when manual testing is complete so I can proceed to Phase [N+1].
  ```

If instructed to execute multiple phases consecutively, skip the pause until the last phase. Otherwise, assume you are just doing one phase.

do not check off items in the manual testing steps until confirmed by the user.


## If You Get Stuck

When something isn't working as expected:
- First, make sure you've read and understood all the relevant code
- Consider if the codebase has evolved since the plan was written
- Present the mismatch clearly and ask for guidance

Use sub-tasks sparingly - mainly for targeted debugging or exploring unfamiliar territory.

## Resumable Agents

If the plan was created by `plan-agent`, you may be able to resume it for clarification:

1. Check `.claude/cache/agents/agent-log.jsonl` for the plan-agent entry
2. Look for the `agentId` field
3. To clarify or update the plan:
   ```
   Task(
     resume="<agentId>",
     prompt="Phase 2 isn't matching the codebase. Can you clarify..."
   )
   ```

The resumed agent retains its full prior context (research, codebase analysis).

Available agents to resume:
- `plan-agent` - Created the implementation plan
- `research-agent` - Researched best practices
- `debug-agent` - Investigated issues

## Resuming Work

If the plan has existing checkmarks:
- Trust that completed work is done
- Pick up from the first unchecked item
- Verify previous work only if something seems off

Remember: You're implementing a solution, not just checking boxes. Keep the end goal in mind and maintain forward momentum.

---

## Agent Orchestration Mode

When implementing larger plans (4+ tasks), use agent orchestration to stay compaction-resistant.

### Why Agent Orchestration?

**The Problem:** During long implementations, context accumulates. If auto-compact triggers mid-task, you lose implementation context. Handoffs created at 80% context become stale.

**The Solution:** Delegate implementation to agents. Each agent:
- Starts with fresh context
- Implements one task
- Creates a handoff on completion
- Returns to orchestrator

Handoffs persist on disk. If compaction happens, you re-read handoffs and continue.

### Setup

1. **Create handoff directory:**
   ```bash
   mkdir -p thoughts/handoffs/<session-name>
   ```
   Use the session name from your continuity ledger.

2. **Read the implementation agent skill:**
   ```bash
   cat .claude/skills/implement_task/SKILL.md
   ```
   This defines how agents should behave.

### Pre-Requisite: Plan Validation

Before implementing, ensure the plan has been validated using the `validate-agent`. The validation step is separate and should have created a handoff with status VALIDATED.

**Check for validation handoff:**
```bash
ls thoughts/handoffs/<session>/validation-*.md
```

If no validation exists, suggest running validation first:
```
"This plan hasn't been validated yet. Would you like me to spawn validate-agent first?"
```

If validation exists but status is NEEDS REVIEW, present the issues before proceeding.

### Orchestration Loop

For each task in the plan:

1. **Prepare agent context:**
   - Read continuity ledger (current state)
   - Read the plan (overall context)
   - Read previous handoff if exists (from thoughts/handoffs/<session>/)
   - Identify the specific task

2. **Spawn implementation agent:**
   ```
   Task(
     subagent_type="general-purpose",
     model="opus",
     prompt="""
     [Paste contents of .claude/skills/implement_task/SKILL.md here]

     ---

     ## Your Context

     ### Continuity Ledger:
     [Paste ledger content]

     ### Plan:
     [Paste relevant plan section or full plan]

     ### Your Task:
     Task [N] of [Total]: [Task description from plan]

     ### Previous Handoff:
     [Paste previous task's handoff content, or "This is the first task - no previous handoff"]

     ### Handoff Directory:
     thoughts/handoffs/<session-name>/

     ### Handoff Filename:
     task-[NN]-[short-description].md

     ---

     Implement your task and create your handoff.
     """
   )
   ```

3. **Process agent result:**
   - Read the agent's handoff file
   - Update ledger checkbox: `[x] Task N`
   - Update plan checkbox if applicable
   - Continue to next task

4. **On agent failure/blocker:**
   - Read the handoff (status will be "blocked")
   - Present blocker to user
   - Decide: retry, skip, or ask user

### Recovery After Compaction

If auto-compact happens mid-orchestration:

1. Read continuity ledger (loaded by SessionStart hook)
2. List handoff directory:
   ```bash
   ls -la thoughts/handoffs/<session-name>/
   ```
3. Read the last handoff to understand where you were
4. Continue spawning agents from next uncompleted task

### Example Orchestration Session

```
User: /implement_plan thoughts/shared/plans/PLAN-add-auth.md

Claude: I'll use agent orchestration for this plan (6 tasks).

Setting up handoff directory...
[Creates thoughts/handoffs/add-auth/]

Task 1 of 6: Create user model
[Spawns agent with full context]
[Agent completes, creates task-01-user-model.md]

✅ Task 1 complete. Handoff: thoughts/handoffs/add-auth/task-01-user-model.md

Task 2 of 6: Add authentication middleware
[Spawns agent with previous handoff]
[Agent completes, creates task-02-auth-middleware.md]

✅ Task 2 complete. Handoff: thoughts/handoffs/add-auth/task-02-auth-middleware.md

--- AUTO COMPACT HAPPENS ---
[Context compressed, but handoffs persist]

Claude: [Reads ledger, sees tasks 1-2 done]
[Reads last handoff task-02-auth-middleware.md]

Resuming from Task 3 of 6: Create login endpoint
[Spawns agent]
...
```

### Handoff Chain

Each agent reads previous handoff → does work → creates next handoff:

```
task-01-user-model.md
    ↓ (read by agent 2)
task-02-auth-middleware.md
    ↓ (read by agent 3)
task-03-login-endpoint.md
    ↓ (read by agent 4)
...
```

The chain preserves context even across compactions.

### When to Use Agent Orchestration

| Scenario | Mode |
|----------|------|
| 1-3 simple tasks | Direct implementation |
| 4+ tasks | Agent orchestration |
| Critical context to preserve | Agent orchestration |
| Quick bug fix | Direct implementation |
| Major feature implementation | Agent orchestration |
| User explicitly requests | Respect user preference |

### Tips

- **Keep orchestrator thin:** Don't do implementation work yourself. Just manage agents.
- **Trust the handoffs:** Agents create detailed handoffs. Use them for context.
- **One agent per task:** Don't batch multiple tasks into one agent.
- **Sequential execution:** Start with sequential. Parallel adds complexity.
- **Update ledger:** After each task, update the continuity ledger checkbox.
