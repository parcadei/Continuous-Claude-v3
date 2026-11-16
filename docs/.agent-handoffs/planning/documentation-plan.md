---
root_span_id: 2614d72a-cb0a-47b5-84c3-1263fc71423e
turn_span_id: ec065eea-d622-471c-bbc7-ab2ba236639f
session_id: 2614d72a-cb0a-47b5-84c3-1263fc71423e
---

# Documentation Plan: Claude Continuity Kit

Generated: 2025-12-28
Based on: Codebase structure analysis and existing documentation review

## Executive Summary

This plan outlines a complete documentation overhaul for the Claude Continuity Kit, targeting three audiences: beginners (5-minute setup), power users (deep customization), and contributors (extending the system). The existing README.md is comprehensive but overwhelming (1400+ lines). The goal is to decompose it into focused, scannable documents while adding missing API references and visual architecture diagrams.

---

## Information Architecture

```
                            README.md
                         (Entry point)
                               |
        +----------------------+----------------------+
        |                      |                      |
   QUICKSTART.md          ARCHITECTURE.md        PATTERNS.md
   (5-min setup)          (System design)        (11 patterns)
        |                      |                      |
        v                      v                      v
   EXAMPLES.md            HOOKS.md              TESTING.md
   (Runnable code)        (Hook system)         (Test suite)
        |                      |                      |
        +----------------------+----------------------+
                               |
                          API.md
                     (Complete reference)
                               |
        +----------------------+----------------------+
        |                                             |
   TROUBLESHOOTING.md                          JOURNEY.md
   (Errors & solutions)                        (How we got here)
```

**Navigation principle:** Each document answers ONE question:
- README: "What is this?"
- QUICKSTART: "How do I start?"
- ARCHITECTURE: "How does it work?"
- PATTERNS: "Which pattern do I use?"
- API: "What's the interface?"
- HOOKS: "How do hooks work?"
- TESTING: "How do I test?"
- EXAMPLES: "Show me code"
- TROUBLESHOOTING: "Why isn't it working?"
- JOURNEY: "Why was it built this way?"

---

## Document Specifications

### 1. README.md (Entry Point)

**Audience:** Everyone (first impression)
**Purpose:** Answer "What is this? Should I use it?"
**Word count target:** 500-800 words (down from 1400+)

**Sections:**
1. **Hero section** - One-sentence pitch + badges
2. **Problem/Solution** - 3-4 sentences max
3. **Quick visual** - ASCII architecture diagram (simplified)
4. **Feature highlights** - Bullet list, 8-10 items max
5. **Quick start** - 4 commands to get running
6. **Documentation map** - Links to all docs with 1-line descriptions
7. **Contributing** - Link to CONTRIBUTING.md
8. **License** - MIT badge

**Diagrams needed:**
- Simplified architecture (3-layer: User -> Claude -> Data)
- The continuity loop (3-step: Start -> Work -> Clear)

**Code examples:**
- None in README (point to QUICKSTART.md)

**Links to:**
- QUICKSTART.md (primary CTA)
- ARCHITECTURE.md (for curious readers)
- docs/guides/PATTERNS.md (for pattern selection)

**Refactoring note:** Move 80% of current README content to other docs. README should be scannable in <30 seconds.

---

### 2. docs/QUICKSTART.md (5-Minute Setup)

**Audience:** Beginners (first-time users)
**Purpose:** Get from zero to working in 5 minutes
**Word count target:** 600-800 words

**Sections:**
1. **Prerequisites checklist** - Python 3.12+, uv, optional Docker
2. **30-second install** - 3 commands (clone, sync, start)
3. **First session** - What to say to Claude
4. **Verify it works** - 3 checks (ledger loads, skill activates, handoff creates)
5. **What just happened?** - 5-sentence explanation
6. **Next steps** - Links to deeper docs

**Diagrams needed:**
- Terminal screenshot mockup showing successful start
- Ledger file structure (simple tree)

**Code examples:**
```bash
# Clone and start
git clone https://github.com/parcadei/claude-continuity-kit.git
cd claude-continuity-kit
uv sync
claude

# First commands
"save state"  # Creates ledger
"/clear"      # Ledger reloads automatically
```

**Links to:**
- README.md (back to overview)
- ARCHITECTURE.md (how it works)
- EXAMPLES.md (runnable code)
- TROUBLESHOOTING.md (if something breaks)

---

### 3. docs/API.md (Complete API Reference)

**Audience:** Power users, contributors
**Purpose:** Exhaustive reference for all public interfaces
**Word count target:** 2000-3000 words

**Sections:**
1. **Overview** - What's covered, how to navigate
2. **Pattern Classes** - All 11 patterns with full signatures
   - Constructor parameters
   - Method signatures
   - Return types
   - Example usage
3. **Primitives** - Consensus, Aggregator, HandoffState
4. **Memory Services** - SQLite and PostgreSQL backends
5. **MCP Runtime** - McpClientManager, call_mcp_tool
6. **Coordination DB** - Agent tracking, broadcast system
7. **Embedding Service** - Provider protocols
8. **CLI Commands** - mcp-exec, mcp-generate, mcp-discover
9. **Hook Interfaces** - Input/output schemas for all 10 hook types
10. **Type Reference** - All enums, dataclasses, type aliases

**Diagrams needed:**
- Class hierarchy diagram (patterns, primitives, services)
- Hook event flow (input -> processing -> output)

**Code examples:**
```python
# Pattern instantiation
from scripts.agentica.patterns import Swarm
from scripts.agentica.primitives import AggregateMode

swarm = Swarm(
    perspectives=["security", "performance"],
    aggregate_mode=AggregateMode.MERGE,
    model="anthropic:claude-sonnet-4.5"
)
result = await swarm.execute("Analyze codebase")
```

**Links to:**
- PATTERNS.md (usage guidance)
- ARCHITECTURE.md (design rationale)
- Source files (direct links to scripts/agentica/)

**Generation note:** Much of this can be auto-generated from docstrings and type hints. Priority: document what's NOT obvious from code.

---

### 4. docs/ARCHITECTURE.md (System Design)

**Audience:** Contributors, architects, curious power users
**Purpose:** Explain WHY the system is designed this way
**Word count target:** 1500-2000 words

**Sections:**
1. **Philosophy** - "Clear, don't compact" principle
2. **Layer overview** - Hooks -> Skills -> Scripts -> Services
3. **Data flow** - Session lifecycle diagram
4. **State management** - Ledgers, handoffs, cache
5. **Multi-agent coordination** - Pattern primitives, task graphs
6. **Memory architecture** - Three-tier (Core, Archival, Recall)
7. **MCP execution model** - Why scripts over loaded tools
8. **Design decisions** - Key tradeoffs with rationale

**Diagrams needed:**
- Full architecture diagram (current README version, improved)
- Session lifecycle (4-phase: Start -> Work -> PreCompact -> End)
- Memory tier diagram (Core/Archival/Recall flow)
- Pattern composition diagram (how patterns combine)

**Code examples:**
- Minimal - focus on concepts, not implementation

**Links to:**
- API.md (implementation details)
- PATTERNS.md (pattern-specific design)
- HOOKS.md (hook system internals)
- docs/architecture/LESSONS_LEARNED.md (historical context)

---

### 5. docs/PATTERNS.md (11 Patterns Reference)

**Audience:** Intermediate users (know basics, selecting patterns)
**Purpose:** Help users select and use the right pattern
**Word count target:** 2500-3500 words

**Sections:**
1. **Pattern selection guide** - Decision table (when to use each)
2. **Pattern cards** - 11 patterns, each with:
   - When to use (2-3 sentences)
   - How it works (1 paragraph)
   - Quick example (5-10 lines)
   - Key parameters (table)
   - Common pitfalls (bullet list)
3. **Hybrid patterns** - How patterns compose
4. **Performance considerations** - Token usage, latency tradeoffs
5. **Pattern selection heuristics** - Claude-as-router concept

**Diagrams needed:**
- Pattern selection flowchart
- Each pattern's agent topology (11 small diagrams)
- Hybrid composition examples (3 diagrams)

**Code examples:**
```python
# Quick examples for each pattern
# Swarm
swarm = Swarm(perspectives=["security", "perf", "ux"])
result = await swarm.execute("Audit OAuth implementation")

# Jury
jury = Jury(num_jurors=5, consensus_mode=ConsensusMode.MAJORITY)
verdict = await jury.decide(bool, "Is this code safe to deploy?")

# Pipeline
pipeline = Pipeline(stages=[fetch, transform, analyze])
result = await pipeline.run(HandoffState(context="Process data"))
```

**Links to:**
- API.md (full signatures)
- EXAMPLES.md (complete runnable examples)
- docs/architecture/PATTERNS.md (existing detailed reference)

**Refactoring note:** Consolidate existing docs/architecture/PATTERNS.md and scripts/agentica/PATTERNS.md into this single source of truth.

---

### 6. docs/HOOKS.md (Hook System)

**Audience:** Power users, contributors (customizing behavior)
**Purpose:** Explain how to use and create hooks
**Word count target:** 1200-1500 words

**Sections:**
1. **What are hooks?** - Event-driven lifecycle extension
2. **Available hooks** - Table of all 10 hook types with events
3. **Hook anatomy** - Shell wrapper -> TypeScript handler pattern
4. **Input/Output schemas** - JSON interface for each hook type
5. **Registration** - settings.json configuration
6. **Creating custom hooks** - Step-by-step guide
7. **Testing hooks** - Manual testing commands
8. **Debugging hooks** - Common issues and solutions

**Diagrams needed:**
- Hook event timeline (session lifecycle with hook points)
- Hook processing flow (input -> handler -> output -> action)

**Code examples:**
```typescript
// Hook handler pattern
interface HookInput {
  source: 'startup' | 'resume' | 'clear' | 'compact';
  session_id: string;
}

async function main() {
  const input: HookInput = JSON.parse(await readStdin());

  // Process input

  const output = {
    result: 'continue',
    message: 'State loaded from ledger'
  };

  console.log(JSON.stringify(output));
}
```

```bash
# Testing a hook
echo '{"type": "resume"}' | .claude/hooks/session-start-continuity.sh
```

**Links to:**
- API.md (hook interface specifications)
- ARCHITECTURE.md (why hooks exist)
- .claude/skills/hook-developer/SKILL.md (existing skill reference)

---

### 7. docs/TESTING.md (Test Suite)

**Audience:** Contributors (adding/running tests)
**Purpose:** Guide for running and writing tests
**Word count target:** 800-1000 words

**Sections:**
1. **Test overview** - 139 tests (122 unit, 17 integration)
2. **Running tests** - Commands for different scenarios
3. **Test structure** - How tests are organized
4. **Coverage by area** - Table of test files per component
5. **Writing tests** - TDD pattern, mutation testing
6. **Test utilities** - Fixtures, mocks, helpers
7. **CI integration** - How tests run in CI

**Diagrams needed:**
- Test pyramid (unit -> integration -> e2e)
- Coverage heatmap (which areas have tests)

**Code examples:**
```bash
# Run all unit tests
uv run pytest tests/unit/ -v

# Run specific pattern tests
uv run pytest tests/unit/test_agentica_swarm.py -v

# Run with coverage
uv run pytest tests/unit/ --cov=scripts/agentica --cov-report=html

# Run integration tests (requires PostgreSQL)
uv run pytest tests/integration/ -v
```

```python
# Test pattern
async def test_swarm_parallel_execution():
    """Swarm executes agents in parallel."""
    swarm = Swarm(
        perspectives=["A", "B", "C"],
        aggregate_mode=AggregateMode.CONCAT
    )

    # Mock agent execution
    with patch("scripts.agentica.patterns.swarm.spawn") as mock_spawn:
        mock_spawn.return_value.call.return_value = "result"
        results = await swarm.execute("task")

    assert len(results) == 3
    assert mock_spawn.call_count == 3
```

**Links to:**
- CONTRIBUTING.md (overall contribution guide)
- API.md (what's being tested)

---

### 8. docs/TROUBLESHOOTING.md (Errors & Solutions)

**Audience:** All users (when things break)
**Purpose:** Quick fixes for common problems
**Word count target:** 1000-1200 words

**Sections:**
1. **Quick diagnostics** - 5 commands to run first
2. **Installation issues**
   - "MCP server not configured"
   - Python version mismatch
   - Missing dependencies
3. **Hook issues**
   - Ledger not loading
   - Hooks not executing
   - TypeScript compilation errors
4. **Pattern issues**
   - Agent spawning failures
   - Memory service errors
   - Embedding service errors
5. **PostgreSQL issues**
   - Connection refused
   - Schema not loaded
   - Migration errors
6. **Context issues**
   - Compaction despite ledger
   - Context filling too fast
   - Agent context pollution
7. **Getting help** - Where to ask questions

**Diagrams needed:**
- Diagnostic flowchart (symptom -> check -> fix)

**Code examples:**
```bash
# Quick diagnostics
uv run python --version              # Check Python version
cat .python-version                  # Check pinned version
uv pip show agentica                 # Check package installed
ls -la thoughts/ledgers/             # Check ledger exists
chmod +x .claude/hooks/*.sh          # Fix hook permissions

# Common fixes
rm -rf .venv && uv venv && uv sync --all-extras  # Recreate venv
docker stop claude-postgres && ./docker/start-postgres.sh  # Restart DB
```

**Links to:**
- QUICKSTART.md (start fresh)
- GitHub Issues (report new problems)

---

### 9. docs/EXAMPLES.md (Runnable Code)

**Audience:** All users (learning by example)
**Purpose:** Copy-paste examples for common tasks
**Word count target:** 1500-2000 words

**Sections:**
1. **Session management examples**
   - Create ledger
   - Update ledger before clear
   - Resume from handoff
2. **Pattern examples** (one per pattern)
   - Swarm research
   - Hierarchical implementation
   - Jury decision
   - Generator/Critic refinement
   - Pipeline data processing
3. **Memory examples**
   - Store and recall facts
   - Semantic search
   - Cross-agent memory sharing
4. **MCP script examples**
   - Search with Morph
   - Documentation with NIA
   - Web scraping with Firecrawl
5. **Custom hook example**
   - Create a simple PostToolUse hook
6. **Integration example**
   - Full workflow: research -> plan -> implement

**Diagrams needed:**
- None (code-focused document)

**Code examples:** This entire document is code examples. Each example should be:
- Complete (copy-paste runnable)
- Commented (explain each step)
- Practical (solve real problems)

```python
# Example: Full Swarm Research Pattern
from scripts.agentica.patterns import Swarm
from scripts.agentica.primitives import AggregateMode
import asyncio

async def research_topic(topic: str) -> dict:
    """Research a topic from multiple perspectives."""

    swarm = Swarm(
        perspectives=[
            "You are a security expert. Analyze for vulnerabilities.",
            "You are a performance expert. Analyze for bottlenecks.",
            "You are a UX expert. Analyze for usability issues."
        ],
        aggregate_mode=AggregateMode.MERGE,
        model="anthropic:claude-sonnet-4.5"
    )

    result = await swarm.execute(f"Analyze: {topic}")
    return result

# Run it
if __name__ == "__main__":
    result = asyncio.run(research_topic("OAuth 2.0 implementation"))
    print(result)
```

**Links to:**
- API.md (full signatures)
- PATTERNS.md (when to use each pattern)
- scripts/agentica/examples/ (more examples)

---

### 10. docs/JOURNEY.md (How We Got Here)

**Audience:** Contributors, curious users
**Purpose:** Document the evolution and rationale
**Word count target:** 1500-2000 words

**Sections:**
1. **The problem** - Why this project exists
2. **Key discoveries** - Major insights that shaped design
3. **Evolution timeline** - How the system grew
4. **Failed approaches** - What didn't work and why
5. **Design principles** - Rules that emerged
6. **Future directions** - Where this is heading
7. **Acknowledgments** - Who contributed ideas

**Diagrams needed:**
- Evolution timeline (visual)
- Before/after architecture comparison

**Code examples:**
- Minimal (narrative document)

**Links to:**
- ARCHITECTURE.md (current design)
- docs/architecture/LESSONS_LEARNED.md (detailed learnings)
- docs/AGENTICA_INTEGRATION_JOURNEY.md (existing journey doc)

**Refactoring note:** Consolidate existing AGENTICA_INTEGRATION_JOURNEY.md and architecture/LESSONS_LEARNED.md into this document, keeping it narrative and accessible.

---

## Implementation Phases

### Phase 1: Foundation (Priority: Critical)

**Goal:** Core navigation and entry points

**Files:**
1. README.md (rewrite - slim down to 500-800 words)
2. docs/QUICKSTART.md (update existing)
3. docs/ARCHITECTURE.md (new - consolidate)

**Success criteria:**
- [ ] New user finds QUICKSTART in <10 seconds from README
- [ ] QUICKSTART gets user running in <5 minutes
- [ ] ARCHITECTURE explains the "why" without implementation details

**Estimated effort:** 4-6 hours

---

### Phase 2: Reference Documentation (Priority: High)

**Goal:** Complete API and pattern reference

**Files:**
4. docs/API.md (new)
5. docs/PATTERNS.md (new - consolidate existing)
6. docs/HOOKS.md (new)

**Success criteria:**
- [ ] Every public class/function documented in API.md
- [ ] Pattern selection guide helps user choose in <1 minute
- [ ] Hook creation walkthrough is copy-paste friendly

**Estimated effort:** 6-8 hours

---

### Phase 3: User Support (Priority: Medium)

**Goal:** Self-service troubleshooting and examples

**Files:**
7. docs/TESTING.md (new)
8. docs/TROUBLESHOOTING.md (new)
9. docs/EXAMPLES.md (new)

**Success criteria:**
- [ ] Common errors have documented solutions
- [ ] Each pattern has runnable example
- [ ] Test commands are copy-paste ready

**Estimated effort:** 4-6 hours

---

### Phase 4: Narrative & Polish (Priority: Low)

**Goal:** Historical context and final polish

**Files:**
10. docs/JOURNEY.md (new - consolidate existing)
11. Cross-linking and consistency pass
12. Diagram generation

**Success criteria:**
- [ ] Design decisions documented with rationale
- [ ] All cross-links work
- [ ] Diagrams are consistent style

**Estimated effort:** 3-4 hours

---

## Diagram Specifications

### Required Diagrams

| Diagram | Location | Style | Tool |
|---------|----------|-------|------|
| Simplified architecture | README.md | ASCII | Manual |
| Continuity loop | README.md | ASCII | Manual |
| Full architecture | ARCHITECTURE.md | Mermaid | Mermaid CLI |
| Session lifecycle | ARCHITECTURE.md | Mermaid | Mermaid CLI |
| Memory tier flow | ARCHITECTURE.md | Mermaid | Mermaid CLI |
| Pattern selection flowchart | PATTERNS.md | Mermaid | Mermaid CLI |
| 11 pattern topologies | PATTERNS.md | ASCII (small) | Manual |
| Hook event timeline | HOOKS.md | Mermaid | Mermaid CLI |
| Test pyramid | TESTING.md | ASCII | Manual |
| Diagnostic flowchart | TROUBLESHOOTING.md | Mermaid | Mermaid CLI |

### Diagram Style Guide

- **ASCII diagrams:** Use for simple structures (<10 elements)
- **Mermaid diagrams:** Use for complex flows, sequences, class hierarchies
- **Consistent naming:** Use exact class/function names from code
- **Color coding:** Green=success path, Red=error path, Yellow=warning

---

## Content Migration Map

Existing content that will be reorganized:

| Source | Destination | Action |
|--------|-------------|--------|
| README.md "Architecture Overview" | ARCHITECTURE.md | Move + expand |
| README.md "The Problem/Solution" | README.md | Keep but shorten |
| README.md "Quick Start" | QUICKSTART.md | Move + expand |
| README.md "How to Talk to Claude" | README.md | Keep summary, details to skills |
| README.md "Skills vs Agents" | ARCHITECTURE.md | Move |
| README.md "MCP Code Execution" | ARCHITECTURE.md + API.md | Split |
| README.md "Continuity System" | ARCHITECTURE.md | Move |
| README.md "Hooks System" | HOOKS.md | Move + expand |
| README.md "Braintrust Session Tracing" | ARCHITECTURE.md | Move |
| README.md "Artifact Index" | ARCHITECTURE.md | Move |
| README.md "TDD Workflow" | TESTING.md | Move |
| README.md "Troubleshooting" | TROUBLESHOOTING.md | Move + expand |
| docs/AGENTICA_INTEGRATION_JOURNEY.md | JOURNEY.md | Consolidate |
| docs/architecture/LESSONS_LEARNED.md | JOURNEY.md | Consolidate |
| docs/architecture/PATTERNS.md | PATTERNS.md | Consolidate |
| scripts/agentica/PATTERNS.md | PATTERNS.md | Consolidate |
| docs/guides/QUICKSTART.md | QUICKSTART.md | Merge/update |

---

## Quality Checklist

Before each document is considered complete:

- [ ] **Scannable:** Can answer main question in <30 seconds
- [ ] **Actionable:** Includes copy-paste code/commands
- [ ] **Linked:** Cross-references related docs
- [ ] **Tested:** All code examples run without errors
- [ ] **Consistent:** Uses same terminology throughout
- [ ] **Versioned:** Includes version/date where relevant
- [ ] **Accessible:** No unexplained jargon
- [ ] **Maintained:** Has clear owner/update path

---

## Success Metrics

**Quantitative:**
- README.md word count: <800 (currently 1400+)
- Time to first successful run: <5 minutes
- Questions answered by docs: >80% (measured by GitHub issues)

**Qualitative:**
- New users find relevant doc on first try
- Contributors can add hooks without asking for help
- Pattern selection is intuitive from flowchart

---

## Open Questions

1. **Versioning:** Should we add version tags to API.md? (Patterns may change)
2. **Search:** Add Algolia/DocSearch for documentation search?
3. **Translations:** Plan for i18n of core docs?
4. **Video:** Complement with video tutorials for visual learners?
5. **Interactive:** Embed runnable examples (Replit/CodeSandbox)?

---

## References

- Existing docs analyzed:
  - `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/README.md`
  - `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/docs/guides/QUICKSTART.md`
  - `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/docs/architecture/PATTERNS.md`
  - `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/docs/architecture/LESSONS_LEARNED.md`
  - `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/docs/AGENTICA_INTEGRATION_JOURNEY.md`
  - `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/PATTERNS.md`

- Codebase structure:
  - `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/docs/.agent-handoffs/analysis/codebase-structure.md`

- Best practices (from codebase rules):
  - Clear, don't compact (continuity.md)
  - Agent context isolation (agent-context-isolation.md)
  - TDD workflow (tdd-workflow skill)
