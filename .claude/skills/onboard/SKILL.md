# Onboard - Project Discovery & Ledger Creation

Analyze a brownfield codebase and create an initial continuity ledger.

## When to Use

- First time working in an existing project
- User says "onboard", "analyze this project", "get familiar with codebase"
- After running `init-project.sh` in a new project

## Process

### Step 1: Check Prerequisites

```bash
# Verify thoughts/ structure exists
ls thoughts/ledgers/ 2>/dev/null || echo "Run init-project.sh first"
```

### Step 2: Codebase Analysis

**If repoprompt available (preferred):**
Use rp-explorer agent for token-efficient codebase mapping.

**Fallback (no repoprompt):**
Analyze manually:

```bash
# Project structure
find . -maxdepth 3 -type f \( -name "*.md" -o -name "package.json" -o -name "pyproject.toml" -o -name "Cargo.toml" -o -name "go.mod" -o -name "Gemfile" -o -name "*.csproj" \) 2>/dev/null | head -20

# Key directories
ls -la src/ app/ lib/ packages/ 2>/dev/null | head -30

# README content
head -100 README.md 2>/dev/null
```

### Step 3: Detect Tech Stack

Look for and summarize:
- **Language**: package.json (JS/TS), pyproject.toml (Python), Cargo.toml (Rust), go.mod (Go)
- **Framework**: Next.js, Django, Rails, etc.
- **Database**: prisma/, migrations/, .env references
- **Testing**: jest.config, pytest.ini, test directories
- **CI/CD**: .github/workflows/, .gitlab-ci.yml

### Step 4: Ask User for Goal

Use AskUserQuestion tool:

```
Question: "What's your primary goal working on this project?"
Options:
- "Add new feature"
- "Fix bugs / maintenance"
- "Refactor / improve architecture"
- "Learn / understand codebase"
```

Then ask:
```
Question: "Any specific constraints or patterns I should follow?"
Options:
- "Follow existing patterns"
- "Check CONTRIBUTING.md"
- "Ask me as we go"
```

### Step 5: Generate Continuity Ledger

Create ledger at: `thoughts/ledgers/CONTINUITY_CLAUDE-<project-name>.md`

Template:
```markdown
# Session: <project-name>
Updated: <timestamp>

## Goal
<User's stated goal from Step 4>

## Constraints
- Tech Stack: <detected>
- Framework: <detected>
- Patterns: <from CONTRIBUTING.md or user input>

## Key Decisions
(None yet - will be populated as decisions are made)

## State
- Now: [→] Initial exploration
- Next: <based on goal>

## Working Set
- Key files: <detected entry points>
- Test command: <detected>
- Build command: <detected>

## Open Questions
- UNCONFIRMED: <any uncertainties from analysis>
```

### Step 6: Confirm with User

Show the generated ledger and ask:
- "Does this look accurate?"
- "Anything to add or correct?"

## Output

- Continuity ledger created at `thoughts/ledgers/CONTINUITY_CLAUDE-<name>.md`
- User has clear starting context
- Ready to begin work with full project awareness

## Notes

- This skill is for BROWNFIELD projects (existing code)
- For greenfield, use `/create_plan` instead
- Ledger can be updated anytime with `/continuity_ledger`
