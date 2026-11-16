---
name: lean4-functors
description: "Lean 4 Mathlib: Functors and category morphisms"
allowed-tools: [Bash, Read, Write]
---

# Lean 4 Functors

Functors are structure-preserving maps between categories.

## Functor Structure

```lean
structure Functor (C : Type u₁) [Category.{v₁} C]
    (D : Type u₂) [Category.{v₂} D] where
  obj : C → D
  map {X Y : C} : (X ⟶ Y) → (obj X ⟶ obj Y)
  map_id (X : C) : map (𝟙 X) = 𝟙 (obj X)
  map_comp {X Y Z : C} (f : X ⟶ Y) (g : Y ⟶ Z) :
    map (f ≫ g) = map f ≫ map g
```

## Key Theorems

- `F.map_id X` - Functors preserve identity
- `F.map_comp f g` - Functors preserve composition

## Notation

- `C ⥤ D` - Functor type
- `𝟭 C` - Identity functor
- `F ⋙ G` - Functor composition (left-to-right)

## Example Usage

```lean
import Mathlib.CategoryTheory.Functor.Basic

variable {C D : Type*} [Category C] [Category D]
variable (F : C ⥤ D)

-- Prove functor preserves composition
example {X Y Z : C} (f : X ⟶ Y) (g : Y ⟶ Z) :
    F.map (f ≫ g) = F.map f ≫ F.map g := F.map_comp f g
```

## Verification Workflow

```bash
lake build  # Compiler verifies all proofs
```
