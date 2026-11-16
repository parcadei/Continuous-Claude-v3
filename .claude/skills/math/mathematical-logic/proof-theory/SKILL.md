---
name: proof-theory
description: "Problem-solving strategies for proof theory in mathematical logic"
allowed-tools: [Bash, Read]
---

# Proof Theory

## When to Use

Use this skill when working on proof-theory problems in mathematical logic.

## Decision Tree


1. **Proof Strategy Selection**
   - Direct proof: assume premises, derive conclusion
   - Proof by contradiction: assume negation, derive false
   - Proof by cases: split on disjunction
   - Induction: base case + inductive step

2. **Structural Induction**
   - Define well-founded ordering on structures
   - Base: prove for minimal elements
   - Step: assume for smaller, prove for current
   - `z3_solve.py prove "induction_principle"`

3. **Cut Elimination**
   - Gentzen's Hauptsatz: cuts can be eliminated
   - Subformula property: only subformulas appear
   - Useful for proof normalization

4. **Completeness/Soundness Check**
   - Soundness: if provable then valid
   - Completeness: if valid then provable
   - `z3_solve.py prove "soundness_theorem"`

5. **Proof Verification**
   - Check each step follows from rules
   - Verify dependencies are satisfied
   - `math_scratchpad.py verify "proof_steps"`


## Tool Commands

### Z3_Induction_Base
```bash
uv run python -m runtime.harness scripts/z3_solve.py prove "P(0)"
```

### Z3_Induction_Step
```bash
uv run python -m runtime.harness scripts/z3_solve.py prove "ForAll([n], Implies(P(n), P(n+1)))"
```

### Z3_Soundness
```bash
uv run python -m runtime.harness scripts/z3_solve.py prove "Implies(derivable(phi), valid(phi))"
```

### Math_Verify
```bash
uv run python -m runtime.harness scripts/math_scratchpad.py verify "proof_structure"
```

## Cognitive Tools Reference

See `.claude/skills/math-mode/SKILL.md` for full tool documentation.
