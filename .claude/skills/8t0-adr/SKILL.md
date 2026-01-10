---
name: 8t0-adr
description: Create Architecture Decision Record using MADR 4.0 format. Documents significant technical decisions with context, alternatives, and consequences.
user-invocable: true
keywords: [adr, architecture, decision, madr]
---

# Architecture Decision Record

<purpose>
Document architectural decisions with:
- Context and problem statement
- Decision made
- Alternatives considered
- Consequences (positive/negative)
- Links to related specs and code
</purpose>

<when_to_create>
- Choosing between technologies
- Defining integration patterns
- Security architecture decisions
- Performance optimization approaches
- Breaking changes or migrations
- Any decision with significant tradeoffs
</when_to_create>

<rules>
1. Always interview for context before writing
2. Include at least 2 alternatives considered
3. Document both positive AND negative consequences
4. Link to related code/specs when applicable
5. Use consistent status lifecycle
</rules>

<workflow>

## Step 1: Check Memory for Pending ADRs

Query memory system for OPEN_THREAD entries with ADR-related tags:
```bash
(cd $CLAUDE_PROJECT_DIR/opc && PYTHONPATH=. uv run python scripts/core/recall_learnings.py --query "ADR architecture decision" --k 5 --text-only)
```

If found, present: "Found N architectural discussions to potentially document."

## Step 2: Determine Topic

If topic provided as argument, use it.
Otherwise, use AskUserQuestion: "What decision needs documenting?"

Topic extraction hints:
- "should we use X" → "X-evaluation"
- "deciding between X and Y" → "X-vs-Y"
- "trade-off" discussion → extract main subject

## Step 3: Determine Next ADR Number

Read `docs/adr/` directory to find highest existing number.
New ADR = highest + 1 (or 0001 if first).

## Step 4: Gather Context

Use AskUserQuestion to gather:
- What problem are we solving?
- What options were considered?
- What constraints exist?
- Who are the stakeholders?

## Step 5: Create ADR File

Create `docs/adr/NNNN-[topic].md`:

```markdown
# ADR-NNNN: [Title]

**Status**: Proposed
**Date**: [today]
**Module**: [module-id or "Cross-cutting"]
**Deciders**: [user], Claude

## Context

[Why this decision is needed. What forces are at play.]

## Decision

[What we decided to do.]

## Consequences

### Positive
- [benefit]

### Negative
- [tradeoff we accept]

### Risks
- [risk]: [mitigation]

## Alternatives Considered

| Option | Pros | Cons | Why Rejected |
|--------|------|------|--------------|
| [option] | [pros] | [cons] | [reason] |

## Related

- Specs: [links to affected SPEC.md files]
- ADRs: [links to related ADRs]
- Code: [file paths once implemented]
```

## Step 6: Update Index

Add entry to `docs/adr/README.md` (create if missing):

```markdown
| NNNN | [Title] | Proposed | [date] |
```

## Step 7: Link from Specs

If ADR relates to a module, update that module's SPEC.md:
- Add ADR reference to relevant requirements

</workflow>

<status_lifecycle>
- **Proposed**: Under discussion
- **Accepted**: Approved for implementation
- **Deprecated**: No longer applies (replaced or obsolete)
- **Superseded by ADR-XXXX**: Replaced by newer decision
</status_lifecycle>

<question_quality>
BAD (too vague):
- "What database should we use?"
- "Is this a good approach?"

GOOD (specific tradeoffs):
- "We're choosing between PostgreSQL (mature, SQL) and MongoDB (flexible schema). Given our data is relational but schemas may evolve, which fits better?"
- "Should we use REST (simpler) or GraphQL (flexible queries) for the API? Our frontend needs vary by page."
</question_quality>

<success_criteria>
- ADR created with full template
- README.md index updated (if exists)
- Related specs linked (if applicable)
- At least 2 alternatives documented
- Consequences include both pros and cons
</success_criteria>
