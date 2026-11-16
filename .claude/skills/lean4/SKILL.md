---
name: lean4
description: "Lean 4 theorem prover with Mathlib for formal verification + Godel-Prover tactic suggestions"
allowed-tools: [Bash, Read, Write]
---

# Lean 4 Formal Verification

Formal theorem proving with Lean 4 and Mathlib for machine-verified proofs.

## Godel-Prover Integration

When LMStudio is running with Godel-Prover-V2-8B loaded, the compiler-in-the-loop hook provides AI-assisted tactic suggestions:

1. **Proof plan prompt**: Chain-of-thought before tactics (APOLLO pattern)
2. **Optimized parameters**: max_tokens=4096, temperature=0.6 for creative tactic exploration
3. **Graceful degradation**: If LMStudio unavailable, continues with manual tactics

To enable Godel-Prover:
1. Install LMStudio from https://lmstudio.ai/
2. Load "Goedel-Prover-V2-8B" model
3. Start local server on port 1234

## CRITICAL: Always Write to File

**ALWAYS write Lean code to a `.lean` file using the Write tool.**
Never output Lean code as text in chat - the compiler-in-the-loop hook only fires on file writes.

```
✓ CORRECT: Write tool → proofs/theorem.lean → hook verifies
✗ WRONG: Output code as markdown in chat → no verification
```

Default location: `proofs/<theorem_name>.lean`

## When to Use

- Abstract math proofs requiring machine verification
- Category theory formalization
- Formal verification of mathematical structures
- Type-theoretic reasoning with dependent types

## Setup

```bash
# Install elan (Lean version manager)
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh

# Create new project with Mathlib
lake new my_project math
cd my_project
lake update
lake build
```

## Core Syntax

### Category Theory Notation

```lean
-- Category declaration
variable {C : Type*} [Category C]

-- Morphism: X ⟶ Y (typed \hom)
variable (f : X ⟶ Y)

-- Composition: f ≫ g (typed \gg, left-to-right)
variable (g : Y ⟶ Z)
#check f ≫ g  -- X ⟶ Z

-- Identity: 𝟙 X (typed \1)
#check 𝟙 X  -- X ⟶ X

-- Functor: C ⥤ D (typed \func)
variable (F : C ⥤ D)
```

### Unicode Input

| Symbol | Input | Meaning |
|--------|-------|---------|
| `⟶` | `\hom` | Morphism |
| `≫` | `\gg` | Composition |
| `𝟙` | `\1` | Identity |
| `⥤` | `\func` | Functor |
| `≅` | `\cong` | Isomorphism |
| `⊗` | `\otimes` | Tensor product |

## Compiler-in-the-Loop Workflow

```bash
# Write proof in MyProof.lean
lake build  # Lean compiler verifies proof
```

The Lean compiler is the verifier. If `lake build` succeeds with no errors, your proof is correct.

## Common Imports

```lean
import Mathlib.CategoryTheory.Category.Basic
import Mathlib.CategoryTheory.Functor.Basic
import Mathlib.CategoryTheory.NatTrans
import Mathlib.CategoryTheory.Limits.Shapes.Products
import Mathlib.CategoryTheory.Monoidal.Basic
import Mathlib.CategoryTheory.Adjunction.Basic
```

## Example: Functor Preserves Identity

```lean
import Mathlib.CategoryTheory.Functor.Basic

open CategoryTheory

example {C D : Type*} [Category C] [Category D]
    (F : C ⥤ D) (X : C) : F.map (𝟙 X) = 𝟙 (F.obj X) := by
  simp [Functor.map_id]
```

## Proof Tactics

| Tactic | Use Case |
|--------|----------|
| `simp` | Simplify with lemmas |
| `exact h` | Provide exact proof term |
| `apply f` | Apply lemma/function |
| `rfl` | Reflexivity |
| `ext` | Extensionality |
| `aesop_cat` | Category theory automation |

## Troubleshooting

| Error | Fix |
|-------|-----|
| `unknown identifier` | Check imports |
| `type mismatch` | Check type signatures |
| `failed to synthesize Category` | Add `[Category C]` instance |
