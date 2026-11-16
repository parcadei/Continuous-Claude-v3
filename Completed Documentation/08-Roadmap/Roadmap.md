# Roadmap

## Immediate (next sessions)

1) Batch convert skills >800 tokens using /formalize
- Target: 62 skills
- Categories: Workflow (15), SDK (5), Dev (8), MCP (6), Math (27), Git (1)

2) Archive prose versions
- `mv SKILL.md SKILL.prose.md`
- `mv SKILL.v6.md SKILL.md`

3) Update skill-upgrader
- Replace 4-agent RAG conversion with `/formalize`

4) Wire format selection
- If SKILL.v6.md exists: load it
- Else: load prose

5) A/B test at least one math skill
- Confirm formalization works in symbolic domain
- Archive prose after validation

## Mid-term

- Add CI token measurement checks
- Add v6.0 validator to pre-commit
- Improve prose-on-demand rendering for formal skills
- Document memory + handoff lifecycle as an API contract

## Long-term

- Consolidate inter-agent protocols with HandoffAtom
- Expand decision-theory notation for multi-agent planning
- Benchmark on MATH/miniF2F
- Consolidate skill and handoff formalizations under one schema family

## Migration flow diagram

```
Inventory skills
  → classify by token count
     → convert >800 to v6.0
     → archive prose
     → update router
```
