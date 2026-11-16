# Router-First Architecture

Route through domain routers before using individual tools. Routers abstract tool selection.

## Pattern

Domain routers (like `math-router`) provide deterministic mapping from user intent to exact CLI commands. Always use the router first; only bypass for edge cases.

## DO

- Call `math-router route "<intent>"` before any math operation
- Let domain skills co-activate with their router (via `coActivate` in skill-rules.json)
- Trust the router's confidence score; only fall back if `command: null`
- Keep trigger keywords/patterns in skill-rules.json broader than routing patterns

## DON'T

- Call individual scripts directly when a router exists
- Duplicate routing logic in individual skills
- Let domain skills bypass their router

## Co-Activation Pattern

Domain skills should co-activate with their router:

```json
{
  "math/abstract-algebra/groups": {
    "coActivate": ["math-router"],
    "coActivateMode": "always"
  }
}
```

This ensures the router is always available when domain knowledge is activated.

## Two-Layer Architecture

1. **Skill-rules trigger layer**: Nudges Claude to use the router (keywords, intent patterns)
2. **Router routing layer**: Deterministic mapping to scripts via regex patterns

Keep the trigger layer broader than routing - the router should handle "not found" gracefully.

## Source Sessions

- 2bbc8d6e: "Trigger layer was narrower than routing layer" - expanded triggers
- This session: Wired 8 domain math skills to co-activate with math-router
