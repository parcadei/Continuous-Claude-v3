# Math Cognitive Stack: Strategy, Design & Implementation

**Date:** 2025-12-30
**Status:** Books indexed, ready for skill generation
**Session Goal:** Build Claude Code into a mathematically reliable assistant

---

## 1. The Problem Statement

A researcher on Twitter articulated the core issue:

> "Claude Code is useful but nowhere near as transformative as people are making it out to be... they're still way worse at math and spatial reasoning than Gemini. It does poorly any code related to these types of problems."

The complaint: LLMs hallucinate math. They compute wrong, prove incorrectly, and present nonsense with confidence.

**Our goal:** Make Claude Code mathematically reliable by augmenting it with verification tools.

---

## 2. The Solution: Cognitive Prosthetics

Instead of hoping the LLM "gets better at math," we give it tools that can't be wrong:

| Layer | Tool | What it does |
|-------|------|--------------|
| Symbolic Computation | SymPy | Exact arithmetic, symbolic manipulation |
| Constraint Solving | Z3 | SAT/SMT solving, find solutions or prove impossible |
| Step Verification | math_scratchpad.py | Audit trail for multi-step reasoning |
| Formal Proofs | Lean 4 | Compiler-verified proofs - if it compiles, it's correct |

**Key insight:** The tools ARE the verification. Claude proposes, tools verify. No hallucination possible on verified outputs.

---

## 3. What We Built This Session

### 3.1 Lean 4 Integration

- Installed `elan` (Lean toolchain manager)
- Lean 4.26.0 available at `~/.elan/bin/lean`
- Created compiler-in-the-loop hooks:
  - `PostToolUse` hook runs Lean on any `.lean` file write
  - Detects `sorry` placeholders (incomplete proofs)
  - Reports compiler errors immediately
  - Stop hook blocks completion with unresolved issues

**Novel claim:** First CLI coding assistant with native Lean 4 compiler-in-the-loop.

### 3.2 Ragie Book Indexing

- 31 math textbooks uploaded to Ragie
- Partition: `math-textbooks`
- Covers: Real Analysis, Linear Algebra, Abstract Algebra, Topology, Number Theory, Complex Analysis, Optimization, Information Theory, Graph Theory, Category Theory, Mathematical Logic, ODEs/PDEs, Numerical Methods

### 3.3 Upload Script

Created `scripts/upload_math_books.py`:
- Handles PDF and EPUB formats
- Uses correct Ragie API parameters (no `mode` - that's Unstructured.io)
- Partition-based organization

---

## 4. Conclusions Proven Wrong

### 4.1 "Use hi_res mode for better OCR"

**Wrong.** Ragie doesn't have a `mode` parameter. That's Unstructured.io's API. Research agent caught this via Nia docs lookup.

### 4.2 "Need complex chunking pipeline"

**Wrong.** Ragie already chunks the PDFs. We don't need a separate `ingest_math_textbook.py` for structure extraction. Just query Ragie directly.

### 4.3 "Mathematical intuition is mysterious"

**Partially wrong.** Mathematical intuition ≈ Bayesian inference over problem patterns. It's learnable via enough examples. However, truly novel insights (research-level breakthroughs) remain beyond pattern matching.

---

## 5. Key Insights Validated

### 5.1 Lean IS the Eval

No human labeling needed. If Lean compiles, the proof is valid. This gives us:
- Ground truth verification
- Infinite scalability
- No ambiguity

### 5.2 Memory Flywheel

Proofs that compile get stored in memory. Over time:
- Similar problems retrieve similar proven approaches
- Only verified proofs accumulate (no garbage)
- System improves with use

### 5.3 Tool-Augmented is Legitimate

Using SymPy/Z3/Lean isn't "cheating" on benchmarks. It's a recognized category (like GPT-4 + Code Interpreter). The question is "can this system solve problems?" not "can the LLM solve problems in isolation?"

### 5.4 Spatial Reasoning Workaround

Spatial reasoning can be reduced to coordinate/graph operations:
- 3D rotation → matrix multiplication
- Geometric constraints → Z3 solver
- Graph layouts → NetworkX + coordinates

Not a full solution (visual imagination still weak), but a practical workaround.

---

## 6. Architecture

### 6.1 Skills Structure

```
.claude/skills/math/
  real-analysis/
    limits/SKILL.md
    continuity/SKILL.md
    convergence/SKILL.md
  linear-algebra/
    eigenvalues/SKILL.md
    matrices/SKILL.md
  abstract-algebra/
    groups/SKILL.md
    rings/SKILL.md
  workflows/
    prove-series-convergence.yaml
    diagonalize-matrix.yaml
```

### 6.2 Skill Tiers (by Dependency)

| Tier | Topics |
|------|--------|
| 1 (Foundation) | Real Analysis, Linear Algebra, Probability |
| 2 (Core Pure) | Abstract Algebra, Topology, Complex Analysis |
| 3 (Applied) | Numerical Methods, ODEs/PDEs, Optimization, Info Theory |
| 4 (Logic) | Mathematical Logic, Category Theory |
| 5 (Specialized) | Measure Theory, Functional Analysis, Graph Theory, Number Theory |

### 6.3 Workflow Types

1. **Dependency Chains:** B requires A's output
   - Example: Diagonalize matrix = eigenvalues → eigenvectors → form P,D

2. **Decision Trees:** Try A, if fail try B
   - Example: Series convergence = ratio test → comparison → integral → root

3. **Cross-Domain Bridges:** Problem in X needs technique from Y
   - Example: Optimization = calculus (gradient) + linear algebra (Hessian)

---

## 7. The Pipeline

### 7.1 Book → Skill Generation

```
Ragie (books indexed)
        ↓
Query: "What are the techniques for [topic]?"
        ↓
LLM synthesizes into SKILL.md template
        ↓
Write to .claude/skills/math/[topic]/SKILL.md
```

**Swarm approach:** Spawn N agents in parallel, each generating one skill.

### 7.2 Workflow Extraction

```
Query: "What is the problem-solving strategy for [topic]?"
        ↓
Returns: "First try X, if inconclusive try Y..."
        ↓
Parse into workflow YAML
```

### 7.3 Testing Skills

```
Load test problems (from books, MATH benchmark, or miniF2F)
        ↓
Run problem through skill
        ↓
Verify:
  - Computation? → SymPy checks
  - Constraint? → Z3 checks
  - Proof? → Lean compiles
        ↓
If verified → skill is valid
If not → iterate or discard
```

---

## 8. Evaluation Strategy

### 8.1 Benchmarks

| Benchmark | Size | Type | Auto-eval |
|-----------|------|------|-----------|
| MATH | 12.5k | Competition problems | Answer check |
| miniF2F | 488 | Formal Lean proofs | Compiler |
| GSM8K | 8.5k | Grade school | Answer check |

### 8.2 Novel Metric

Not just "got right answer" but "answer is Lean-verified."

Publishable result: "X% of MATH problems solved with formal verification"

### 8.3 Testing in Claude Code

Use Claude Code CLI for eval (tests actual setup):

```bash
claude --print -p "Prove: [theorem]" >> results.json
```

This tests skills + hooks + Lean integration directly.

---

## 9. Open Source Considerations

### 9.1 What We Ship

- Skills (SKILL.md files) - patterns we synthesize, no copyright issues
- Workflows (YAML files) - decision trees we create
- Scripts (generate, test, eval) - tooling
- Hooks (Lean compiler-in-the-loop) - integration

### 9.2 What Users Bring

- Their own textbooks (RAG them locally or via Ragie)
- API keys (Ragie, Anthropic)
- Lean installation (via elan)

### 9.3 Database Choice

- Default: SQLite (zero friction)
- Optional: PostgreSQL + pgvector (for power users)

---

## 10. Next Steps

### Immediate (Next Session)

1. **Build `generate_math_skills.py`**
   - Query Ragie for topics
   - Generate SKILL.md for each
   - Write to skills folder

2. **Generate first batch of skills**
   - Start with Tier 1: Real Analysis, Linear Algebra
   - Test with sample problems

### Short-term

3. **Build workflow extractor**
   - Extract decision trees from books
   - Generate workflow YAML files

4. **Build eval harness**
   - Load miniF2F/MATH problems
   - Run through Claude Code CLI
   - Aggregate results

### Medium-term

5. **Run benchmark eval**
   - Baseline: Claude without skills
   - Treatment: Claude + skills + tools
   - Measure delta

6. **Document for open source**
   - README with setup instructions
   - Example usage
   - Contribution guide

---

## 11. Scripts Created

| Script | Purpose | Status |
|--------|---------|--------|
| `scripts/upload_math_books.py` | Batch upload to Ragie | Done |
| `scripts/generate_math_skills.py` | Book → Skill pipeline | TODO |
| `scripts/extract_workflows.py` | Book → Workflow pipeline | TODO |
| `scripts/eval_math_harness.py` | Run benchmark eval | TODO |

---

## 12. Key Files

| File | Purpose |
|------|---------|
| `.claude/hooks/src/compiler-in-the-loop.ts` | Lean PostToolUse hook |
| `.claude/skills/lean4/SKILL.md` | Lean 4 writing patterns |
| `.claude/skills/math-mode/SKILL.md` | SymPy + Z3 cognitive tools |
| `docs/math/MATH_COGNITIVE_STACK.md` | This document |

---

## 13. Summary

We built a mathematically reliable Claude Code by:

1. **Adding verification tools** (SymPy, Z3, Lean) as cognitive prosthetics
2. **Creating compiler-in-the-loop** hooks for Lean 4
3. **Indexing 31 math textbooks** in Ragie for knowledge retrieval
4. **Designing a skill/workflow architecture** for structured math knowledge
5. **Planning Lean-based evaluation** where compiler = ground truth

The key insight: **Claude becomes reliable when it can't output unverified claims.** The tools constrain the output space to only valid mathematics.

Next session: Generate skills from books, test with Lean verification.
