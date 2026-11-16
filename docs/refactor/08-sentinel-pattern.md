# Module: Sentinel Pattern

## Overview

Sentinel is a **first-class pattern** (not an overlay). It spawns a dedicated agent that monitors other agents via blackboard polling, sends corrections, and can block problematic actions.

---

## Pattern Definition

```python
# scripts/agentica_patterns/patterns/sentinel.py

@dataclass
class SentinelPattern:
    """
    Quality monitoring pattern.

    Spawns a sentinel agent that:
    1. Polls blackboard every N seconds
    2. Cross-references agent outputs against quality criteria
    3. Posts directives to correct/stop problematic agents
    """

    check_interval: int = 30  # seconds
    quality_criteria: list[str] = field(default_factory=list)
    can_block: bool = True  # Can sentinel block agent actions?

    async def execute(
        self,
        monitored_agents: list[SpawnedAgent],
        criteria: list[str],
    ) -> None:
        """Spawn sentinel to monitor agents."""

        sentinel_prompt = f"""
You are a SENTINEL agent. Your job is to monitor other agents and ensure quality.

CHECK INTERVAL: Every {self.check_interval} seconds, review the blackboard for agent updates.

QUALITY CRITERIA:
{chr(10).join(f'- {c}' for c in criteria)}

ACTIONS:
1. If an agent's output violates criteria, post a DIRECTIVE to the blackboard targeting that agent.
2. If critical issues found, post a BROADCAST to pause all agents.
3. Log your checks to the blackboard with message_type='status'.

OUTPUT FORMAT:
When posting to blackboard, use JSON:
{{
  "message_type": "directive",
  "target_agent": "agent-uuid or null for broadcast",
  "payload": {{
    "action": "correct|pause|stop",
    "message": "Explanation of issue and required fix"
  }}
}}
"""

        sentinel = spawn_agent(
            prompt=sentinel_prompt,
            perspective="Quality Sentinel",
            allowed_tools=["Read", "Grep", "Bash"],  # Bash for blackboard CLI
        )

        # Sentinel runs until all monitored agents complete
        await wait_for_all(monitored_agents)

        # Signal sentinel to stop
        await post_to_blackboard(
            swarm_id=os.environ.get("SWARM_ID"),
            message_type="status",
            payload={"action": "sentinel_stop", "reason": "All monitored agents completed"}
        )
```

---

## Blackboard Integration

### Sentinel Posts Directives

```python
async def post_directive(
    target_agent: str | None,
    action: str,
    message: str,
) -> None:
    """Post a directive to the blackboard."""

    await pool.execute("""
        INSERT INTO blackboard (swarm_id, sender_agent, message_type, target_agent, payload)
        VALUES ($1, $2, 'directive', $3, $4)
    """,
        os.environ.get("SWARM_ID"),
        os.environ.get("AGENT_ID"),
        target_agent,
        json.dumps({"action": action, "message": message})
    )
```

### Agents Check for Directives

The PreToolUse hook (write-path only) checks for directives:

```typescript
// In blackboard-poll.ts
const directive = messages.find(m =>
    m.message_type === 'directive' &&
    (m.target_agent === agentId || m.target_agent === null) &&
    !m.read_by.includes(agentId)
);

if (directive) {
    // Mark as read
    await markAsRead(directive.id, agentId);

    if (directive.payload.action === 'stop') {
        return { result: 'block', reason: `Sentinel stop: ${directive.payload.message}` };
    }

    if (directive.payload.action === 'correct') {
        return {
            result: 'continue',
            message: `[SENTINEL CORRECTION]\n${directive.payload.message}\n\nPlease address this before continuing.`
        };
    }
}
```

---

## When to Use Sentinel

| Scenario | Use Sentinel? | Rationale |
|----------|---------------|-----------|
| Research Swarm | **Yes** | Catch agents going off-topic |
| Code Implementation | **Yes** | Catch security issues, bad patterns |
| Jury Voting | No | Jurors are isolated by design |
| Simple Pipeline | No | Sequential, easy to verify |
| High-Stakes Decision | **Yes** | Extra quality layer |

### Triggering in skill-rules.json

```json
{
  "sentinel-pattern": {
    "type": "orchestration",
    "enforcement": "suggest",
    "priority": "high",
    "description": "Spawn sentinel to monitor agent quality",
    "promptTriggers": {
      "keywords": ["sentinel", "monitor agents", "quality check", "watch agents"],
      "intentPatterns": [
        "(spawn|run|use).*sentinel",
        "monitor.*(agents|swarm)",
        "quality.*(check|control)"
      ]
    }
  }
}
```

---

## Sentinel Criteria Examples

### Code Quality Sentinel

```python
criteria = [
    "No hardcoded secrets or API keys",
    "All functions have error handling",
    "No TODO comments left in production code",
    "Type annotations on all public functions",
    "Tests written for new functions",
]
```

### Research Quality Sentinel

```python
criteria = [
    "Claims backed by citations",
    "No obvious factual errors",
    "Stays on topic (related to original query)",
    "No duplicate findings already posted by other agents",
]
```

---

## Sentinel Sub-Agent Spawning

Sentinels can spawn sub-agents for deeper analysis:
- Respects depth limit (max 3 levels)
- Sub-sentinels for investigating suspicious findings
- Must post findings to blackboard regardless

```python
async def sentinel_deep_analysis(finding: Finding) -> Analysis:
    """Spawn sub-sentinel for deeper investigation."""
    if get_current_depth() >= 3:
        # At depth limit, escalate to orchestrator
        await post_to_blackboard("escalate", finding)
        return None

    sub_sentinel = spawn_agent(
        prompt=f"Investigate this finding in depth: {finding}",
        perspective="Deep Analysis Sentinel",
        allowed_tools=["Read", "Grep", "Glob"],
    )
    return await wait_for_agent(sub_sentinel)
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/agentica_patterns/patterns/sentinel.py` | Sentinel pattern implementation |
| `.claude/skills/sentinel-pattern/SKILL.md` | Skill for triggering sentinel |

## Files to Modify

| File | Changes |
|------|---------|
| `.claude/skills/skill-rules.json` | Add sentinel triggers |
| `.claude/hooks/src/blackboard-poll.ts` | Handle sentinel directives |
