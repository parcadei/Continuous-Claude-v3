---
name: agentica-spawn
description: Spawn Agentica multi-agent patterns
---

# Agentica Spawn Skill

Use this skill after user selects an Agentica pattern.

## When to Use

- After agentica-orchestrator prompts user for pattern selection
- When user explicitly requests a multi-agent pattern (swarm, hierarchical, etc.)
- When implementing complex tasks that benefit from parallel agent execution
- For research tasks requiring multiple perspectives (use Swarm)
- For implementation tasks requiring coordination (use Hierarchical)
- For iterative refinement (use Generator/Critic)
- For high-stakes validation (use Jury)

## Pattern Selection to Spawn Method

### Swarm (Research/Explore)
```python
swarm = Swarm(
    perspectives=[
        "Security expert analyzing for vulnerabilities",
        "Performance expert optimizing for speed",
        "Architecture expert reviewing design"
    ],
    aggregate_mode=AggregateMode.MERGE,
)
result = await swarm.execute(task_description)
```

### Hierarchical (Build/Implement)
```python
hierarchical = Hierarchical(
    coordinator_premise="You break tasks into subtasks",
    specialist_premises={
        "planner": "You create implementation plans",
        "implementer": "You write code",
        "reviewer": "You review code for issues"
    },
)
result = await hierarchical.execute(task_description)
```

### Generator/Critic (Iterate/Refine)
```python
gc = GeneratorCritic(
    generator_premise="You generate solutions",
    critic_premise="You critique and suggest improvements",
    max_rounds=3,
)
result = await gc.run(task_description)
```

### Jury (Validate/Verify)
```python
jury = Jury(
    num_jurors=5,
    consensus_mode=ConsensusMode.MAJORITY,
    premise="You evaluate the solution"
)
verdict = await jury.decide(bool, question)
```

## Environment Variables

All spawned agents receive:
- `SWARM_ID`: Unique identifier for this swarm run
- `AGENT_ROLE`: Role within the pattern (coordinator, specialist, etc.)
- `PATTERN_TYPE`: Which pattern is running
