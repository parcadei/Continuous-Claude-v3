# A Developer's Guide to the NL-to-DT+ML Converter

**For those who want to understand without getting a PhD first**

---

## What Is This?

Imagine you tell someone "Build me a house." That sentence is fuzzy. What kind of house? How many rooms? What's the budget? A skilled contractor knows how to ask the right follow-up questions and work within building codes.

This project does something similar for AI agents. It takes natural language prompts like "Implement a caching layer" and converts them into structured skill definitions that an AI can actually execute reliably.

**NL** = Natural Language (how humans write prompts)
**DT** = Decision Theory (how to make choices)
**ML** = Modal Logic (rules about what must, should, or cannot happen)

The result? Instead of an AI guessing what you meant, it has a formal blueprint.

---

## Why Does It Matter?

Skills need to be precise. Natural language is not.

Consider this prompt: "Update the config file safely."

What does "safely" mean here?
- Back up first? (probably)
- Validate the new values? (maybe)
- Lock the file during writes? (depends on the system)
- Never delete existing keys? (unclear)

An AI that just "wings it" might do any of these, or none. A structured skill definition captures exactly what "safely" means for THIS context, with explicit rules the AI must follow.

The gap between fuzzy instructions and precise execution is where bugs, security issues, and unexpected behavior live. This project bridges that gap.

---

## The Journey

### It Started with an Experiment

We built a "skill upgrader" - a system where 4 AI agents work together to improve skill definitions. One agent focuses on states and actions, another on policies and rewards, a third on logical constraints, and a fourth on verification.

It worked. But something was missing.

Each agent was doing its piece, but we didn't have a coherent theory explaining WHY these pieces fit together. We were building a house without understanding architecture.

### Digging into the Foundations

We uploaded textbooks to Ragie (a retrieval system):
- **Category Theory**: How structures transform while preserving meaning
- **Decision Theory**: How to model choices and consequences
- **Modal Logic**: How to express rules about necessity, time, and obligation

Then we searched academic papers through Nia (a documentation search tool) to find how these theories connect to natural language processing.

### The Verification Problem

Here's the tricky part: when you read something in an academic paper, is it actually true? Or just a claim someone made?

We adopted a three-legged verification approach:

1. **Check the textbooks** (Ragie): Does the foundational theory support this?
2. **Find the claim** (Arxiv papers): What exactly are researchers asserting?
3. **Cross-reference**: Does claim X match what the textbooks say? If not, mark it as "Belief" not "Knowledge"

This matters because building on unverified claims is how software projects end up with mysterious bugs. If the foundation is shaky, everything above it wobbles.

---

## Key Insights in Plain English

### Imperatives Evoke Questions

When someone says "Implement X," that's not a question. But it EVOKES questions.

Think about it: "Implement a cache" immediately makes you wonder:
- What's being cached?
- How long do items live?
- What's the eviction policy?
- Where is it stored?

There's a formal framework called Inferential Erotetic Logic (yes, "erotetic" means "pertaining to questions") that describes exactly how statements evoke questions. We use this to systematically extract what needs to be answered before implementation can begin.

### "Must" Means Different Things

"You must be joking" is not the same as "The file must exist."

- The first is an inference about probability
- The second is a requirement (precondition)

Classical logic can't tell these apart. But there's a technique called "exact verification" that can. We use context to figure out which flavor of "must" we're dealing with:

| Phrase | Interpretation |
|--------|----------------|
| "The file must exist" | Precondition |
| "Must always log errors" | Obligation (deontic) |
| "Must have been deleted" | Inference about past |
| "Must complete eventually" | Temporal guarantee |

### Transformers Preserve Structure

Here's a reassuring discovery: large language models like Claude aren't just pattern-matching black boxes. Recent research shows that self-attention mechanisms are actually mathematical objects called "functors" that preserve compositional structure.

What this means practically: when we ask Claude to transform a natural language prompt into a structured skill, there's theoretical justification for expecting that transformation to preserve meaning. It's not magic - it's math.

---

## The 4-Stage Pipeline

### Stage 1: Erotetic Analysis (Break into Questions)

**Input:** "Implement a rate limiter for the API"

**Output:**
- Questions evoked: [What's the rate limit? Per user or global? What happens when exceeded?]
- Presuppositions: [An API exists, rate limiting is desirable]
- Dependencies: [Answering "what's the limit" requires knowing the use case]

Think of this as the "discovery phase" in a software project.

### Stage 2: Decision Theory (Model the Choices)

**Input:** Questions from Stage 1

**Output:**
- States: [normal, throttled, blocked]
- Actions: [allow_request, queue_request, reject_request]
- Observations: [request_count, time_window, client_id]
- Hidden info: [Is this a legitimate burst or an attack?] -> This makes it a POMDP

If there's hidden information (things we can't directly observe), we're dealing with a POMDP (Partially Observable Markov Decision Process). This is crucial because it tells us we need to maintain beliefs and update them as evidence arrives.

### Stage 3: Logic Constraints (Extract the Rules)

**Input:** The original prompt + context

**Output:**
- Temporal: G(rate_limit_enforced) - "always enforce"
- Deontic: O(log_rejections) - "must log when rejecting"
- Temporal: F(reset_counter) - "eventually reset the counter"
- Forbidden: F(block_admin) - "never block admin users"

The keywords in the prompt map to logical operators:

| Keyword | Logic | Meaning |
|---------|-------|---------|
| "always" | G | Globally true |
| "never" | G (negation) | Never true |
| "must" | O | Obligatory |
| "may" | P | Permitted |
| "eventually" | F | Future true |

### Stage 4: Synthesis (Combine into Skill Format)

**Input:** All outputs from Stages 1-3

**Output:** A structured skill definition with:
- Initiation conditions (when to start)
- Observation space (what can be sensed)
- Action space (what can be done)
- Policy (state -> action mapping)
- Termination (when to stop)
- Constraints (must/must-not rules)
- Verification properties (safety/liveness)

This final stage is where we use the LLM as a "functor" - a structure-preserving transformation. We're not just summarizing; we're mapping from one formal domain (evoked questions, decision structures, logical constraints) to another (executable skill specification).

---

## Current Status

**Confidence Level:** 72%

Why not higher? We have:
- Verified theoretical foundations (textbooks)
- Promising paper citations (some empirical, some formal)
- A clear architecture

What we lack:
- End-to-end testing with real prompts
- Hand-traced examples proving each stage works
- Edge case exploration

The 28% uncertainty is honest. Until we run actual test cases, this is a well-researched hypothesis, not a proven system.

---

## How to Help

### 1. TDD (Test-Driven Development)

We need tests before implementation. What would convince you that Stage 1 works? Write that test.

```python
def test_erotetic_analysis():
    prompt = "Implement a cache with LRU eviction"
    result = analyze(prompt)

    # What questions SHOULD be evoked?
    assert "cache size" in result.evoked_questions
    assert "time-based expiry" in result.evoked_questions

    # What presuppositions exist?
    assert "items can be cached" in result.presuppositions
```

### 2. Hand-Traced Examples

Take a real skill prompt and manually work through all 4 stages. Document:
- What the output should be at each stage
- Where ambiguity creeps in
- What information you needed that wasn't in the prompt

These become golden test cases.

### 3. Challenge the Theory

Found a paper that contradicts something here? Excellent. We want to know. The three-legged verification exists precisely because we don't want to build on sand.

### 4. Edge Cases

What prompts would break this?
- Contradictory requirements
- Deeply nested conditionals
- Implicit knowledge assumptions
- Multi-agent coordination

---

## Quick Reference

| Stage | Input | Output | Key Insight |
|-------|-------|--------|-------------|
| 1. Erotetic | Prompt | Questions + Presuppositions | Imperatives evoke questions |
| 2. Decision | Questions | States, Actions, Observability | Hidden info = POMDP |
| 3. Logic | Prompt + Context | Temporal, Deontic, Epistemic rules | "Must" needs disambiguation |
| 4. Synthesis | All above | Structured Skill | LLM as structure-preserving functor |

---

## Further Reading

If you want to go deeper:

- `theoretical-foundation.md` in this directory: Full formal details with citations
- `.claude/skills/skill-upgrader/SKILL.md`: The 4-agent system that sparked this research
- LaValle's "Planning Algorithms": Decision theory foundations
- Blackburn's "Modal Logic": Constraint representation

---

*Last updated: 2025-12-30*
*Status: Research complete, implementation pending*
