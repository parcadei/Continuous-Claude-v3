---
name: prove
description: Formal theorem proving with research, testing, and verification phases
triggers: ["prove", "verify", "show that", "is it true", "formalize"]
allowed-tools: [Bash, Read, Write, Edit, WebSearch, WebFetch, AskUserQuestion, Grep, Glob]
priority: high
---

# /prove - Machine-Verified Proofs (5-Phase Workflow)

**For mathematicians who want verified proofs without learning Lean syntax.**

## Prerequisites

Before using this skill, check Lean4 is installed:

```bash
# Check if lake is available
command -v lake &>/dev/null && echo "Lean4 installed" || echo "Lean4 NOT installed"
```

**If not installed:**
```bash
# Install elan (Lean version manager)
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh

# Restart shell, then verify
lake --version
```

First run of `/prove` will download Mathlib (~2GB) via `lake build`.

## Usage

```
/prove every group homomorphism preserves identity
/prove Monsky's theorem
/prove continuous functions on compact sets are uniformly continuous
```

## The 5-Phase Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  📚 RESEARCH → 🏗️ DESIGN → 🧪 TEST → ⚙️ IMPLEMENT → ✅ VERIFY  │
└─────────────────────────────────────────────────────────────┘
```

### Phase 1: RESEARCH (before any Lean)

**Goal:** Understand if/how this can be formalized.

1. **Search Mathlib with Loogle** (PRIMARY - type-aware search)
   ```bash
   # Use loogle for type signature search - finds lemmas by shape
   loogle-search "pattern_here"

   # Examples:
   loogle-search "Nontrivial _ ↔ _"           # Find Nontrivial lemmas
   loogle-search "(?a → ?b) → List ?a → List ?b"  # Map-like functions
   loogle-search "IsCyclic, center"           # Multiple concepts
   ```

   **Query syntax:**
   - `_` = any single type
   - `?a`, `?b` = type variables (same var = same type)
   - `Foo, Bar` = must mention both

2. **Search External** - What's the known proof strategy?
   - Use Nia MCP if available: `mcp__nia__search`
   - Use Perplexity MCP if available: `mcp__perplexity__search`
   - Fall back to WebSearch for papers/references
   - Check: Is there an existing formalization elsewhere (Coq, Isabelle)?

3. **Identify Obstacles**
   - What lemmas are NOT in Mathlib?
   - Does proof require axioms beyond ZFC? (Choice, LEM, etc.)
   - Is the statement even true? (search for counterexamples)

4. **Output:** Brief summary of proof strategy and obstacles

**CHECKPOINT:** If obstacles found, use AskUserQuestion:
- "This requires [X]. Options: (a) restricted version, (b) accept axiom, (c) abort"

### Phase 2: DESIGN (skeleton with sorries)

**Goal:** Build proof structure before filling details.

1. Create Lean file with:
   - Imports
   - Definitions needed
   - Main theorem statement
   - Helper lemmas as `sorry`

2. Annotate each sorry:
   ```lean
   -- SORRY: needs proof (straightforward)
   -- SORRY: needs proof (complex - ~50 lines)
   -- AXIOM CANDIDATE: v₂ constraint - will test in Phase 3
   ```

3. Verify skeleton compiles (with sorries)

**Output:** `proofs/<theorem_name>.lean` with annotated structure

### Phase 3: TEST (counterexample search)

**Goal:** Catch false lemmas BEFORE trying to prove them.

For each AXIOM CANDIDATE sorry:

1. **Generate test cases**
   ```lean
   -- Create #eval or example statements
   #eval testLemma (randomInput1)  -- should return true
   #eval testLemma (randomInput2)  -- should return true
   ```

2. **Run tests**
   ```bash
   lake env lean test_lemmas.lean
   ```

3. **If counterexample found:**
   - Report the counterexample
   - Use AskUserQuestion: "Lemma is FALSE. Options: (a) restrict domain, (b) reformulate, (c) abort"

**CHECKPOINT:** Only proceed if all axiom candidates pass testing.

### Phase 4: IMPLEMENT (fill sorries)

**Goal:** Complete the proofs.

Standard iteration loop:
1. Pick a sorry
2. Write proof attempt
3. Compiler-in-the-loop checks (hook fires automatically)
4. If error, Godel-Prover suggests fixes
5. Iterate until sorry is filled
6. Repeat for all sorries

**Tools active:**
- compiler-in-the-loop hook (on every Write)
- Godel-Prover suggestions (on errors)

### Phase 5: VERIFY (audit)

**Goal:** Confirm proof quality.

1. **Axiom Audit**
   ```bash
   lake build && grep "depends on axioms" output
   ```
   - Standard: propext, Classical.choice, Quot.sound ✓
   - Custom axioms: LIST EACH ONE

2. **Sorry Count**
   ```bash
   grep -c "sorry" proofs/<file>.lean
   ```
   - Must be 0 for "complete" proof

3. **Generate Summary**
   ```
   ✓ MACHINE VERIFIED (or ⚠️ PARTIAL - N axioms)

   Theorem: <statement>
   Proof Strategy: <brief description>

   Proved:
   - <lemma 1>
   - <lemma 2>

   Axiomatized (if any):
   - <axiom>: <why it's needed>

   File: proofs/<name>.lean
   ```

## Research Tool Priority

Use whatever's available, in order:

| Tool | Best For | Command |
|------|----------|---------|
| **Loogle** | Type signature search (PRIMARY) | `loogle-search "pattern"` |
| Nia MCP | Library documentation | `mcp__nia__search` |
| Perplexity MCP | Proof strategies, papers | `mcp__perplexity__search` |
| WebSearch | General references | WebSearch tool |
| WebFetch | Specific paper/page content | WebFetch tool |

**Loogle setup:** Requires `~/.local/share/loogle` with Mathlib index. Run `loogle-server &` for fast queries.

If no search tools available, proceed with caution and note "research phase skipped".

## Checkpoints (automatic)

The workflow pauses for user input when:
- ⚠️ Research finds obstacles
- ❌ Testing finds counterexamples
- 🔄 Implementation hits unfillable sorry after N attempts

## Output Format

```
┌─────────────────────────────────────────────────────┐
│ ✓ MACHINE VERIFIED                                  │
│                                                     │
│ Theorem: ∀ φ : G →* H, φ(1_G) = 1_H                │
│                                                     │
│ Proof Strategy: Direct application of              │
│ MonoidHom.map_one from Mathlib.                    │
│                                                     │
│ Phases:                                             │
│   📚 Research: Found in Mathlib.Algebra.Group.Hom  │
│   🏗️ Design: Single lemma, no sorries needed       │
│   🧪 Test: N/A (trivial)                           │
│   ⚙️ Implement: 3 lines                            │
│   ✅ Verify: 0 custom axioms, 0 sorries            │
│                                                     │
│ File: proofs/group_hom_identity.lean               │
└─────────────────────────────────────────────────────┘
```

## What I Can Prove

| Domain | Examples |
|--------|----------|
| Category Theory | Functors, natural transformations, Yoneda |
| Abstract Algebra | Groups, rings, homomorphisms |
| Topology | Continuity, compactness, connectedness |
| Analysis | Limits, derivatives, integrals |
| Logic | Propositional, first-order |

## Limitations

- Complex proofs may take multiple iterations
- Novel research-level proofs may exceed capabilities
- Some statements are unprovable over ℚ (need ℝ extension)

## Behind The Scenes

- **Lean 4.26.0** - Theorem prover
- **Mathlib** - 100K+ formalized theorems
- **Godel-Prover** - AI tactic suggestions (via LMStudio)
- **Compiler-in-the-loop** - Automatic verification on every write
- **Research tools** - Nia, Perplexity, WebSearch (graceful degradation)

## See Also

- `/loogle-search` - Search Mathlib by type signature (used in Phase 1 RESEARCH)
- `/math-router` - For computation (integrals, equations)
- `/lean4` - Direct Lean syntax access
