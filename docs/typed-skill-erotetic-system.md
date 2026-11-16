# Typed Skill Schema + Erotetic System

## Executive Summary

The Typed Skill Schema system adds optional typed parameters to Claude Code skills. When a user invokes a skill with incomplete information, the system automatically identifies which parameters are unknown and asks for clarification.

**Example**: User types "Deploy my FastAPI app" without specifying a hosting provider. The system detects the missing `hosting` parameter and asks "Where should I deploy? (aws/gcp/azure/vercel/railway)?"

Key capabilities:
- **Typed skill parameters**: Add enums, bools, ints to SKILL.md frontmatter with automatic extraction patterns
- **Smart clarification**: Automatically identifies missing required parameters and asks only for what's needed
- **Fast extraction**: Parameter detection takes ~5ms (no LLM calls, deterministic)
- **Backward compatible**: Skills without typed parameters work exactly as before

For the theoretical foundations (Inferential Erotetic Logic, Z3 constraint solving, formal verification), see the Appendix.

---

## Quick Start (5 minutes)

### Prerequisites

You need:
- **Python 3.12+**: Check with `python3 --version`
- **uv**: `pip install uv` or `brew install uv` (macOS)
- **Agentica** (optional): For skill generation. Install via `uv pip install agentica` or skip if only testing schemas

### Create Your First Typed Skill

1. Create `.claude/skills/hello-world/SKILL.md`:

```yaml
---
name: hello-world
description: Greet a user with customization
parameters:
  language:
    type: enum
    values: [english, spanish, french]
    infer_from: '\b(english|spanish|french)\b'
  tone:
    type: enum
    values: [formal, casual, playful]
    default: casual
    infer_from: '\b(formal|casual|playful)\b'
---

# Hello World

A simple skill that greets the user.

## When to Use

When you want to greet someone with custom language and tone.

## Instructions

1. Extract language and tone from user prompt
2. Generate appropriate greeting
3. Respond with the greeting
```

2. Run the extraction check:

```bash
uv run python scripts/erotetic_skill_check.py \
  --skill hello-world \
  --prompt "Say hello in Spanish with a casual tone"
```

Expected output: `{"isEmpty": true, "unknowns": [], "count": 0}` (all parameters found).

3. Test with missing parameters:

```bash
uv run python scripts/erotetic_skill_check.py \
  --skill hello-world \
  --prompt "Say hello in Spanish"
```

Expected output: `{"isEmpty": false, "unknowns": ["tone"], "count": 1}` (missing tone).

### What's Next

- **Deep dive on parameters**: See "How to Use" → "Creating a Typed Skill"
- **Understand E(X,Q)**: See "Architecture" → "System Overview"
- **Convert existing skills**: See "How to Use" → "Converting Existing Skills"
- **Run full test suite**: `uv run pytest tests/unit/test_z3_erotetic.py -v`

---

## Architecture

### System Overview

```
                                USER PROMPT
                          "Deploy FastAPI to AWS"
                                    |
                                    v
    +---------------------------------------------------------------+
    |                    SKILL.md: Typed Parameters                  |
    |  +----------------------------------------------------------+ |
    |  |  parameters:                                              | |
    |  |    hosting:                                               | |
    |  |      type: enum                                           | |
    |  |      values: [vercel, aws, gcp, azure, railway]          | |
    |  |      infer_from: '\b(vercel|aws|gcp|azure|railway)\b'    | |
    |  |    framework:                                             | |
    |  |      type: enum                                           | |
    |  |      values: [fastapi, express, django, rails, hono]     | |
    |  |      infer_from: '\b(fastapi|express|...)\b'             | |
    |  +----------------------------------------------------------+ |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |              skill_extractor.py: Regex Extraction              |
    |  extracted = {hosting: "aws", framework: "fastapi"}           |
    |  (~5ms, deterministic, testable)                              |
    +---------------------------------------------------------------+
                                    |
                                    v
    +---------------------------------------------------------------+
    |             z3_erotetic.py: Compute E(X,Q)                     |
    |  E(X,Q) = {} (empty - all parameters extracted!)              |
    |  OR                                                            |
    |  E(X,Q) = ["database"] (one unknown remains)                  |
    +---------------------------------------------------------------+
                                    |
                                    v
                     isEmpty=true: Proceed with skill
                     isEmpty=false: Ask clarifying questions
```

### Component Descriptions

| Component | File | Purpose |
|-----------|------|---------|
| Schema Parser | `scripts/skill_schema_parser.py` | Parse typed params from YAML frontmatter |
| Value Extractor | `scripts/skill_extractor.py` | Extract values from prompts via regex |
| Schema Loader | `scripts/skill_loader.py` | Load SKILL.md from disk |
| E(X,Q) Checker | `scripts/z3_erotetic.py` | Compute unknown propositions |
| CLI Entry Point | `scripts/erotetic_skill_check.py` | JSON interface for hooks |
| Skill Generator | `scripts/skill_generator_v2.py` | CREATE/CONVERT/ENHANCE modes |
| Parity Checker | `scripts/skill_parity_checker.py` | Verify prose vs schema coverage |
| Prose Extractor | `scripts/skill_prose_extractor.py` | LLM-based param inference |
| Schema Extractor | `scripts/skill_schema_extractor.py` | Direct E(X,Q) from schema |

### Data Flow

1. **Skill Activation**: User prompt triggers skill via `skill-rules.json` patterns
2. **Schema Loading**: `skill_loader.py` reads SKILL.md, extracts frontmatter
3. **Value Extraction**: `skill_extractor.py` applies `infer_from` regex patterns
4. **E(X,Q) Computation**: `z3_erotetic.py` identifies unknowns (value = "UNKNOWN" or None)
5. **Clarification Loop**: If unknowns exist, hook asks user; repeats until E(X,Q) = {}
6. **Skill Execution**: With all params known, skill proceeds

---

## How to Use

### 1. Creating a Typed Skill

Create a SKILL.md file with typed parameters in the YAML frontmatter:

```yaml
---
name: deploy-api
description: Deploy API to cloud provider
parameters:
  hosting:
    type: enum
    values: [vercel, aws, gcp, azure, railway]
    required: true
    infer_from: '\b(vercel|aws|gcp|azure|railway)\b'
  framework:
    type: enum
    values: [fastapi, express, django, rails, hono]
    infer_from: '\b(fastapi|express|django|rails|hono)\b'
  replicas:
    type: int
    default: 1
    min: 1
    max: 10
---

# Deploy API

Deploy your API application to a cloud hosting provider.

## When to Use

Use this skill when deploying backend applications to cloud providers.

## Instructions

1. Extract deployment parameters from prompt
2. Generate configuration files
3. Provide deployment commands
```

**Parameter Types**:
- `enum`: Finite set of allowed values
- `bool`: True/false
- `int`: Integer with optional min/max bounds
- `string`: Arbitrary text (not Z3-checkable)

**Key Fields**:
- `required`: If true and not extracted, triggers clarification
- `default`: Used when parameter not found in prompt
- `infer_from`: Regex pattern for extraction (recommended for enums)

### 2. Running E(X,Q) Check

```bash
# Full extraction - all parameters found
uv run python scripts/erotetic_skill_check.py \
  --skill deploy-api \
  --prompt "Deploy my FastAPI app to AWS with 3 replicas"
# Output: {"isEmpty": true, "unknowns": [], "count": 0}

# Partial extraction - framework found, hosting unknown
uv run python scripts/erotetic_skill_check.py \
  --skill deploy-api \
  --prompt "Deploy my FastAPI app"
# Output: {"isEmpty": false, "unknowns": ["hosting"], "count": 1}

# Minimal extraction - multiple unknowns
uv run python scripts/erotetic_skill_check.py \
  --skill deploy-api \
  --prompt "Deploy my app"
# Output: {"isEmpty": false, "unknowns": ["hosting", "framework"], "count": 2}

# With custom base path
uv run python scripts/erotetic_skill_check.py \
  --skill deploy-api \
  --prompt "Deploy to AWS" \
  --base-path /path/to/project

# Enable generic fallback patterns
uv run python scripts/erotetic_skill_check.py \
  --skill simple-skill \
  --prompt "Build API with JWT" \
  --use-generic-fallback
```

### 3. Converting Existing Skills

Use the skill generator to convert prose skills to typed schemas:

```bash
# Convert mode - extract params from existing prose
uv run python -c "
import asyncio
from scripts.skill_generator_v2 import convert_skill

async def main():
    result = await convert_skill('.claude/skills/debug')
    print(f'Coverage: {result.parity_result.coverage_score:.1%}')
    print(f'Missing: {result.parity_result.prose_only}')
    print(result.yaml_content)

asyncio.run(main())
"

# Create mode - new skill from prompt
uv run python -c "
import asyncio
from scripts.skill_generator_v2 import create_skill, CreationMode

async def main():
    result = await create_skill(
        'Build a GraphQL API generator',
        mode=CreationMode.RESEARCH
    )
    print(result.yaml_content)

asyncio.run(main())
"

# Enhance mode - add params to existing
uv run python -c "
import asyncio
from scripts.skill_generator_v2 import enhance_skill

async def main():
    result = await enhance_skill(
        '.claude/skills/debug',
        {'verbose': {'type': 'bool', 'default': False}}
    )
    print(f'New coverage: {result.parity_result.coverage_score:.1%}')

asyncio.run(main())
"
```

### 4. Verifying Parity

Check that a converted schema preserves the semantic intent of the original prose:

```python
from scripts.skill_parity_checker import check_parity

prose_eqx = {
    "parameters": {"auth_method": {}, "log_format": {}, "database": {}},
    "unknowns": {"auth_method": "UNKNOWN", "log_format": "UNKNOWN"}
}

schema_eqx = {
    "parameters": {"auth_method": {"type": "enum", "values": ["JWT", "OAuth"]}},
    "unknowns": {}
}

result = check_parity(prose_eqx, schema_eqx)
print(f"Coverage: {result.coverage_score:.1%}")  # 33.3% (1 of 3 params)
print(f"Missing: {result.prose_only}")           # ['log_format', 'database']
print(f"Valid: {result.is_valid}")               # False (< 80% threshold)
```

---

## Implementation Details

### File Reference

| File | Purpose | Lines |
|------|---------|-------|
| `scripts/skill_schema_parser.py` | Parse YAML frontmatter to SkillSchema dataclass | 82 |
| `scripts/skill_extractor.py` | Apply regex patterns to extract values | ~60 |
| `scripts/skill_loader.py` | Load SKILL.md from filesystem | ~40 |
| `scripts/z3_erotetic.py` | Core E(X,Q) computation | 105 |
| `scripts/erotetic_skill_check.py` | CLI entry point for hooks | 89 |
| `scripts/skill_generator_v2.py` | CREATE/CONVERT/ENHANCE modes | 424 |
| `scripts/skill_parity_checker.py` | Bidirectional coverage verification | 133 |
| `scripts/skill_prose_extractor.py` | LLM-based parameter inference | ~100 |
| `scripts/skill_schema_extractor.py` | Direct E(X,Q) from schema | ~80 |
| `.claude/skills/deploy-api/SKILL.md` | Example typed skill | 75 |

### Key Decisions and Rationale

**Decision 1: Typed params over global schemas**

We considered maintaining global parameter schemas (e.g., "all hosting parameters across all skills") but rejected this approach. Skills have domain-specific vocabularies - a "framework" for web development differs from a "framework" for machine learning. Skill-local typed params allow each skill to define its own semantic space.

**Decision 2: Regex over LLM for extraction**

Initial implementation used LLM calls to extract parameter values from prompts. This took approximately 1500ms per extraction and was non-deterministic. Switching to regex `infer_from` patterns achieved:
- ~300x estimated speedup (regex ~5ms vs LLM ~1500ms, not benchmarked)
- Deterministic, reproducible results
- Easy to test and debug
- No API costs for extraction

Trade-off: Regex patterns must be carefully crafted to handle variations. We provide fallback to generic patterns for skills without typed params.

**Decision 3: Z3 for formal verification**

We use Z3 constraint solving for E(X,Q) computation because:
- Finite domains (enums) are tractable for SAT solvers
- Provides formal guarantee of correctness
- Fast execution (sub-millisecond for typical parameter sets)
- Well-tested, widely-used library

Alternative considered: Custom constraint propagation. Rejected due to development overhead with no clear benefit.

**Decision 4: 80% parity threshold**

When converting prose skills to typed schemas, we require 80% parameter coverage to consider the conversion valid. This threshold:
- Allows some flexibility (prose may mention edge cases not worth typing)
- Catches significant gaps in semantic coverage
- Can be tuned per use case via `PARITY_THRESHOLD` constant

---

## Testing

### Unit Tests (83 core tests)

| Test File | Count | Coverage |
|-----------|-------|----------|
| `test_skill_schema_parser.py` | 7 | YAML parsing, edge cases |
| `test_skill_extractor.py` | 7 | Pattern matching, UNKNOWN sentinel |
| `test_skill_loader.py` | 5 | Filesystem loading |
| `test_skill_generator_v2.py` | 14 | CREATE/CONVERT/ENHANCE modes |
| `test_erotetic_skill_integration.py` | 5 | End-to-end flow |
| `test_erotetic_skill_check_cli.py` | 4 | CLI interface |
| `test_z3_erotetic.py` | 41 | E(X,Q) computation |

Run core tests:
```bash
uv run pytest tests/unit/test_skill_schema_parser.py \
  tests/unit/test_skill_extractor.py \
  tests/unit/test_skill_loader.py \
  tests/unit/test_skill_generator_v2.py \
  tests/unit/test_erotetic_skill_integration.py \
  tests/unit/test_erotetic_skill_check_cli.py \
  tests/unit/test_z3_erotetic.py -v
```

### E2E Verification

The system has been manually verified with the `deploy-api` skill:

```bash
# Full extraction (all params resolved)
uv run python scripts/erotetic_skill_check.py \
  --skill deploy-api \
  --prompt "Deploy my FastAPI app to AWS with 3 replicas"
# Result: {"isEmpty": true, "unknowns": [], "count": 0}

# Partial extraction (one param missing)
uv run python scripts/erotetic_skill_check.py \
  --skill deploy-api \
  --prompt "Deploy to AWS"
# Result: {"isEmpty": false, "unknowns": ["framework"], "count": 1}

# Minimal extraction (multiple params missing)
uv run python scripts/erotetic_skill_check.py \
  --skill deploy-api \
  --prompt "Deploy my app"
# Result: {"isEmpty": false, "unknowns": ["hosting", "framework"], "count": 2}
```

---

## Future Work

### Immediate (P0)
1. **TypeScript hook wiring**: Update `.claude/hooks/src/erotetic-clarification.ts` to call `erotetic_skill_check.py` when skill has typed params

### Short-term (P1)
2. **Domain detection for generic prompts**: Detect whether a prompt targets iOS, web design, CLI tools, etc., and apply domain-specific question schemas
3. **dQ attachment**: Include valid answer options in E(X,Q) output for AskUserQuestion tool

### Medium-term (P2)
4. **Migrate existing skills**: Add typed params to high-use skills (commit, debug, implement_plan)
5. **Answer validation**: Validate user responses against dQ options before proceeding

### Research (P3)
6. **Conditional dependencies**: Express that `jwt_secret` is required only if `auth_method: jwt`
7. **Multi-round question loops**: Track clarification history across turns

---


### Key Decisions from Handoffs

| Session | Decision |
|---------|----------|
| 2025-12-30 | Use regex `infer_from` patterns (300x speedup) |
| 2025-12-30 | Typed params optional (backward compatible) |
| 2025-12-30 | Abandon formal 4-stage pipeline (80% value, 5% complexity) |
| 2025-12-30 | Z3 for E(X,Q) on finite enums (formal correctness) |
| 2025-12-30 | 80% parity threshold for conversions |

### Source Files

- Implementation handoff: `thoughts/shared/handoffs/open-source-release/2025-12-30_16-08-14_typed-skill-erotetic-implementation.md`
- Implementation plan: `thoughts/shared/plans/typed-skill-schema-plan.md`
- Skill generator plan: `thoughts/shared/plans/skill-generator-plan.md`
- Theoretical foundation: `scripts/prompt_to_dtml/research/theoretical-foundation.md`
- Methodology: `scripts/prompt_to_dtml/research/METHODOLOGY.md`

---

## Appendix: Theoretical Background

### The Journey: How We Arrived Here

This appendix captures the theoretical exploration that led to the pragmatic system described above. Skip this section unless you're interested in why we chose this approach.

#### 1. The Original Idea

The project began with two parallel tracks that converged unexpectedly.

**Token Efficiency for Skills**: Claude Code skills stored as prose in SKILL.md files consume significant context. A skill definition of 200 words (approximately 484 tokens) could potentially be compressed to 40 tokens using structured schemas. The question was how to capture the same semantic content in a more compact representation.

**Discovery of Erotetic Logic**: While researching question-answering systems, we encountered Andrzej Wisniewski's Inferential Erotetic Logic (IEL). The key concept is *evocation*: a set of declaratives X evokes question Q (written E(X,Q)) when X multiple-conclusion entails the direct answers to Q without forcing any single answer. This formalized something we observed intuitively - when users write prompts like "Deploy my app", they implicitly raise questions about hosting, framework, and configuration.

The convergence insight: typed skill schemas are BOTH token-efficient AND erotetic-checkable. The same structure that reduces context consumption also enables formal verification of what information is missing.

#### 2. What We Tried

We explored a 4-stage formal pipeline grounded in category theory:

**Stage 1: Erotetic Analysis** - Extract questions and presuppositions from natural language using Wisniewski's IEL framework. Convert imperatives to declaratives that evoke questions via E(X,Q).

**Stage 2: Decision Theory Extraction** - Identify state spaces (S), actions (A), and reward structures (R) following MDP/POMDP formalizations from LaValle and Sutton/Barto.

**Stage 3: Logic Constraint Extraction** - Map natural language to temporal (G, F, U), deontic (O, F, P), and epistemic (K, B) operators using Fine's exact verification semantics.

**Stage 4: Categorical Synthesis** - Apply functorial composition via DisCoPy to transform the formal representation into executable skill specifications, treating the LLM as a structure-preserving functor per O'Neill's proof that self-attention is a morphism in Para(Vect).

We implemented DisCoPy functors, built a full IEL question decomposition system, and attempted LLM-based proposition extraction at approximately 1500ms per call.

#### 3. What Didn't Work

**Free-form NL to Formal Propositions**: Converting arbitrary natural language to formal logical propositions proved too complex. The phrase "file must exist" could mean a precondition, an obligation, or an epistemic necessity - disambiguation required understanding context that simple pattern matching could not capture.

**Full Formal Pipeline**: The 4-stage pipeline was theoretically elegant but overkill for CLI UX. Users do not need the system to prove their prompt is consistent with deontic temporal logic; they need their deployment configured correctly.

**Web Search for Formal Logic Papers**: We attempted to use web search for verification but found RAGged textbooks far more reliable. We indexed six books into Ragie: Wisniewski's "Questions, Inferences, and Scenarios", LaValle's "Planning Algorithms", Sutton/Barto's "Reinforcement Learning", Blackburn's "Modal Logic", and Barr-Wells and Pierce on category theory.

#### 4. What We Built

The pragmatic solution achieved 80% of the value with 5% of the complexity:

**Typed Skill Parameters**: SKILL.md files can now include a `parameters:` section in YAML frontmatter defining enum, bool, int, and string parameters with explicit value sets and regex extraction patterns.

**Regex `infer_from` Patterns**: Instead of calling an LLM to extract parameter values, we use skill-specific regex patterns. This achieves ~300x estimated speedup (regex ~5ms vs LLM ~1500ms, not benchmarked) and is deterministic and testable.

**Z3 E(X,Q) on Finite Enums**: For parameters with finite domains (enums, bools, bounded ints), Z3 can formally compute which propositions are unknown. This is true formal erotetic verification, not an approximation.

**Skill Generator with Parity Verification**: When converting prose skills to typed schemas, the generator compares E(X,Q) from both representations to ensure the schema covers at least 80% of the prose-identified parameters.

### Formal Foundations (For Reference)

The E(X,Q) computation is grounded in Inferential Erotetic Logic (Wisniewski, 2013). In brief:
- **E(X,Q)**: A set of propositions X evokes question Q if X entails all direct answers to Q without entailing a unique answer
- **Unknown detection**: A parameter is unknown if its value cannot be extracted AND it is required for the skill to proceed
- **Z3 constraint solving**: We model the parameter space as a SAT problem and ask Z3 to find which variables cannot be assigned

For a formal treatment, see Wisniewski's *Questions, Inferences, and Scenarios* (indexed via Ragie in the project).

### Full Reference List

| Reference | Key Contribution |
|-----------|------------------|
| Wisniewski, A. (2013). *Questions, Inferences, and Scenarios* | Inferential Erotetic Logic framework, E(X,Q) evocation |
| Koralus & Mascarenhas (2013). The erotetic theory of reasoning | Cognitive grounding for question-driven search |
| Funakura (2021). QSEM | Compositional interrogative semantics implementation |
| Barr & Wells (1990). *Category Theory for Computing Science* | Functor axioms: identity, composition, endpoint preservation |
| Pierce (1991). *Basic Category Theory* | Adjoint functors, Free/Forgetful pattern |
| O'Neill (2025). Self-attention as endofunctor | Transformers preserve categorical structure |
| Toumi et al. (2023). DisCoPy | Python toolkit for monoidal categories |
| LaValle (2006). *Planning Algorithms* | MDP/POMDP formalization |
| Sutton & Barto (2018). *Reinforcement Learning* | Decision theory foundations |
| Blackburn et al. (2001). *Modal Logic* | Temporal, deontic, epistemic operators |
| Fine (2012). Exact verification | Modal disambiguation via exact verifiers |
