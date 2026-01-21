---
name: create-handoff
description: Create handoff document for transferring work to another session
---

# Create Handoff

You are tasked with writing a handoff document to hand off your work to another agent in a new session. You will create a handoff document that is thorough, but also **concise**. The goal is to compact and summarize your context without losing any of the key details of what you're working on.


## Process
### 1. Filepath & Metadata
Use the following information to understand how to create your document:

**First, determine the session name from existing handoffs:**
```bash
ls -td thoughts/shared/handoffs/*/ 2>/dev/null | head -1 | xargs basename
```

This returns the most recently modified handoff folder name (e.g., `open-source-release`). Use this as the handoff folder name.

If no handoffs exist, use `general` as the folder name.

**Create your file under:** `thoughts/shared/handoffs/{session-name}/YYYY-MM-DD_HH-MM_description.yaml`, where:
- `{session-name}` is from existing handoffs (e.g., `open-source-release`) or `general` if none exist
- `YYYY-MM-DD` is today's date
- `HH-MM` is the current time in 24-hour format (no seconds needed)
- `description` is a brief kebab-case description

**Examples:**
- `thoughts/shared/handoffs/open-source-release/2026-01-08_16-30_memory-system-fix.yaml`
- `thoughts/shared/handoffs/general/2026-01-08_16-30_bug-investigation.yaml`

### 2. Write YAML handoff (~400 tokens vs ~2000 for markdown)

**CRITICAL: Use EXACTLY this YAML format. Do NOT deviate or use alternative field names.**

The `goal:` and `now:` fields are shown in the statusline - they MUST be named exactly this.

```yaml
---
session: {session-name from ledger}
date: YYYY-MM-DD
status: complete|partial|blocked
outcome: SUCCEEDED|PARTIAL_PLUS|PARTIAL_MINUS|FAILED
---

goal: {What this session accomplished - shown in statusline}
now: {What next session should do first - shown in statusline}
test: {Command to verify this work, e.g., pytest tests/test_foo.py}

done_this_session:
  - task: {First completed task}
    files: [{file1.py}, {file2.py}]
  - task: {Second completed task}
    files: [{file3.py}]

blockers: [{any blocking issues}]

questions: [{unresolved questions for next session}]

decisions:
  - {decision_name}: {rationale}

findings:
  - {key_finding}: {details}

worked: [{approaches that worked}]
failed: [{approaches that failed and why}]

next:
  - {First next step}
  - {Second next step}

files:
  created: [{new files}]
  modified: [{changed files}]
```

**Field guide:**
- `goal:` + `now:` - REQUIRED, shown in statusline
- `done_this_session:` - What was accomplished with file references
- `decisions:` - Important choices and rationale
- `findings:` - Key learnings
- `worked:` / `failed:` - What to repeat vs avoid
- `next:` - Action items for next session

**DO NOT use alternative field names like `session_goal`, `objective`, `focus`, `current`, etc.**
**The statusline parser looks for EXACTLY `goal:` and `now:` - nothing else works.**
---

### 3. Mark Session Outcome (REQUIRED)

**IMPORTANT:** Before responding to the user, you MUST ask about the session outcome.

Use the AskUserQuestion tool with these exact options:

```
Question: "How did this session go?"
Options:
  - SUCCEEDED: Task completed successfully
  - PARTIAL_PLUS: Mostly done, minor issues remain
  - PARTIAL_MINUS: Some progress, major issues remain
  - FAILED: Task abandoned or blocked
```

After the user responds, index and mark the outcome:
```bash
# Mark the most recent handoff (works with PostgreSQL or SQLite)
# Use git root to find project, then opc/scripts/core/
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "${CLAUDE_PROJECT_DIR:-.}")

# First, index the handoff into the database
cd "$PROJECT_ROOT/opc" && uv run python scripts/core/artifact_index.py --file thoughts/shared/handoffs/{session_name}/{filename}.yaml

# Then mark the outcome
cd "$PROJECT_ROOT/opc" && uv run python scripts/core/artifact_mark.py --latest --outcome <USER_CHOICE>
```

**IMPORTANT:** Replace `{session_name}` and `{filename}` with the actual values from step 1.

These commands auto-detect the database (PostgreSQL if configured, SQLite fallback).

**Note:** If indexing fails, the marking step will show "Database marking was not available" - this is acceptable for the first handoff but indicates the indexing step was skipped.

### 4. Confirm completion

After marking the outcome, respond to the user:

```
Handoff created! Outcome marked as [OUTCOME].

Resume in a new session with:
/resume_handoff path/to/handoff.yaml
```

---
##.  Additional Notes & Instructions
- **more information, not less**. This is a guideline that defines the minimum of what a handoff should be. Always feel free to include more information if necessary.
- **be thorough and precise**. include both top-level objectives, and lower-level details as necessary.
- **avoid excessive code snippets**. While a brief snippet to describe some key change is important, avoid large code blocks or diffs; do not include one unless it's necessary (e.g. pertains to an error you're debugging). Prefer using `/path/to/file.ext:line` references that an agent can follow later when it's ready, e.g. `packages/dashboard/src/app/dashboard/page.tsx:12-24`
