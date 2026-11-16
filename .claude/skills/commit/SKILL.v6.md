---
name: commit
version: 6.0-hybrid
description: Create git commits with user approval and no Claude attribution
---

# Option: commit

## I (Initiation)
activate: [user_says_commit, user_says_push, feature_complete]
skip: [uncommitted_changes_empty, mid_implementation]

## Y (Observation Space)
| signal | source | interpretation |
|--------|--------|----------------|
| git_status | git status | modified/staged files |
| git_diff | git diff | actual changes |
| conversation_context | session history | what was accomplished |

## U (Action Space)
primary: [Bash]
forbidden: [co_author_lines, claude_attribution]

## pi (Policy)

### P0: Review Changes
```
eta |-> assess_changes via git_status, git_diff
```

| action | Q | why | mitigation |
|--------|---|-----|------------|
| git_add_all | -inf | Adds unintended files | use explicit file paths |
| assume_single_commit | -inf | Forces unrelated changes together | assess logical grouping |

### P1: Plan Commits
```
eta |-> group_files_logically
eta |-> draft_messages (imperative mood, explain why)
```

| action | Q | why |
|--------|---|-----|
| atomic_commits | HIGH | Clear history, easy revert |
| descriptive_messages | HIGH | Future context |

### P2: Request Approval
```
eta |-> present_plan_to_user
plan: {files: [...], message: "...", count: N}
```

| action | Q | why |
|--------|---|-----|
| execute_without_approval | -inf | User may disagree with grouping |
| ask_confirmation | +inf | User trusts but verifies |

### P3: Execute
```
eta |-> git_add(specific_files)
eta |-> git_commit(message)
eta |-> generate_reasoning(hash, message)
```

| action | Q | why |
|--------|---|-----|
| add_specific_files | HIGH | Intentional commits |
| generate_reasoning | HIGH | Preserves build context |

### Command Reference
```bash
git add <file1> <file2> ...
git commit -m "message"
bash .claude/scripts/generate-reasoning.sh <hash> "<message>"
git log --oneline -n N
```

## beta (Termination)
```
beta(eta) = 1.0 if commits_created OR user_cancels
```
success: [commits_made, reasoning_generated, log_shown]
failure: [no_changes, user_declined]

## Output Schema
```yaml
plan: {commits: [{files: [...], message: "..."}]}
result: {hashes: [...], log: "..."}
```

## Invariants
```
inv_1: never include "Co-Authored-By" or "Generated with Claude"
inv_2: always use specific file paths (never git add -A)
inv_3: always generate reasoning.md after each commit
```
