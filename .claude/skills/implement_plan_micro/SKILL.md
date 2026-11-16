---
name: implement_plan
description: Implement technical plans from thoughts/shared/plans with verification
version: 3.0
---

# Formal Specification

## Multimodal Logic Integration

Five modal logics via fusion with bridge principles:
- **JL**: Justification Logic - evidence-backed claims
- **IEL**: Inferential Erotetic Logic - question handling
- **TEL**: Temporal Epistemic Logic - phase sequencing
- **SDL**: Standard Deontic Logic - obligations/permissions
- **DEL**: Dynamic Epistemic Logic - action modalities

## Justification Logic (JL)

```
# Justification terms
[h]:context(task_n)                    # Handoff h justifies task context
[v]:verified(phase_n)                  # Verification v justifies completion
[p]:plan(tasks)                        # Plan p justifies task list

# Evidence production
[read(f)]exists e. [e]:content(f)
[verify(c)]exists v. [v]:pass(c) | [v]:fail(c)

# Handoff chain: evidence propagates
[h_n]:complete(task_n) -> [h_{n+1}]:context(task_{n+1})
proceed(task) <-> exists h. [h]:validated
```

## Inferential Erotetic Logic (IEL)

```
# Mode and blocker questions
?{direct, orchestration}               # Mode selection
?{continue, retry, ask_user}           # Blocker resolution
mismatch(plan, reality) -> ?{how_proceed}
no_validation -> ?{run_validation_first}
```

## Temporal Epistemic Logic (TEL)

```
# File reading constraints
[](mentioned(f) -> <>read_fully(f))           # Eventually read
[](mentioned(f) -> not spawn U read_fully(f)) # No spawn until read
[](partial_read(f) -> false)                  # Partial reads forbidden

# Phase sequencing
[](phase(n) -> P(phase(n-1) & verified(n-1))) # Verified before next
[](automated_pass -> <>manual_verify)         # Automated gates manual
[](manual_pass(n) -> <>phase(n+1))            # Manual gates next phase

# Handoff persistence
[](handoff_created(h) -> []exists_on_disk(h)) # Survives compaction

# Termination
<>(all_complete | abandoned)
```

## Standard Deontic Logic (SDL)

```
# Reading obligations
O(read_fully(plan))
O(read_fully(f)) <- mentioned_in_plan(f)
O(check_existing_checkmarks)
F(partial_read)

# Verification obligations
O(run_automated) <- impl_complete
O(pause_for_manual) <- automated_pass
O(present_manual_checklist)
F(checkoff_manual) <- not user_confirmed

# Mode selection
O(orchestration) <- tasks >= 4
P(direct) <- tasks <= 3
O(respect_user_preference)

# Orchestration obligations
O(read_previous_handoff) <- exists_handoff(task_{n-1})
O(create_handoff) <- agent_completes
O(update_ledger) <- task_complete
F(batch_tasks)                                # One agent per task
F(proceed_on_mismatch) <- not user_guidance
```

## Dynamic Epistemic Logic (DEL)

```
# Implementation actions
[read(plan)]K(tasks) & K(phases) & K(criteria)
[read(handoff_n)]K(context_{n+1})
[spawn(agent, task)]<>result(agent)
[verify(c)](K(pass) | K(fail))

# Composed workflows
[select_direct][implement ; verify_auto ; present_manual ; wait]*
[select_orchestration][prepare ; spawn ; wait ; read_handoff ; update]*

# Recovery
[compaction ; read_ledger ; list_handoffs ; read_last]resume

# Mismatch
[detect_mismatch ; stop ; present ; wait]proceed_or_abort
```

## Bridge Principles

```
# Evidence persistence (JL-TEL)
[h]:context(n) -> [][h]:context(n)

# Evidence obligations (JL-SDL)
O(exists h. [h]:validated) <- pre_implement
O(exists v. [v]:pass(auto)) <- pre_manual

# Handoff chain (full integration)
[h_n]:complete(n) -> O([spawn]<>[h_{n+1}]:context(n+1))
compaction -> (forall h. persists(h))
```

## State Machine

```
INIT --> READ_PLAN --> MODE_SELECT --+--> DIRECT: [IMPL -> AUTO -> MANUAL -> WAIT]*
                                     |
                                     +--> ORCHESTRATION: [PREP -> SPAWN -> WAIT -> HANDOFF]*
                                                                                    |
                                                                                    v
                                                                                COMPLETE
```

## Output Schema

```yaml
handoff_path: "thoughts/handoffs/<session>/task-[NN]-[desc].md"
schema:
  required: [status, task_desc, files_modified[], verification_results, context_for_next]
  optional: [blocker, decisions[], open_questions[]]
tracking:
  plan: "- [x] Task N: description"
  ledger: "[x] Task N"
```

---

# Prose (Where Logic Insufficient)

## Mode Selection

| Tasks | Context Critical | Mode |
|-------|------------------|------|
| 1-3 | No | Direct |
| 1-3 | Yes | Orchestration |
| 4+ | Any | Orchestration |

User preference overrides.

## Templates

**Mismatch:**
```
Issue in Phase [N]:
Expected: [plan says]
Found: [actual]
How should I proceed?
```

**Manual Verification Pause:**
```
Phase [N] Complete - Ready for Manual Verification
Automated passed: [list]
Please verify: [manual items from plan]
Let me know when done.
```

**Agent Spawn:**
```
Task(subagent_type="general-purpose", model="opus", prompt="""
[implement_task SKILL.md]
## Context
- Ledger: [content]
- Plan: [section]
- Task: [N]/[Total]: [desc]
- Previous Handoff: [content or "first task"]
- Handoff Dir: thoughts/handoffs/<session>/
""")
```

**Recovery (post-compaction):**
1. Ledger auto-loaded by SessionStart
2. `ls thoughts/handoffs/<session>/`
3. Read last handoff
4. Resume next task

---

# Validity Constraints

```
forall phase. has_auto_criteria(phase) & has_manual_criteria(phase)
forall task. one_agent_per_task(task)
forall h. on_disk(h) -> recoverable(h)
compaction -> (forall h. persists(h))
forall i < j. completed(task_i) before started(task_j)
```
