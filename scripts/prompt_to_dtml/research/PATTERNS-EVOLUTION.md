# Pattern Evolution: NL to DT+ML Converter

**Document**: How we iterated through different approaches
**Date**: 2025-12-30
**Status**: Research complete

---

## Pattern 1: Skill Upgrader (4-Agent Blackboard)

### What We Built

A parallel research architecture where 4 specialized agents each query different Ragie-indexed books simultaneously, then synthesize findings on a shared blackboard:

- **Agent 1 (LaValle Planner)**: States, actions, transitions (MDP/POMDP structure)
- **Agent 2 (Sutton & Barto)**: Policy, rewards, termination conditions
- **Agent 3 (Blackburn)**: Modal/temporal/deontic constraints
- **Agent 4 (Huth & Ryan)**: Safety/liveness verification

Each agent appends to `00-blackboard.md` without conflicts, then synthesis combines findings into a v5.1 Hybrid skill.

### Result

From the A/B test (`2025-12-30_00-54_skill-upgrader-ab-test-complete.md`):
- 4 books indexed in Ragie (decision-theory + modal-logic partitions)
- Agent 4 verification: 6/6 safety properties passed, 5/6 liveness passed
- Upgraded `create_plan` skill: 485 lines compressed to ~200 lines (59% reduction)
- Real citations: LaValle p.489-511, Sutton p.6-330, Blackburn p.32-504

### Learning

Parallel research with blackboard synthesis works exceptionally well when:
1. Each agent has a distinct domain (no overlap in book partitions)
2. Agents have clear output locations (numbered sections)
3. A final synthesis step combines all findings

The pattern scales: we applied the same workflow to `implement_plan`, `debug`, `tdd`, and `create_handoff` skills.

---

## Pattern 2: Direct NL to Logic Mapping (Naive Keywords)

### What We Tried

Initial attempt: map NL keywords directly to modal operators.

```
"must" → O (obligation)
"always" → G (globally/always in temporal logic)
"never" → G neg (always not)
"knows" → K (epistemic knowledge)
```

### Result

Failed on context-sensitivity. From `theoretical-foundation.md`:

> "must be joking" does not equal O(joking) - different exact verifiers

The phrase "file must exist" is a precondition (different accessibility relation), not a deontic obligation. Classical modal logic cannot distinguish these without semantic context.

### What We Learned

Keyword-based extraction is insufficient. We needed Fine (2012) via Koralus-Mascarenhas: **exact verification semantics** disambiguates modal operators based on what would verify the statement in context, not just surface keywords.

This drove us toward RAG-based verification: authoritative texts provide the formal disambiguation rules.

---

## Pattern 3: RAG-Based Verification (Ragie + Curated PDFs)

### What We Built

Instead of relying on LLM training knowledge (which claims high confidence without verification), we:

1. Uploaded 6 authoritative PDFs to Ragie (2 partitions)
2. Queried Ragie for specific claims before accepting them
3. Distinguished K (knowledge - verified against sources) from B (belief - from LLM training)

From `theoretical-foundation.md` verification table:

| Claim | Status |
|-------|--------|
| Functor preserves identity | K-formal (Barr-Wells p.509-510) |
| DisCoCat grammar-to-semantics | B (Arxiv paper, not in books) |

### Result

Real citations replaced training-derived claims:
- LaValle on MDP: "A K-stage decision-making problem is defined using... a finite state space X" (p.510-511)
- Blackburn on temporal logic: "The intended interpretation of F phi is 'phi will be true at some Future time'" (p.34-35)

### What We Learned

Ragie + curated PDFs beat web search for formal verification because:
- Page-level citations are verifiable
- Partition separation (decision-theory vs modal-logic) enables targeted queries
- The books are authoritative (LaValle, Sutton & Barto, Blackburn, Huth & Ryan)

Key insight: web search returns many sources of variable quality. Curated books return one authoritative source per domain.

---

## Pattern 4: Three-Legged Verification (Source to Claim to Cross-check)

### What We Built

The final verification methodology:

1. **Source**: Query Ragie for specific claim
2. **Claim**: Record what the source says (with page number)
3. **Cross-check**: Query related sources to confirm or refute

Example from erotetic logic verification:

| Step | Action | Result |
|------|--------|--------|
| Source | Query "erotetic implication Wisniewski" | Found IEL framework definition |
| Claim | "E(X, Q) iff X mc-entails dQ, no single answer forced" | Recorded |
| Cross-check | Query "compositional interrogative semantics" | Found QSEM implementation on GitHub |
| Status update | UNCONFIRMED to K-empirical | Confirmed with implementation evidence |

### Result

Upgraded claims from belief to knowledge:
- K-empirical: Implementations exist (QSEM on GitHub, DisCoPy docs)
- K-formal: Proofs exist in sources (Barr-Wells p.509-510 on functor axioms)
- B: Arxiv papers without book verification (still useful, marked appropriately)

### What We Learned

Iterative RAG queries close knowledge gaps. The three-legged pattern forces honest epistemic status: you cannot claim K without citing a source and cross-checking.

---

## What Failed

### 1. Initial Confidence Too High

Early stages assigned 85% confidence to claims. After applying three-legged verification, this dropped to 70% for the logic stage. The gap revealed:
- Training knowledge sounds confident but may be outdated
- "I know this" from LLM is not the same as "Verified against source"

### 2. Imperatives = Questions (Wrong Model)

Initial assumption: "Implement X" is a question that the skill answers.

Correction from Wisniewski's Inferential Erotetic Logic:
> Imperatives are NOT questions - they are DECLARATIVES that EVOKE questions

The transformation rule became:
```
NL Prompt -> {
  Declaratives X: {goal(...), neg current(...)},
  Evoked Q: E(X, Q) via mc-entailment,
  Questions: [Q1...Qn]
}
```

### 3. Context-Sensitivity in Modal Disambiguation

"Must" does not always map to O. From Fine (2012):
- "You must be joking" - epistemic necessity
- "You must file by April" - deontic obligation
- "The file must exist" - precondition (different accessibility relation)

Naive keyword mapping fails without exact verification semantics.

### 4. Ragie API Key Not Auto-Loaded

First run of skill-upgrader fell back to training knowledge because `.env` was not loaded. Fix: add explicit `load_dotenv()` to `scripts/ragie_query.py`. Small bug, but it meant the first A/B comparison used no real citations.

---

## What Worked

### 1. Ragie + Curated PDFs > Web Search

For formal verification, authoritative textbooks with page citations beat web search:
- LaValle Planning Algorithms (decision theory)
- Sutton & Barto RL (policy, rewards)
- Blackburn Modal Logic (K, B, O, F, P operators)
- Huth & Ryan Logic in CS (safety, liveness, CTL)

### 2. K vs B Epistemic Framing

Distinguishing knowledge (K) from belief (B) caught overconfident claims:
- K-formal: Barr-Wells p.509-510 confirms functor preserves identity
- K-empirical: QSEM implementation exists on GitHub
- B: Self-Attention as Endofunctor paper (2025, not in indexed books)

### 3. Parallel Agent Research with Blackboard Synthesis

4-agent pattern achieved:
- No agent conflicts (numbered sections)
- Complete coverage (states, policy, constraints, verification)
- Citations from all 4 books in final output

### 4. User Feedback Loop

The critique that raised new gaps:
- Initial claim: Imperatives ARE questions
- User challenge: "That seems wrong"
- Research: Wisniewski IEL shows imperatives EVOKE questions
- Update: K-empirical status with corrected transformation rule

---

## Final Confidence: 72% (Calibrated)

From `theoretical-foundation.md`:

| Stage | Confidence | Basis |
|-------|------------|-------|
| Erotetic (questions) | 75% | K-empirical: IEL + QSEM implementation |
| Decision Theory | 80% | K-formal: LaValle + Sutton verified |
| Logic Constraints | 70% | K-formal on operators, B on disambiguation rules |
| Categorical Synthesis | 65% | K-formal on functor axioms, B on LLM-as-functor |

**Weighted average**: 72%

This is honest calibration. The 70% for logic constraints reflects that Fine (2012) exact verification semantics is not in the indexed books - it comes from Arxiv papers. We know we need it, but cannot claim K-formal status.

---

## Summary Table

| Pattern | Approach | Result | Key Learning |
|---------|----------|--------|--------------|
| 1. Skill Upgrader | 4-agent blackboard | 84.25% avg confidence | Parallel research + synthesis works |
| 2. Direct NL-Logic | Keyword mapping | Failed on context | Need exact verification semantics |
| 3. RAG Verification | Ragie + PDFs | K vs B distinction | Page citations beat web search |
| 4. Three-Legged | Source-Claim-Crosscheck | UNCONFIRMED to K | Iterative RAG closes gaps |

**Final architecture**: Pattern 1 (parallel agents) + Pattern 3 (Ragie) + Pattern 4 (three-legged verification) = honest 72% confidence with verifiable citations.
