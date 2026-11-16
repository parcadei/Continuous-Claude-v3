---
globs: [".claude/skills/**/*"]
---

# Skill Development Rules

When working with files in `.claude/skills/`:

## SKILL.md Structure

```yaml
---
name: skill-name
description: Brief description
allowed-tools: [Bash, Read]  # Optional: restrict tools
---
```

## DO
- Keep SKILL.md concise (< 200 lines)
- Include clear "When to Use" section
- Provide copy-paste bash commands
- Reference scripts/ for MCP operations
- Add triggers to skill-rules.json

## DON'T
- Include implementation details in SKILL.md
- Duplicate content across skills
- Create skills without corresponding trigger in skill-rules.json
- Use allowed-tools that aren't needed

## MCP Wrapper Skills
For skills that wrap MCP scripts:
- Use `allowed-tools: [Bash, Read]` to restrict capabilities
- Point to the script in scripts/ directory
- Include parameter documentation
