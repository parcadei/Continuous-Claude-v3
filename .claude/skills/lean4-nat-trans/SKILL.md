---
name: lean4-nat-trans
description: "Lean 4 Mathlib: Natural transformations between functors"
allowed-tools: [Bash, Read, Write]
---

# Natural Transformations in Lean 4 Mathlib

## NatTrans Structure

```lean
structure NatTrans {C : Type u₁} [Category C] {D : Type u₂} [Category D]
    (F G : C ⥤ D) where
  app (X : C) : F.obj X ⟶ G.obj X
  naturality ⦃X Y : C⦄ (f : X ⟶ Y) :
    F.map f ≫ app Y = app X ≫ G.map f
```

## Key Operations

- `α.app X` - Component at object X
- `α.naturality f` - Naturality square commutes

## Vertical Composition

```lean
def vcomp {F G H : C ⥤ D} (α : F ⟶ G) (β : G ⟶ H) : F ⟶ H where
  app X := α.app X ≫ β.app X
```

## Notation

- `F ⟶ G` - Natural transformation type (same as morphism!)
- `σ ≫ τ` - Vertical composition
- `σ ◫ τ` - Horizontal composition

## Extensionality

```lean
theorem NatTrans.ext {α β : F ⟶ G} (h : ∀ X, α.app X = β.app X) : α = β
```

## Example

```lean
import Mathlib.CategoryTheory.NatTrans

variable {C D : Type*} [Category C] [Category D]
variable {F G : C ⥤ D} (α : F ⟶ G)

-- Use naturality
example {X Y : C} (f : X ⟶ Y) :
    F.map f ≫ α.app Y = α.app X ≫ G.map f := α.naturality f
```
