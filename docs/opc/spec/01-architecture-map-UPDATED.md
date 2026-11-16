# Architecture Map

**Reference:** See [00-architecture-decisions.md](./00-architecture-decisions.md) for authoritative Round 3 decisions (113+ total decisions).

## Overview

High-level map of the continuity system architecture, showing how components interact and route requests.

## Core Architecture

```
User Input
    ↓
Maestro (Main Conversation)
    ↓
Routing Layer (Keyword + Haiku Fallback)
    ↓
Lead Agent (Scout/Architect/Pioneer/etc.)
    ↓
Specialist Agents (if hierarchical pattern)
    ↓
Tools (Bash, Edit, Read, etc.)
```

## Routing Philosophy (Round 3 Decision)

The system uses a **three-tier routing architecture**:

### Tier 1: Maestro (Main Conversation)

- **Role**: Primary orchestrator, decides WHEN to delegate
- **Responsibilities**:
  - Parse user intent
  - Decide: handle directly OR delegate to agents
  - Select orchestration pattern (swarm/hierarchical/jury/etc.)
  - Summarize agent results for user

**Key Insight**: Maestro is NOT a separate agent - it's the main Claude Code conversation.

### Tier 2: Routing Layer (Keyword + Haiku Fallback)

- **Role**: Map intent → appropriate Lead Agent
- **Mechanism**: Two-phase routing

#### Phase 1: Keyword Matching (Fast, Deterministic)

```typescript
interface RoutingRule {
  keywords: string[];           // e.g., ["codebase", "search", "find"]
  leadAgent: string;            // e.g., "Scout"
  confidence: number;           // 0.8-1.0 for keyword matches
}

// Example routing rules
const rules: RoutingRule[] = [
  { keywords: ["search", "find", "locate"], leadAgent: "Scout", confidence: 0.9 },
  { keywords: ["design", "architecture"], leadAgent: "Architect", confidence: 0.9 },
  { keywords: ["implement", "build", "create"], leadAgent: "Pioneer", confidence: 0.85 },
  { keywords: ["review", "critique"], leadAgent: "Critic", confidence: 0.9 },
];
```

**Advantages**:
- Fast (milliseconds)
- Deterministic (same input → same route)
- Transparent (user can understand routing)
- No API cost

#### Phase 2: Haiku Fallback (Semantic, LLM-based)

When keyword matching confidence <0.7 OR no keywords match:

```typescript
async function haikuFallback(userIntent: string): Promise<{ agent: string, confidence: number }> {
  const prompt = `
Given user intent: "${userIntent}"

Available agents:
- Scout: Codebase search, file location, pattern finding
- Architect: System design, architecture decisions
- Pioneer: New feature implementation
- Critic: Code review, quality assessment
- [... 14 other agents]

Which agent is best suited? Return JSON:
{ "agent": "AgentName", "confidence": 0.0-1.0, "reasoning": "..." }
`;

  const response = await haiku(prompt);
  return JSON.parse(response);
}
```

**Advantages**:
- Handles ambiguous/novel intents
- Semantic understanding (not just keywords)
- Learns from agent descriptions

**Cost**: ~$0.001 per routing (Haiku is cheap)

### Tier 3: Lead Agent (Execution)

- **Role**: Execute the delegated task
- **Responsibilities**:
  - Read relevant context (ledgers, plans, code)
  - Decide: execute directly OR spawn specialist agents (hierarchical)
  - Use tools (Bash, Edit, Read, etc.)
  - Return results to Maestro

## Component Layers

### Layer 1: Infrastructure

```
SpawnQueue          - Spawn coordination (replaces Oracle agent)
Routing Layer       - Task routing (replaces Nexus agent)
Temporal Memory     - Session history (PostgreSQL)
Artifact Index      - Document indexing (Ragie)
Braintrust Tracing  - Observability
```

### Layer 2: Agent Orchestration

```
18 Core Agents:

Tier 1: Meta-Orchestration
  - Maestro         - Main conversation orchestrator
  - [Oracle]        - DEPRECATED (replaced by SpawnQueue)
  - [Nexus]         - DEPRECATED (replaced by Routing Layer)

Tier 2: Planning & Analysis
  - Scout           - Codebase reconnaissance
  - Surveyor        - System mapping
  - Architect       - Design and architecture
  - Pathfinder      - Implementation planning
  - Atlas           - Documentation mapping

Tier 3: Implementation
  - Pioneer         - New features
  - Phoenix         - Refactoring
  - Spark           - Quick fixes
  - Liaison         - Integration work

Tier 4: Quality & Validation
  - Critic          - Code review
  - Judge           - Architectural decisions
  - Sentinel        - Security
  - Warden          - Resource management
  - Validator       - Test validation
  - Chronicler      - Session documentation
```

### Layer 3: Workflows

```
/onboard    - User onboarding (tutorial in sandbox)
/plan       - Create implementation plans
/implement  - Execute plans via agents
/review     - Quality review via Critic/Judge
```

### Layer 4: Persistence

```
thoughts/ledgers/           - Session state (checkboxes)
thoughts/shared/plans/      - Implementation plans
thoughts/shared/handoffs/   - Cross-session handoffs
docs/archive/               - Archived artifacts
```

## Request Flow Example

### Example 1: Simple Request (Direct Maestro Handling)

```
User: "What's the status of Phase 3?"
  ↓
Maestro: Read thoughts/ledgers/current.md
  ↓
Maestro: "Phase 3 completed, now on Phase 4"
```

**No agent spawning needed** - Maestro handles directly.

### Example 2: Delegation (Keyword Routing)

```
User: "Find all files that use authentication"
  ↓
Maestro: "This is a search task, delegate to agent"
  ↓
Routing Layer (Keyword Match):
  - Keywords: ["find", "files"]
  - Match: Scout agent
  - Confidence: 0.9
  ↓
Lead Agent (Scout):
  - Use Morph/Grep to search codebase
  - Find 12 files with auth patterns
  - Return results
  ↓
Maestro: "Found 12 files: [list]"
```

### Example 3: Ambiguous Intent (Haiku Fallback)

```
User: "Make the system more robust"
  ↓
Maestro: "Ambiguous intent, delegate"
  ↓
Routing Layer (Keywords): No strong match (confidence <0.7)
  ↓
Routing Layer (Haiku Fallback):
  Prompt: "User wants 'more robust', which agent?"
  Haiku: { agent: "Sentinel", confidence: 0.75, reasoning: "Robustness = security + reliability" }
  ↓
Lead Agent (Sentinel):
  - Audit for security issues
  - Check error handling
  - Suggest improvements
  ↓
Maestro: "Sentinel found 3 security gaps and 5 error handling improvements"
```

### Example 4: Hierarchical Pattern

```
User: "Implement the new payment API"
  ↓
Maestro: "Complex implementation, delegate"
  ↓
Routing Layer: Match "implement" → Pioneer
  ↓
Lead Agent (Pioneer):
  "This is complex, spawn specialists"
  ↓
  Specialist Agents:
    - Architect: Design API structure
    - Sentinel: Security review
    - Validator: Test strategy
  ↓
  Pioneer: Synthesize results, implement
  ↓
Maestro: "Payment API implemented, tests passing"
```

## Data Flow

```
Session Start
  ↓
Load Ledger (thoughts/ledgers/CONTINUITY_CLAUDE-*.md)
  ↓
User Input
  ↓
Maestro: Direct handling OR agent delegation
  ↓
Agent Execution (if delegated)
  ↓
Update Ledger (checkboxes, state)
  ↓
Return to User
  ↓
Session End: Archive artifacts (if needed)
```

## Routing Decision Tree

```
User Input
  ↓
Is this a simple status query?
  YES → Maestro handles directly (read ledger)
  NO ↓

Is this a well-defined task?
  YES → Routing Layer
    ↓
    Keyword match found (confidence >0.7)?
      YES → Route to matched Lead Agent
      NO → Haiku fallback → Route to semantic match
  NO ↓

Is this a complex/multi-phase task?
  YES → Maestro creates plan first
    ↓
    Plan complete? → Route to Pioneer/Phoenix (implementation)
    Plan unclear? → Route to Pathfinder (planning)
```

## Key Design Principles

1. **Maestro = Main Conversation**: Not a separate agent, keeps orchestration transparent
2. **Two-Phase Routing**: Fast keywords first, semantic fallback for edge cases
3. **Keyword Transparency**: Users understand why routing happened
4. **Haiku Efficiency**: Cheap LLM calls for ambiguous cases
5. **SpawnQueue > Oracle**: Explicit spawn coordination, no hot-path LLMs
6. **Routing Layer > Nexus**: Deterministic keyword routing, semantic fallback

## Anti-Patterns (Deprecated)

These patterns were replaced in Round 3:

### Anti-Pattern 1: Oracle Agent for Spawn Coordination

```
# OLD (deprecated)
User → Maestro → Oracle → Spawns agents
       (Oracle decides who to spawn)

# NEW (current)
User → Maestro → SpawnQueue
       (Maestro decides, SpawnQueue coordinates)
```

**Why changed**: Oracle was a hot-path LLM (slow, expensive, non-deterministic).

### Anti-Pattern 2: Nexus Agent for Routing

```
# OLD (deprecated)
User → Maestro → Nexus → Lead Agent
       (Nexus routes based on LLM)

# NEW (current)
User → Maestro → Routing Layer (Keyword + Haiku) → Lead Agent
       (Deterministic keywords, semantic fallback)
```

**Why changed**: Nexus routing was opaque, slow, and required LLM for every route.

## Migration Notes

### Oracle → SpawnQueue

- **Old**: `.claude/agents/oracle.md`
- **New**: `scripts/agentica_patterns/spawn_queue.py`
- **Archived**: `docs/archive/agents/2025-01-01-oracle.md`

### Nexus → Routing Layer

- **Old**: `.claude/agents/nexus.md`
- **New**: Keyword matching + Haiku fallback (no separate agent file)
- **Archived**: `docs/archive/agents/2025-01-01-nexus.md`

## Testing Strategy

```typescript
// Test keyword routing
test('keyword routing selects correct agent', () => {
  const intent = "find all TypeScript files";
  const route = keywordRoute(intent);
  expect(route.agent).toBe('Scout');
  expect(route.confidence).toBeGreaterThan(0.7);
});

// Test Haiku fallback
test('haiku fallback handles ambiguous intent', async () => {
  const intent = "improve system reliability";
  const route = await haikuFallback(intent);
  expect(route.agent).toBe('Sentinel'); // or Warden
  expect(route.confidence).toBeGreaterThan(0.6);
});

// Test routing decision tree
test('simple queries skip routing', () => {
  const intent = "what is the current phase?";
  const decision = routingDecision(intent);
  expect(decision.type).toBe('maestro-direct');
  expect(decision.agent).toBeNull();
});
```

## Related Decisions

From [00-architecture-decisions.md](./00-architecture-decisions.md):

- **Maestro = Main Conversation**: Not a separate agent
- **Routing Philosophy**: Maestro → Routing → Lead Agent
- **Keyword Matching**: Fast, deterministic, transparent
- **Haiku Fallback**: Semantic routing for ambiguous cases
- **SpawnQueue**: Replaces Oracle agent for spawn coordination
- **18 Core Agents**: Oracle and Nexus deprecated
- **Archive Paths**: Deprecated agents → `docs/archive/agents/`

## References

- [Agent Orchestration](./05-agent-orchestration.md) - Agent spawning patterns
- [Hooks & Skills & Routing](./03-hooks-skills-routing.md) - Routing implementation
- [Temporal Archival](./20-temporal-archival.md) - Archiving deprecated agents
- [Sandbox Environment](./14-sandbox.md) - Sandbox routing behavior
