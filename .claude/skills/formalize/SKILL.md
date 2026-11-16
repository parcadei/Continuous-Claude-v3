---
name: formalize
description: Convert prose skills to v6.0 formal logic format (MDP + modal logic)
allowed-tools: [Read, Write, Task]
---

# Formalize

Convert prose SKILL.md files to v6.0 formal specification using decision theory and modal logic.

## When to Use

- "formalize this skill"
- "convert to v6.0"
- "add formal logic to this skill"
- Converting skills >800 tokens (where compression helps)

## Conversion Patterns

### I - Initiation
Extract from "When to Use" section:
```
activate: [trigger words/phrases from prose]
skip: [anti-patterns, "don't use when"]
```

### Y - Observation Space
Extract from environment/input sections:
```
| signal | source | interpretation |
```

### U - Action Space
From frontmatter + context:
```
primary: [allowed-tools from YAML]
forbidden: [infer from "never do X"]
```

### pi - Policy
Extract from "Process Steps" or decision trees:
```
eta |-> action if condition
Q-values: HIGH (preferred) / MED / LOW / -inf (forbidden)
```

### beta - Termination
Infer from implicit success/failure:
```
beta(eta) = 1.0 if terminal_condition
success: [done conditions]
failure: [abort conditions]
```

### Constraints
Extract from "Important Notes" or rules:
```
Deontic: O(obligated), F(forbidden), P(permitted)
Temporal: □(always), ◇(eventually)
```

### Verification
Add checklist:
```
| property | formula | check |
| safety | □¬(bad) | ✓/✗ |
| liveness | ◇(good) | ✓/✗ |
```

## Output Template

```markdown
---
name: {skill_name}
version: 6.0
description: {description}
---

# {Skill Name}

## I (Initiation)
activate: [...]
skip: [...]

## Y (Observation Space)
| signal | source | interpretation |

## U (Action Space)
primary: [...]
forbidden: [...]

## pi (Policy)
eta |-> action if condition

| action | Q | why |

## beta (Termination)
success: [...]
failure: [...]

## Invariants
inv_1: □(rule)
```

## Usage

```bash
# Read skill, apply patterns, write v6.0 version
Read original -> Apply patterns -> Write to SKILL.v6.md
```
