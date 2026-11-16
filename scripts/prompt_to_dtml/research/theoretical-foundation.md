# NL→DT+ML Converter: Theoretical Foundation

**Status**: Research complete, verification DONE (2025-12-30)
**Verification**: Three-legged (Ragie books → Claims → Cross-check)
**Date**: 2025-12-30
**Sources**: 6 books (Ragie) + Arxiv papers (Nia)

## Stage 1: Erotetic Analysis (Questions/Presuppositions)

### Core Concepts (K-empirical - implementations exist)
- **Direct Answer**: "just-sufficient possibilities" offered by a question (Wiśniewski)
- **Erotetic Implication**: Q e-implies Q* given X if X + direct answers to Q yield answers to Q*
- **Question Soundness**: For each valuation v, some direct answer A ∈ d(Q) has v(A)=1
- **Compositional Semantics**: Q operator + ? operator (CCG interrogatives)

### Key Papers (VERIFIED with implementations)
| Paper | Claim | Status |
|-------|-------|--------|
| Wiśniewski IEL | Inferential Erotetic Logic framework | K-formal (calculus) |
| ACM TOCL 2017 | Automated erotetic search scenarios | K-empirical (computational) |
| QSEM (CCG) | Compositional interrogative semantics | K-empirical (github.com/hfunakura/qsem) |
| Koralus-Mascarenhas | Erotetic theory of reasoning | K-formal (mental models link) |
| QuestBench (2503.22674) | Task as CSP with missing variables | K - formalizable |
| (QA)² (2212.10003) | Detect questionable assumptions | K - implemented |

### Transformation Rule
```
NL Prompt → {
  Declaratives X: {goal(...), ¬current(...)},  // Imperatives as premises
  Evoked Q: E(X, Q) via mc-entailment,         // Wiśniewski evocation
  Questions: [Q1...Qn],                         // Atomic decomposition
  Presuppositions: [P1...Pm],                   // Existence/context assumptions
  Dependencies: Im(Q, X, Q1)                    // Erotetic implication
}
```

### Key Insight: Imperatives → Evocation
Prompts like "Implement X" are not questions but DECLARATIVES that EVOKE questions:
- E(X, Q) iff: (i) X mc-entails dQ, (ii) no single answer forced
- This bridges imperatives to erotetic logic without treating them as interrogatives

---

## Stage 2: Decision Theory Extraction (MDP/POMDP/BDI)

### Core Concepts (K - verified from LaValle, Sutton&Barto)
- **MDP**: (S, A, T, R, γ) - states, actions, transitions, rewards, discount
- **POMDP**: MDP + (O, b) - observations, belief state
- **BDI**: Beliefs→state estimation, Desires→rewards, Intentions→policy

### Key Papers
| Paper | Claim | Status |
|-------|-------|--------|
| TextWorld (Microsoft) | Logical predicates: `at(fridge, kitchen) ⊗ in(apple, fridge)` | K - implemented |
| LSTM-DQN | Factorized Q: `Q(s, (v,o)) = (Q(s,v) + Q(s,o))/2` | K - validated |
| DRQN | Belief tracking: `bₜ = LSTM(oₜ, bₜ₋₁)` | K - validated |

### Transformation Rule
```
NL Prompt → {
  States (S): Entities + attributes that affect decisions
  Actions (A): Verb + noun_phrase grammar
  Observable: Directly sensed
  Hidden: Must be inferred → POMDP
  Rewards (R): Goal satisfaction mapping
}
```

### POMDP Indicators in NL
- "Understand what user means" → intent hidden
- "Predict whether X" → future hidden
- "Figure out the best Y" → optimal solution unknown

---

## Stage 3: Logic Constraint Extraction

### Core Concepts (K - verified from Blackburn, Huth&Ryan)

| Logic | Operators | Meaning |
|-------|-----------|---------|
| Modal | □, ◇ | Necessity, possibility |
| Epistemic | K, B | Knowledge (factive), belief (may be false) |
| Deontic | O, F, P | Obligation, forbidden, permitted |
| Temporal | G, F, U, X | Always, eventually, until, next |

### Key Papers (HIGH RELEVANCE)
| Paper | Claim | Status |
|-------|-------|--------|
| OLG++ (2507.05488) | Graph-based obligation representation | K - implemented |
| Deontic Temporal Logic (2501.05765) | O/F/P + temporal operators for AI | K - formal semantics |
| NL-to-FOL (ACL 2024) | LLM prompting for formalization | K - validated |
| LINC (2310.15164) | LLM + external prover verification | K - architecture pattern |
| ODRL (W3C) | Standard vocabulary for deontic | K - established standard |

### NL → Logic Mapping (verified, but context-sensitive)
| NL Keyword | Logic | Operator | Disambiguation |
|------------|-------|----------|----------------|
| must/required | Deontic | O | vs precondition (exact verifiers differ) |
| should | Deontic (soft) | O (lower penalty) | |
| always/invariant | Temporal | G | |
| never | Temporal | G¬ | |
| eventually | Temporal | F | |
| until | Temporal | U | |
| knows | Epistemic | K | factive (implies truth) |
| believes | Epistemic | B | non-factive (may be false) |
| can/may | Deontic | P | |
| forbidden/cannot | Deontic | F | |

### Key Insight: Exact Verification for Disambiguation
From Fine (2012) via Koralus-Mascarenhas:
- "must be joking" ≠ O(joking) → different exact verifiers
- "file must exist" = precondition → □(exists) in different accessibility relation
- Classical modal logic can't distinguish; exact verification can

### Transformation Rule
```
NL Prompt → {
  Temporal: [G(invariants), F(goals), φ U ψ (ordering)],
  Deontic: [O(musts), F(forbids), P(mays)],
  Epistemic: [K(known_facts), B(user_claims)]
}
```

---

## Stage 4: Categorical Synthesis (Functor Application)

### Core Concepts (K - verified from Barr-Wells, Pierce via Ragie)
- **Functor F: C→D** preserves: identity, composition, endpoints ✓ (Barr-Wells p.509-510)
- **Natural Transformation**: Coherent rewiring between functors ✓ (Barr-Wells p.126-127)
- **Adjoint (Free/Forgetful)**: Optimal/canonical construction ✓ (Pierce p.60-61)

### Key Papers (K-empirical/K-formal - Ragie indexed 2025-12-30)
| Paper | Claim | Status |
|-------|-------|--------|
| DisCoPy (2311.10608) | Python toolkit for monoidal categories, Functor.apply() | K-empirical (docs.discopy.org) |
| Self-Attention as Endofunctor (2501.02931) | Transformers are morphisms in Para(Vect), free monad | K-formal (proof) |
| Effect Functors (2504.00316) | Effects handle scope ambiguity, Hamblin semantics link | K-formal |
| DisCoCat (1003.4394) | Functors lift grammar→semantics | K-empirical (700+ citations) |
| DisCoCirc (1904.03478) | Document-level gates updating meanings | K-empirical |

### Key Implementation Insight
From Self-Attention paper: "Self-attention components as morphisms in Para(Vect)" means using an LLM AS the functor in Stage 4 is theoretically justified - transformers preserve categorical structure.

### Functor Axioms for Converter
```
C: NL-Prompt → DT+ML-Skill

F-1: Endpoint preservation
     If p₁→p₂ (refinement), then C(p₁)→C(p₂) (skill transformation)

F-2: Identity preservation
     C(id_prompt) = id_C(prompt)

F-3: Composition preservation
     C(g∘f) = C(g)∘C(f)
```

### Structure to Preserve
- **Semantic content**: Meaning of prompt = meaning of skill
- **Ambiguity handling**: Multiple interpretations → density matrices
- **Refinement ordering**: Prompt specializations → skill transformations

---

## Verification Summary (Three-Legged: 2025-12-30)

### Factive Knowledge (K) - Verified via Ragie
- [x] MDP/POMDP formalization (textbook definitions match papers)
- [x] Modal/deontic/temporal operators (formal semantics consistent)
- [x] Functor preserves identity (Barr-Wells p.509-510: "F(idC) is the identity")
- [x] Functor preserves composition (Barr-Wells p.509-510: "Ff(u′∘u) = Ff(u′)∘Ff(u)")
- [x] Functor preserves endpoints (Barr-Wells p.99-100: "preserve source and target")
- [x] Adjoint = Free/Forgetful pattern (Pierce p.60-61: confirmed)
- [x] Natural transformation = arrows between functors (Barr-Wells p.126-127)
- [x] NL→logic keyword mapping (multiple sources agree)

### Belief (B) - From Arxiv Papers, NOT in Ragie Books
- [~] DisCoCat "functors lift grammar→semantics" (Arxiv 1003.4394, not in Pierce/Barr-Wells)
- [~] Self-Attention as Endofunctor (Arxiv 2501.02931, 2025 paper)
- [~] Effect functors for impure meanings (Arxiv 2504.00316, 2025 paper)

### K-empirical - Now Verified (2025-12-30 erotetic PDF upload)
- [x] Erotetic logic → IEL framework (Wiśniewski), QSEM implementation (GitHub)
- [x] Compositional interrogative semantics → CCG + theorem prover approach
- [~] CSP formulation completeness (QuestBench is recent, but formalizable)

### Open Questions
1. How to handle B(user_claim) that contradicts K(fact)?
2. What's the minimal presupposition set for prompt coherence?
3. How to preserve multiple readings until disambiguation forced?

---

## Implementation Architecture

```
scripts/prompt_to_dtml/
├── research/
│   └── theoretical-foundation.md  ← YOU ARE HERE
├── converter.py                   # Main entry point
├── stages/
│   ├── erotetic.py               # Stage 1: Question decomposition
│   ├── decision_theory.py        # Stage 2: MDP/POMDP extraction
│   ├── logic_constraints.py      # Stage 3: Modal/deontic/temporal
│   └── synthesizer.py            # Stage 4: Functor application
├── templates/
│   └── skill_v51.py              # v5.1 Hybrid template
└── tests/
    ├── test_erotetic.py
    ├── test_decision_theory.py
    ├── test_logic_constraints.py
    └── test_synthesizer.py
```

## Next Steps

1. Three-legged verification (Read → Verify → Confirm K vs B)
2. TDD: Write tests for each stage
3. Implement stages bottom-up
4. Integration test on real NL skill
