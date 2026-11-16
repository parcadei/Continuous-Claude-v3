# Observe Before Editing

Before editing code to fix a bug, confirm what the system *actually produced*.

## Pattern

Outputs don't lie. Code might. Check outputs first.

## DO

1. Check if expected directories exist: `ls -la .claude/cache/`
2. Check if expected files were created: `ls -la .claude/cache/learnings/`
3. Check logs for errors: `tail .claude/cache/*.log`
4. Run the failing command manually to see actual error
5. Only then edit code

## DON'T

- Assume "hook didn't run" without checking outputs
- Edit code based on what you *think* should happen
- Confuse global vs project paths (check both: `.claude/` and `~/.claude/`)

## Source Sessions

- a541f08a: Token limit error was invisible until manual run revealed it
- 6a9f2d7a: Looked in wrong cache path (`~/.claude/` vs `.claude/`), assumed hook failure
- a8bd5cea: Confirmed hook worked by finding output files in project cache
- 1c21e6c8: Verified Artifact Index indexing by checking DB file exists
