---
name: skill-developer
description: Meta-skill for creating and managing Claude Code skills
allowed-tools: [Bash, Read, Write, Edit]
---

# Skill Developer

Meta-skill for creating new Claude Code skills, including skills that wrap MCP pipelines.

## When to Use

- "Create a skill for X"
- "Help me make a new skill"
- "Turn this script into a skill"
- "How do I create a skill?"

## Skill Structure

Skills live in `.claude/skills/<skill-name>/`:

```
.claude/skills/my-skill/
├── SKILL.md          # Required: Main skill definition
├── scripts/          # Optional: Supporting scripts
└── templates/        # Optional: Templates, examples
```

### SKILL.md Format

```yaml
---
name: skill-name
description: Brief description (shown in skill list)
allowed-tools: [Bash, Read, Write]  # Optional: restrict tools
---

# Skill Name

## When to Use
[When Claude should discover this skill]

## Instructions
[Step-by-step instructions for Claude to follow]

## Examples
[Usage examples]
```

## Creating an MCP Pipeline Skill

To create a new MCP chain script and wrap it as a skill:

### Step 1: Use the Template

Copy the multi-tool-pipeline template:

```bash
cp $CLAUDE_PROJECT_DIR/scripts/multi_tool_pipeline.py $CLAUDE_PROJECT_DIR/scripts/my_pipeline.py
```

Reference the template pattern:

```bash
cat $CLAUDE_PROJECT_DIR/.claude/skills/multi-tool-pipeline/SKILL.md
cat $CLAUDE_PROJECT_DIR/scripts/multi_tool_pipeline.py
```

### Step 2: Customize the Script

Edit your new script to chain the MCP tools you need:

```python
async def main():
    from runtime.mcp_client import call_mcp_tool
    args = parse_args()

    # Chain your MCP tools (serverName__toolName)
    result1 = await call_mcp_tool("server1__tool1", {"param": args.arg1})
    result2 = await call_mcp_tool("server2__tool2", {"input": result1})

    print(result2)
```

### Step 2: Create the Skill

Create `.claude/skills/my-pipeline/SKILL.md`:

```markdown
---
name: my-pipeline
description: What the pipeline does
allowed-tools: [Bash, Read]
---

# My Pipeline Skill

## When to Use
- [Trigger conditions]

## Instructions

Run the pipeline:

\`\`\`bash
uv run python -m runtime.harness scripts/my_pipeline.py --arg1 "value"
\`\`\`

### Parameters
- `--arg1`: Description

## MCP Servers Required
- server1: For tool1
- server2: For tool2
```

### Step 3: Add Triggers (Optional)

Add to `.claude/skills/skill-rules.json`:

```json
{
  "skills": {
    "my-pipeline": {
      "type": "domain",
      "enforcement": "suggest",
      "priority": "medium",
      "description": "What it does",
      "promptTriggers": {
        "keywords": ["keyword1", "keyword2"],
        "intentPatterns": ["(pattern).*?(match)"]
      }
    }
  }
}
```

## Reference Files

For full details, read:

```bash
cat $CLAUDE_PROJECT_DIR/.claude/rules/skill-development.md
cat $CLAUDE_PROJECT_DIR/.claude/rules/mcp-scripts.md
```

## Quick Checklist

- [ ] SKILL.md has frontmatter (name, description)
- [ ] "When to Use" section is clear
- [ ] Instructions are copy-paste ready
- [ ] MCP servers documented if needed
- [ ] Triggers added to skill-rules.json (optional)

## Examples in This Repo

Look at existing skills for patterns:

```bash
ls $CLAUDE_PROJECT_DIR/.claude/skills/
cat $CLAUDE_PROJECT_DIR/.claude/skills/commit/SKILL.md
cat $CLAUDE_PROJECT_DIR/.claude/skills/exa-search/SKILL.md
```
