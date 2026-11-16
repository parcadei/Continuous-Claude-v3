# Changelog

Human and Claude-readable changelog for Claude Continuity Kit features.

Format: Each entry includes **What**, **Why**, and **How** for full context.

---

## 2025-12-30

### Added: Dependency Preflight Skill + Auto-Detection Hook

**What:**
- New skill: `/dependency-preflight` for systematic Python import/dependency troubleshooting
- New hook: `import-error-detector` that auto-detects import errors in Bash output

**Why:**
- Analysis of 430+ session learnings showed 60% of git fixes were path/environment related
- Common pattern: `ModuleNotFoundError` appears, user doesn't know diagnostic steps
- Sessions 2243c067, 4784f390, 5e6aada8, 4500e7cd all had similar issues
- Root cause often: uv using different Python version than expected

**How:**

1. **Skill** (`.claude/skills/dependency-preflight/SKILL.md`):
   - Decision tree for diagnosing import errors
   - Commands: `uv run python --version`, `uv pip show <module>`, etc.
   - Covers: ModuleNotFoundError, ImportError, circular imports, pip/uv failures
   - Triggered by keywords: "import error", "module not found", "ModuleNotFoundError"

2. **Hook** (`.claude/hooks/src/import-error-detector.ts`):
   - PostToolUse hook with `"matcher": "Bash"`
   - Regex matches: `ModuleNotFoundError`, `ImportError`, `No module named`
   - Returns system reminder suggesting the skill
   - Latency: ~5ms per Bash call

3. **Registration**:
   - Hook: `.claude/settings.json` → `PostToolUse` section
   - Skill trigger: `.claude/skills/skill-rules.json` → `dependency-preflight`

**Test:**
```bash
echo '{"tool_name": "Bash", "tool_output": "ModuleNotFoundError: No module named pandas"}' \
  | node .claude/hooks/dist/import-error-detector.mjs
```

**Files Created:**
- `.claude/skills/dependency-preflight/SKILL.md`
- `.claude/hooks/src/import-error-detector.ts`
- `.claude/hooks/import-error-detector.sh`
- `.claude/hooks/dist/import-error-detector.mjs`

**Files Modified:**
- `.claude/settings.json` (added hook registration)
- `.claude/skills/skill-rules.json` (added skill trigger)

---

## Template for Future Entries

```markdown
### Added/Changed/Fixed/Removed: [Feature Name]

**What:**
- Brief description of the feature/change

**Why:**
- Problem it solves
- Evidence (session IDs, frequency data, user feedback)
- Root cause if applicable

**How:**
- Implementation details
- Key files and their roles
- How to use/invoke
- Any configuration needed

**Test:**
- How to verify it works

**Files Created:**
- List of new files

**Files Modified:**
- List of changed files
```

---

## Index by Category

### Skills
| Skill | Added | Purpose |
|-------|-------|---------|
| `/dependency-preflight` | 2025-12-30 | Python import/dependency troubleshooting |

### Hooks
| Hook | Event | Added | Purpose |
|------|-------|-------|---------|
| `import-error-detector` | PostToolUse | 2025-12-30 | Auto-detect import errors |

### Rules
| Rule | Added | Purpose |
|------|-------|---------|
| (none yet) | - | - |

---

## How to Use This Changelog

**For Humans:**
- Scan the date headers for recent changes
- Read "What" for quick overview, "Why" for context, "How" for details

**For Claude:**
- Search by feature name or date
- Use "Files Created/Modified" to understand scope
- Reference session IDs in "Why" to trace back to learnings
