---
name: create_handoff
version: 6.0-hybrid
description: Create handoff document for transferring work to another session
---

# Option: create_handoff

## I (Initiation)
activate: [session_ending, context_full, major_milestone, explicit_request]
skip: [task_just_started, no_work_completed]

## Y (Observation Space)
| signal | source | interpretation |
|--------|--------|----------------|
| session_name | ledger/handoff | active work stream |
| git_state | git metadata | commit/branch context |
| braintrust_ids | state files | trace linking |
| completed_work | session memory | task status |

## U (Action Space)
primary: [Bash, Write, AskUserQuestion]
forbidden: [Edit existing handoffs]

## pi (Policy)

### P0: Determine Session Name
```
eta |-> read_ledger OR read_handoff OR fallback_general
```

| action | Q | why | mitigation |
|--------|---|-----|------------|
| guess_name | -inf | Wrong folder created | check ledger first |
| skip_archive | LOW | Loses history | optional, not required |

### P1: Gather Metadata
```bash
# Session name from ledger/handoff
ls thoughts/ledgers/CONTINUITY_CLAUDE-*.md 2>/dev/null | head -1 | sed 's/.*CONTINUITY_CLAUDE-\(.*\)\.md/\1/'
ls -d thoughts/shared/handoffs/*/ 2>/dev/null | head -1 | xargs basename

# Git metadata via spec_metadata.sh
~/.claude/scripts/spec_metadata.sh

# Braintrust IDs (if available)
cat ~/.claude/state/braintrust_sessions/*.json | jq -s 'sort_by(.started) | last'
```

| action | Q | why |
|--------|---|-----|
| read_ledger_state | HIGH | Populate Ledger section accurately |
| get_braintrust_ids | MED | Enable artifact index linking |
| fallback_general | MED | Don't block if no ledger |

### P2: Write Handoff
```
eta |-> write_to_current_md
path = thoughts/shared/handoffs/{session_name}/current.md
```

**Template structure:**
- YAML frontmatter: date, session_name, git_commit, branch, root_span_id, turn_span_id
- Ledger section: Goal, Now, This Session, Next, Decisions
- Context section: Tasks, Critical References, Recent changes, Learnings, Post-Mortem, Artifacts, Next Steps

| action | Q | why |
|--------|---|-----|
| include_code_snippets | -inf | Bloats handoff | use file:line refs |
| omit_learnings | -inf | Loses context | required section |
| skip_postmortem | -inf | No artifact indexing | required for queryability |

### P3: Mark Session Outcome
```
eta |-> ask_user_outcome -> mark_in_db
```

| action | Q | why | mitigation |
|--------|---|-----|------------|
| guess_outcome | -inf | Wrong data for ML | always ask user |
| skip_marking | LOW | No outcome tracking | acceptable if DB missing |

### P4: Confirm Completion
```
eta |-> respond_with_resume_command
```

## beta (Termination)
```
beta(eta) = 1.0 if handoff_written AND outcome_marked
```
success: [handoff_file_exists, outcome_recorded, user_confirmed]
failure: [write_error, no_session_name, user_cancelled]

## Output Schema
```yaml
file: thoughts/shared/handoffs/{session_name}/current.md
sections: [Ledger, Context, Tasks, Learnings, Post-Mortem, Artifacts, Next Steps]
outcome: [SUCCEEDED, PARTIAL_PLUS, PARTIAL_MINUS, FAILED]
```

## Invariants
```
inv_1: always ask outcome before completion
inv_2: never include large code blocks (use file:line refs)
inv_3: Ledger section extracted by SessionStart hook
inv_4: Post-Mortem required for artifact indexing
```
