---
name: create_plan
description: Create implementation plans through iterative research
model: opus
version: 5.0-hybrid
---

# Option: create_plan

```
o = (I, pi, beta)  -- Initiation, Policy, Termination
```

## Initiation (I)

**Activate:** User requests implementation planning, ticket provided, complex multi-phase work.
**Skip:** Simple one-shot tasks, pure research without implementation goal.

## Observation Space (Y)

| Observation | Source | Purpose |
|-------------|--------|---------|
| task_spec | User prompt, ticket | Goal definition |
| file_contents | Read tool | Current state |
| code_patterns | Agent research | Implementation guidance |
| user_feedback | Clarifications | Requirement refinement |

## Action Space (U)

- **Primary:** Read, Task, TodoWrite, Write, Bash(mkdir)
- **Support:** WebSearch, Glob, Grep
- **Forbidden:** Edit, destructive Bash (planning only)

---

## Policy (pi)

### P0: Parameter Check
```
eta_0 |-> read_all(params) if has_params(prompt)
eta_0 |-> present(initial_prompt) otherwise
```

Initial prompt: Request task/ticket, context, constraints, research links.

### P1: Context Gathering
```
for file in mentioned_files(task_spec):
  eta |-> read_fully(file)              # Q = HIGH
  Q(spawn_before_read) = -inf           # Forbidden

eta' |-> spawn_parallel([codebase-locator, codebase-analyzer, thoughts-locator])
eta' |-> wait_all
```

### P2: Understanding
```
eta |-> present_understanding(summary, evidence[], questions[])
if user_correction: eta |-> spawn_verification(correction)
```

Template: "Based on research, I understand [summary]. Found: [evidence]. Questions: [focused]."

### P3: Design Options
```
eta |-> present_options([{approach, pros, cons}, ...])
eta |-> await_selection
```

### P4: Structure
```
eta |-> present_structure(overview, phases[{name, accomplishment}])
eta |-> await_approval
```

### P5: Write Plan
```
eta |-> bash("mkdir -p thoughts/shared/plans")
eta |-> write_plan("thoughts/shared/plans/{date}-{ticket}-{desc}.md")
```

### P6: Review
```
eta |-> present_draft(path)
while not approved:
  eta |-> revise(feedback)
```

---

## Termination (beta)

```
beta(eta) = 1.0 if approved OR abandoned OR max_iterations
beta(eta) = 0.0 otherwise
```

**Success:** Plan approved, all criteria defined, no open questions.
**Failure:** Abandoned, max iterations, irreconcilable requirements.

---

## Q-Heuristics

### Global Preferences
```
ask_clarification >> assume            when confidence < 0.7
read_file >> guess_content             when file_mentioned
spawn_research >> proceed_blind        when codebase_unknown
verify_correction >> accept_blindly    when user_corrects
wait_all_tasks >> partial_synthesis    in research
```

### Phase-Specific

| Phase | HIGH Q | LOW Q |
|-------|--------|-------|
| Gather | read_fully, spawn_parallel | partial_read, sequential |
| Present | cite_evidence, focused_questions | vague_claims, many_questions |
| Design | compare_options | single_option, assume |
| Write | complete_schema | missing_sections |
| Review | address_feedback | ignore_feedback |

### Constraints (Q = -inf)
- partial_read when file mentioned
- spawn before read(mentioned_files)
- finalize when open_questions exist
- proceed(phase_n+1) before approved(phase_n)

---

## Agent Dispatch

| Condition | Agent |
|-----------|-------|
| files unknown | codebase-locator |
| impl unclear | codebase-analyzer |
| patterns needed | codebase-pattern-finder |
| prior work? | thoughts-locator |
| external docs | research-agent |

---

## State Machine

```
INIT --> GATHER --> PRESENT --> OPTIONS --> STRUCTURE --> WRITE --> REVIEW --> DONE
             |          |           |                        |          |
          (clarify)*  (verify)*  (iterate)*                          (iterate)*
```

---

## Output Schema (REQUIRED)

```yaml
path: "thoughts/shared/plans/YYYY-MM-DD-{ticket}-{desc}.md"
sections:
  required:
    - overview
    - current_state_analysis:
        format: "file:line evidence"
    - desired_end_state
    - key_discoveries[]:
        min: 3
        format: "[Dn] discovery text (file:line)"
    - not_doing[]
    - implementation_approach
    - phases[]:
        - name
        - overview
        - effort_hours: number  # REQUIRED per phase
        - changes[]:
            - file
            - description
            - code_snippet?      # Key functions, not stubs
        - success_criteria:
            - automated[]        # executable commands
            - manual[]           # human verification
    - risks[]:                   # REQUIRED, min 3
        - risk: string
        - likelihood: "low" | "medium" | "high"
        - impact: "low" | "medium" | "high"
        - mitigation: string
    - effort_estimates:          # REQUIRED summary table
        format: |
          | Phase | Hours | Notes |
          |-------|-------|-------|
    - decision_rationale:        # Q-heuristic audit
        format: |
          | Decision | Selected | Alternative | Q-value | Why |
          |----------|----------|-------------|---------|-----|
    - testing_strategy
    - references[]
  optional:
    - functor_diagram            # If category theory applicable
    - i_state_summary            # Session state for continuity
    - performance_considerations
    - migration_notes
```

---

## Templates (Required Output)

**Risks:** `| Risk | Likelihood | Impact | Mitigation |` - min 3 rows covering: Technical, Scope, Integration, Performance.

**Effort:** `| Phase | Hours | Notes |` - per-phase hours with total.

**Decisions:** `| Decision | Selected | Alternative | Q | Why |` - Q-values: HIGH/MED/LOW.

---

## Invariants

```
inv_1: never partial_read(f)
inv_2: open_question => not finalized
inv_3: phase(n) => approved(n-1)
inv_4: claim => evidence(claim)
inv_5: plan => risks.length >= 3
inv_6: phase => effort_hours defined
```

---

## Decision Theory vs Modal Logic

| Modal Logic | Decision Theory |
|-------------|-----------------|
| O(phi) obligation | pi: eta |-> action |
| F(phi) forbidden | Q(eta, action) = -inf |
| K(p) knowledge | eta.beliefs[p] = HIGH |
| ?{a,b} question | info-gathering action |
| <>phi eventually | goal in beta |

**Hybrid advantages:**
1. Explicit action selection via Q-values (Decision Theory)
2. Required risk/effort outputs (Modal Logic output quality)
3. Termination as probability function (Decision Theory)
4. Evidence-backed claims with file:line (both)
5. Actionable project management info (Modal Logic)
