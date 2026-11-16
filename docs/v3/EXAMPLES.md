# Examples

Runnable code examples for common tasks in the Claude Continuity Kit.

---

## Pattern Examples

### Swarm: Research Task

Spawn multiple agents with different perspectives to attack a problem from different angles.

```python
from scripts.agentica.patterns import Swarm, AggregateMode

# Research a topic from multiple angles
swarm = Swarm(
    perspectives=[
        "You are a security expert. Analyze for vulnerabilities.",
        "You are a performance expert. Analyze for bottlenecks.",
        "You are a UX expert. Analyze for usability issues.",
    ],
    aggregate_mode=AggregateMode.MERGE,  # Combine all insights
)

result = await swarm.execute("Analyze this OAuth implementation")
print(f"Combined insights: {result}")
```

**When to use:** Research, exploration, "investigate X from multiple angles"

---

### Jury: Consensus Decision

N independent agents vote on a question. Consensus mechanism determines the verdict.

```python
from scripts.agentica.patterns import Jury, ConsensusMode

# Three reviewers vote on code quality
jury = Jury(
    num_jurors=3,
    consensus_mode=ConsensusMode.MAJORITY,
    premise="You are a code reviewer. Evaluate honestly.",
)

verdict = await jury.decide(
    return_type=bool,
    question="Does this code follow best practices?",
)

print(f"Verdict: {'Approved' if verdict else 'Rejected'}")
```

**Variants:**
- `ConsensusMode.UNANIMOUS` - All jurors must agree
- `ConsensusMode.THRESHOLD` - Use with `threshold=0.8` for 80% agreement

**When to use:** Validation, high-stakes decisions, "is this correct?"

---

### Pipeline: Sequential Processing

Each stage receives the output of the previous stage via HandoffState.

```python
from scripts.agentica.patterns import Pipeline, HandoffState

async def fetch_data(state: HandoffState) -> HandoffState:
    """Fetch raw data from API."""
    data = {"users": ["alice", "bob"]}  # Simulate API call
    state.add_artifact("raw_data", data)
    state.update_instruction("Clean and normalize the data")
    return state

async def transform_data(state: HandoffState) -> HandoffState:
    """Clean and normalize data."""
    raw = state.artifacts["raw_data"]
    cleaned = [u.upper() for u in raw["users"]]
    state.add_artifact("cleaned_data", cleaned)
    state.update_instruction("Generate insights from cleaned data")
    return state

async def analyze_data(state: HandoffState) -> HandoffState:
    """Extract insights from processed data."""
    cleaned = state.artifacts["cleaned_data"]
    state.add_artifact("insight", f"Found {len(cleaned)} users")
    state.update_instruction("COMPLETE")
    return state

pipeline = Pipeline(stages=[fetch_data, transform_data, analyze_data])

initial_state = HandoffState(
    context="Analyze Q4 sales data",
    next_instruction="Fetch data from API"
)
result = await pipeline.run(initial_state)

print(f"Final insight: {result.artifacts['insight']}")
```

**When to use:** Linear workflows with clear steps, data processing pipelines

---

### Hierarchical: Coordinator + Specialists

Coordinator decomposes tasks, specialists execute, coordinator synthesizes.

```python
from scripts.agentica.patterns import Hierarchical

hierarchical = Hierarchical(
    coordinator_premise="You decompose complex tasks into subtasks.",
    specialist_premises={
        "researcher": "You research topics and find relevant information.",
        "analyst": "You analyze data and extract insights.",
        "writer": "You write clear, concise summaries.",
    },
)

result = await hierarchical.execute(
    "Research the impact of AI on software development and write a summary"
)
print(result)
```

**When to use:** Complex tasks requiring multiple skill sets, "implement X"

---

### Generator/Critic: Iterative Refinement

Generator proposes, critic evaluates, iterate until approved.

```python
from scripts.agentica.patterns import GeneratorCritic

gc = GeneratorCritic(
    generator_premise="You generate Python code solutions.",
    critic_premise="You review code for correctness and best practices.",
    max_rounds=3,
)

result = await gc.run("Create a function to validate email addresses")

# Result is a HandoffState with artifacts
if "APPROVED" in result.next_instruction:
    print("Code approved!")
    print(result.artifacts.get("code"))
else:
    print("Max iterations reached")
    print(result.artifacts.get("feedback"))
```

**When to use:** Code generation, document drafting, creative tasks needing refinement

---

### MapReduce: Parallel Fan-Out

Fan out work to N mappers in parallel, then combine with reducer.

```python
from scripts.agentica.patterns import MapReduce

mr = MapReduce(
    mapper_premise="You analyze one file for security issues.",
    reducer_premise="You synthesize security findings into a report.",
    num_mappers=4,
)

files = ["auth.py", "api.py", "db.py", "utils.py"]
result = await mr.execute(
    query="Find security vulnerabilities",
    chunks=files
)
print(result)
```

**When to use:** Parallel processing of independent subtasks, code review, data analysis

---

## Hook Examples

### Block Dangerous File Writes

PreToolUse hook that blocks writes to sensitive files.

```typescript
// .claude/hooks/src/pre-tool-use-guard.ts
import { readFileSync } from 'fs';

interface PreToolUseInput {
  tool_name: string;
  tool_input: Record<string, unknown>;
}

interface HookOutput {
  result: 'continue' | 'block';
  reason?: string;
}

const BLOCKED_PATTERNS = ['.env', 'secrets', 'credentials', '.pem', '.key'];

async function main() {
  const input: PreToolUseInput = JSON.parse(readFileSync(0, 'utf-8'));

  if (input.tool_name === 'Write') {
    const path = (input.tool_input?.file_path as string) || '';

    for (const pattern of BLOCKED_PATTERNS) {
      if (path.includes(pattern)) {
        const output: HookOutput = {
          result: 'block',
          reason: `Cannot write to sensitive file matching pattern: ${pattern}`,
        };
        console.log(JSON.stringify(output));
        return;
      }
    }
  }

  console.log(JSON.stringify({ result: 'continue' }));
}

main();
```

Register in `.claude/settings.json`:
```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": ["Write"],
      "hooks": [{
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/pre-tool-use-guard.sh"
      }]
    }]
  }
}
```

---

### Inject Context on Session Start

SessionStart hook that loads continuity ledger.

```typescript
// .claude/hooks/src/session-start-continuity.ts
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

interface SessionStartInput {
  type: 'start' | 'resume' | 'compact';
  session_id: string;
}

async function main() {
  const input: SessionStartInput = JSON.parse(readFileSync(0, 'utf-8'));

  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const ledgerDir = join(projectDir, 'thoughts', 'ledgers');

  // Find most recent ledger
  const ledgerPath = join(ledgerDir, 'CONTINUITY_CLAUDE-current.md');

  if (existsSync(ledgerPath)) {
    const content = readFileSync(ledgerPath, 'utf-8');

    console.log(JSON.stringify({
      result: 'continue',
      message: `## Continuity Ledger\n\n${content}`,
    }));
    return;
  }

  console.log(JSON.stringify({ result: 'continue' }));
}

main();
```

---

## Memory Examples

### Store and Retrieve Facts

Using the MemoryService for session-persistent memory.

```python
from scripts.agentica.memory_service import MemoryService

# Initialize memory for this session
memory = MemoryService(session_id="my-session")
await memory.connect()

# Core memory: key-value for current session facts
await memory.set_core("persona", "You are a helpful coding assistant")
await memory.set_core("task", "Build a REST API with FastAPI")

# Archival memory: searchable long-term storage
await memory.store("User prefers Python over JavaScript")
await memory.store("Project uses PostgreSQL database")
await memory.store("Deploy to AWS Lambda")

# Recall: cross-source query
result = await memory.recall("What database does the project use?")
print(result)  # [Archival]: Project uses PostgreSQL database

# Generate context for prompt injection
context = await memory.to_context()
print(context)
# ## Core Memory
# **persona:** You are a helpful coding assistant
# **task:** Build a REST API with FastAPI
#
# ## Recent Archival Memory
# - Deploy to AWS Lambda
# - Project uses PostgreSQL database
# - User prefers Python over JavaScript

await memory.close()
```

---

### Search Archival Memory

FTS5-powered search with BM25 ranking.

```python
from scripts.agentica.memory_service import MemoryService

memory = MemoryService(session_id="research")
await memory.connect()

# Store research findings
await memory.store("React 18 introduces concurrent rendering")
await memory.store("Vue 3 uses Composition API")
await memory.store("Svelte compiles to vanilla JavaScript")

# Search for specific topics
results = await memory.search("concurrent rendering", limit=5)
for result in results:
    print(f"[{result['id']}] {result['content']} (rank: {result['rank']:.2f})")

await memory.close()
```

---

## MCP Examples

### Call External Tool

Using the MCP runtime to call external tools.

```python
from runtime.mcp_client import call_mcp_tool

# Tool identifier format: "serverName__toolName"
result = await call_mcp_tool(
    "perplexity__perplexity_ask",
    {"query": "What are the latest features in Python 3.13?"}
)
print(result)
```

---

### Multi-Tool Pipeline Script

A complete script that chains multiple MCP tools.

```python
#!/usr/bin/env python3
"""
USAGE:
    uv run python -m runtime.harness scripts/research_pipeline.py \\
        --topic "React Server Components"

Multi-tool research pipeline:
1. Search with Perplexity for current info
2. Find code examples with GitHub search
3. Scrape documentation with Firecrawl
"""

import argparse
from runtime.mcp_client import call_mcp_tool

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True, help="Research topic")
    args = parser.parse_args()

    # Step 1: Get current information
    print(f"Researching: {args.topic}")
    perplexity_result = await call_mcp_tool(
        "perplexity__perplexity_ask",
        {"query": f"Latest best practices for {args.topic}"}
    )
    print(f"Perplexity: {perplexity_result[:500]}...")

    # Step 2: Find code examples
    github_result = await call_mcp_tool(
        "github__search_code",
        {"query": args.topic, "per_page": 5}
    )
    print(f"Found {len(github_result.get('items', []))} code examples")

    # Step 3: Scrape official docs (if available)
    # Note: URL would need to be determined from search results
    # firecrawl_result = await call_mcp_tool(
    #     "firecrawl__scrape",
    #     {"url": "https://react.dev/reference/..."}
    # )

    return {
        "topic": args.topic,
        "research": perplexity_result,
        "examples": github_result,
    }

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

### Using Script Templates

Prefer using existing scripts with CLI arguments over writing new ones.

```bash
# Discover available scripts
ls scripts/

# Read script help
python scripts/firecrawl_scrape.py --help

# Execute with arguments
uv run python -m runtime.harness scripts/firecrawl_scrape.py \
    --url "https://docs.anthropic.com/claude"

# Multi-tool pipeline
uv run python -m runtime.harness scripts/multi_tool_pipeline.py \
    --repo-path "." \
    --max-commits 5
```

---

## HandoffState Examples

### Creating and Using HandoffState

The HandoffState is the core data structure for agent-to-agent communication.

```python
from scripts.agentica.patterns import HandoffState

# Create initial state
state = HandoffState(
    context="Building a REST API for user management",
    next_instruction="Design the database schema"
)

# Add artifacts as work progresses
state.add_artifact("schema", {
    "users": ["id", "email", "name", "created_at"],
    "sessions": ["id", "user_id", "token", "expires_at"]
})

# Update instruction for next agent
state.update_instruction("Implement the API endpoints")

# Record handoff for traceability
state.record_handoff(from_agent="designer", to_agent="implementer")

# Serialize for storage/transmission
data = state.to_dict()

# Deserialize
restored = HandoffState.from_dict(data)

# Merge states (later wins on conflicts)
other_state = HandoffState(
    context="Updated context",
    next_instruction="Deploy to production"
)
merged = state.merge(other_state)
print(merged.next_instruction)  # "Deploy to production"
```

---

## Consensus and Aggregation

### Using Consensus Primitives

```python
from scripts.agentica.patterns import Consensus, ConsensusMode, ConsensusNotReachedError

# Majority voting
majority = Consensus(mode=ConsensusMode.MAJORITY)
votes = [True, True, False, True, False]
result = majority.decide(votes)  # True (3 vs 2)

# Unanimous voting
unanimous = Consensus(mode=ConsensusMode.UNANIMOUS)
try:
    result = unanimous.decide([True, True, False])
except ConsensusNotReachedError as e:
    print(f"No consensus: {e}")

# Threshold voting (80% agreement required)
threshold = Consensus(mode=ConsensusMode.THRESHOLD, threshold=0.8)
votes = ["approve", "approve", "approve", "approve", "reject"]
result = threshold.decide(votes)  # "approve" (80% >= 80%)

# Weighted voting
weights = [1.0, 2.0, 1.0]  # Second vote counts double
votes = ["A", "B", "A"]
result = majority.decide(votes, weights=weights)  # "B" (2.0 vs 2.0, B wins by first-seen)
```

---

### Using Aggregator Primitives

```python
from scripts.agentica.patterns import Aggregator, AggregateMode

# Merge dictionaries
merge_agg = Aggregator(mode=AggregateMode.MERGE)
results = [
    {"security": "issues found"},
    {"performance": "optimal"},
    {"ux": "needs improvement"}
]
merged = merge_agg.aggregate(results)
# {"security": "issues found", "performance": "optimal", "ux": "needs improvement"}

# Concatenate strings
concat_agg = Aggregator(mode=AggregateMode.CONCAT, separator="\n\n")
results = ["Finding 1: XSS vulnerability", "Finding 2: SQL injection"]
combined = concat_agg.aggregate(results)
# "Finding 1: XSS vulnerability\n\nFinding 2: SQL injection"

# Select best by score
best_agg = Aggregator(mode=AggregateMode.BEST)
results = [
    {"score": 0.7, "result": "Solution A"},
    {"score": 0.9, "result": "Solution B"},
    {"score": 0.6, "result": "Solution C"},
]
best = best_agg.aggregate(results)  # "Solution B"

# Deduplicate
dedup_agg = Aggregator(mode=AggregateMode.MERGE, deduplicate=True)
results = [["a", "b"], ["b", "c"], ["c", "d"]]
unique = dedup_agg.aggregate(results)  # ["a", "b", "c", "d"]
```

---

## Environment Variables for Hooks

Patterns set environment variables that hooks can read to enable pattern-aware behavior.

### Swarm Pattern
```bash
PATTERN_TYPE=swarm
PATTERN_ID=<unique_swarm_id>
SWARM_ID=<unique_swarm_id>
AGENT_ROLE=worker
```

### Jury Pattern
```bash
PATTERN_TYPE=jury
PATTERN_ID=<unique_jury_id>
JURY_ID=<unique_jury_id>
AGENT_ROLE=juror
JUROR_INDEX=<n>        # 0-indexed
TOTAL_JURORS=<n>
```

### Pipeline Pattern
```bash
PATTERN_TYPE=pipeline
PATTERN_ID=<unique_pipeline_id>
PIPELINE_ID=<unique_pipeline_id>
AGENT_ROLE=stage
PIPELINE_STAGE_INDEX=<n>       # 0-indexed
PIPELINE_TOTAL_STAGES=<n>
```

### Hierarchical Pattern
```bash
PATTERN_TYPE=hierarchical
PATTERN_ID=<unique_hierarchy_id>
HIERARCHY_ID=<unique_hierarchy_id>
AGENT_ROLE=coordinator|specialist
COORDINATOR_ID=<coordinator_id>  # For specialists
HIERARCHY_LEVEL=<n>              # 0 = coordinator, 1+ = specialist
```

---

## Complete Example: Research Agent

Combining patterns for a complete research workflow.

```python
from scripts.agentica.patterns import (
    Swarm, Hierarchical, Jury,
    AggregateMode, ConsensusMode, HandoffState
)

async def research_topic(topic: str) -> dict:
    """Research a topic using multiple patterns."""

    # Phase 1: Gather information from multiple perspectives (Swarm)
    swarm = Swarm(
        perspectives=[
            "You research academic papers and citations.",
            "You research industry applications and case studies.",
            "You research community discussions and opinions.",
        ],
        aggregate_mode=AggregateMode.MERGE,
    )
    research_results = await swarm.execute(f"Research: {topic}")

    # Phase 2: Analyze and synthesize (Hierarchical)
    hierarchical = Hierarchical(
        coordinator_premise="You coordinate analysis of research findings.",
        specialist_premises={
            "analyst": "You analyze data for trends and patterns.",
            "synthesizer": "You synthesize findings into coherent narratives.",
        },
    )
    synthesis = await hierarchical.execute(
        f"Analyze these research findings:\n{research_results}"
    )

    # Phase 3: Quality check (Jury)
    jury = Jury(
        num_jurors=3,
        consensus_mode=ConsensusMode.MAJORITY,
        premise="You evaluate research quality and accuracy.",
    )
    is_quality = await jury.decide(
        return_type=bool,
        question=f"Is this research synthesis accurate and well-supported?\n{synthesis}"
    )

    return {
        "topic": topic,
        "research": research_results,
        "synthesis": synthesis,
        "quality_approved": is_quality,
    }

# Run the research
result = await research_topic("Impact of LLMs on software development")
print(f"Research {'approved' if result['quality_approved'] else 'needs revision'}")
```

---

## Testing Patterns

Example test for the Swarm pattern.

```python
import pytest
from unittest.mock import AsyncMock, patch

from scripts.agentica.patterns import Swarm, AggregateMode

@pytest.mark.asyncio
async def test_swarm_executes_all_perspectives():
    """Test that swarm spawns agent for each perspective."""

    # Mock the spawn function
    mock_agent = AsyncMock()
    mock_agent.call.return_value = {"insight": "test insight"}

    with patch("scripts.agentica.patterns.swarm.spawn", return_value=mock_agent):
        swarm = Swarm(
            perspectives=["perspective 1", "perspective 2"],
            aggregate_mode=AggregateMode.MERGE,
        )

        result = await swarm.execute("test query")

        # Verify all perspectives were spawned
        assert mock_agent.call.call_count == 2
        assert "insight" in result
```

---

## Running Examples

All examples assume you're in the project root with the virtual environment active.

```bash
# Install dependencies
uv sync

# Run pattern examples
uv run python -c "
import asyncio
from scripts.agentica.patterns import Swarm, AggregateMode

async def main():
    # Your example code here
    pass

asyncio.run(main())
"

# Run MCP scripts
uv run python -m runtime.harness scripts/your_script.py --arg value

# Run tests
uv run pytest tests/unit/test_agentica_*.py -v
```
