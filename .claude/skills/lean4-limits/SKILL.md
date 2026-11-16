---
name: lean4-limits
description: "Lean 4 Mathlib: Limits, colimits, products, coproducts"
allowed-tools: [Bash, Read, Write]
---

# Lean 4 Limits Skill

Mathlib categorical limits and colimits reference.

## When to Use

- Working with products/coproducts in category theory
- Constructing universal cones and cocones
- Proving properties using limit/colimit universality

## Products

```lean
-- Product notation
∏ᶜ f         -- Product object (piObj)
Pi.π f b     -- Projection: ∏ᶜ f ⟶ f b
Pi.lift p    -- Universal: given p : ∀ b, P ⟶ f b, get P ⟶ ∏ᶜ f
```

## Coproducts

```lean
-- Coproduct notation
∐ f           -- Coproduct object (sigmaObj)
Sigma.ι f b   -- Injection: f b ⟶ ∐ f
Sigma.desc p  -- Universal: given p : ∀ b, f b ⟶ X, get ∐ f ⟶ X
```

## Type Classes

```lean
[HasProduct f]      -- Product exists
[HasCoproduct f]    -- Coproduct exists
[HasLimits C]       -- All limits exist
[HasColimits C]     -- All colimits exist
```

## Fan/Cofan Construction

```lean
Fan.mk P p      -- Create product cone (P apex, p projections)
Cofan.mk P p    -- Create coproduct cocone
```

## Universal Property

```lean
-- Morphisms into products determined by projections
Pi.hom_ext : (∀ b, g₁ ≫ Pi.π f b = g₂ ≫ Pi.π f b) → g₁ = g₂
```

## Example

```lean
import Mathlib.CategoryTheory.Limits.Shapes.Products

variable {C : Type*} [Category C] [HasProducts C]
variable {β : Type*} (f : β → C)

-- Use product projection
example (b : β) : ∏ᶜ f ⟶ f b := Pi.π f b
```

## Key Imports

```lean
import Mathlib.CategoryTheory.Limits.Shapes.Products
import Mathlib.CategoryTheory.Limits.Shapes.BinaryProducts
import Mathlib.CategoryTheory.Limits.HasLimits
```
