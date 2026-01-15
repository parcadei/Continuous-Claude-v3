---
name: research-external
description: External research workflow for docs, web, APIs - NOT codebase exploration
model: sonnet
allowed-tools: [Bash, Read, Write, Task]
---

# External Research Workflow

Research external sources (documentation, web, APIs) for libraries, best practices, and general topics.

> **Note:** The current year is 2025. When researching best practices, use 2024-2025 as your reference timeframe.

## Invocation

```
/research-external <focus> [options]
```

## Question Flow (No Arguments)

If the user types just `/research-external` with no or partial arguments, guide them through this question flow. Use AskUserQuestion for each phase.

### Phase 1: Research Type

```yaml
question: "What kind of information do you need?"
header: "Type"
options:
  - label: "How to use a library/package"
    description: "API docs, examples, patterns"
  - label: "Best practices for a task"
    description: "Recommended approaches, comparisons"
  - label: "General topic research"
    description: "Comprehensive multi-source search"
  - label: "Compare options/alternatives"
    description: "Which tool/library/approach is best"
```

**Mapping:**
- "How to use library" → library focus
- "Best practices" → best-practices focus
- "General topic" → general focus
- "Compare options" → best-practices with comparison framing

### Phase 2: Specific Topic

```yaml
question: "What specifically do you want to research?"
header: "Topic"
options: []  # Free text input
```

Examples of good answers:
- "How to use Prisma ORM with TypeScript"
- "Best practices for error handling in Python"
- "React vs Vue vs Svelte for dashboards"

### Phase 3: Library Details (if library focus)

If user selected library focus:

```yaml
question: "Which package registry?"
header: "Registry"
options:
  - label: "npm (JavaScript/TypeScript)"
    description: "Node.js packages"
  - label: "PyPI (Python)"
    description: "Python packages"
  - label: "crates.io (Rust)"
    description: "Rust crates"
  - label: "Go modules"
    description: "Go packages"
```

Then ask for specific library name if not already provided.

### Phase 4: Depth

```yaml
question: "How thorough should the research be?"
header: "Depth"
options:
  - label: "Quick answer"
    description: "Just the essentials"
  - label: "Thorough research"
    description: "Multiple sources, examples, edge cases"
```

**Mapping:**
- "Quick answer" → --depth shallow
- "Thorough" → --depth thorough

### Phase 5: Output

```yaml
question: "What should I produce?"
header: "Output"
options:
  - label: "Summary in chat"
    description: "Tell me what you found"
  - label: "Research document"
    description: "Write to thoughts/shared/research/"
  - label: "Handoff for implementation"
    description: "Prepare context for coding"
```

**Mapping:**
- "Research document" → --output doc
- "Handoff" → --output handoff

### Summary Before Execution

```
Based on your answers, I'll research:

**Focus:** library
**Topic:** "Prisma ORM connection pooling"
**Library:** prisma (npm)
**Depth:** thorough
**Output:** doc

Proceed? [Yes / Adjust settings]
```

## Focus Modes (First Argument)

| Focus | Primary Tool | Purpose |
|-------|--------------|---------|
| `library` | nia-docs | API docs, usage patterns, code examples |
| `best-practices` | perplexity-search | Recommended approaches, patterns, comparisons |
| `general` | All MCP tools | Comprehensive multi-source research |

## Options

| Option | Values | Description |
|--------|--------|-------------|
| `--topic` | `"string"` | **Required.** The topic/library/concept to research |
| `--depth` | `shallow`, `thorough` | Search depth (default: shallow) |
| `--output` | `handoff`, `doc` | Output format (default: doc) |
| `--library` | `"name"` | For `library` focus: specific package name |
| `--registry` | `npm`, `py_pi`, `crates`, `go_modules` | For `library` focus: package registry |

## Workflow

### Step 1: Parse Arguments

Extract from user input:
```
FOCUS=$1           # library | best-practices | general
TOPIC="..."        # from --topic
DEPTH="shallow"    # from --depth (default: shallow)
OUTPUT="doc"       # from --output (default: doc)
LIBRARY="..."      # from --library (optional)
REGISTRY="npm"     # from --registry (default: npm)
```

### Step 2: Execute Research by Focus

#### Focus: `library`

Primary tool: **nia-docs** - Find API documentation, usage patterns, code examples.

```bash
# Semantic search in package
opc-run scripts/mcp/nia_docs.py \
  --package "$LIBRARY" \
  --registry "$REGISTRY" \
  --query "$TOPIC" \
  --limit 10)

# If thorough depth, also grep for specific patterns
opc-run scripts/mcp/nia_docs.py \
  --package "$LIBRARY" \
  --grep "$TOPIC")

# Supplement with official docs if URL known
opc-run scripts/mcp/firecrawl_scrape.py \
  --url "https://docs.example.com/api/$TOPIC" \
  --format markdown)
```

**Thorough depth additions:**
- Multiple semantic queries with variations
- Grep for specific function/class names
- Scrape official documentation pages

#### Focus: `best-practices`

Primary tool: **perplexity-search** - Find recommended approaches, patterns, anti-patterns.

```bash
# AI-synthesized research (sonar-pro)
opc-run scripts/mcp/perplexity_search.py \
  --research "$TOPIC best practices 2024 2025")

# If comparing alternatives
opc-run scripts/mcp/perplexity_search.py \
  --reason "$TOPIC vs alternatives - which to choose?")
```

**Thorough depth additions:**
```bash
# Chain-of-thought for complex decisions
opc-run scripts/mcp/perplexity_search.py \
  --reason "$TOPIC tradeoffs and considerations 2025")

# Deep comprehensive research
opc-run scripts/mcp/perplexity_search.py \
  --deep "$TOPIC comprehensive guide 2025")

# Recent developments
opc-run scripts/mcp/perplexity_search.py \
  --search "$TOPIC latest developments" \
  --recency month --max-results 5)
```

#### Focus: `general`

Use ALL available MCP tools - comprehensive multi-source research.

**Step 2a: Library documentation (nia-docs)**
```bash
opc-run scripts/mcp/nia_docs.py \
  --search "$TOPIC")
```

**Step 2b: Web research (perplexity)**
```bash
opc-run scripts/mcp/perplexity_search.py \
  --research "$TOPIC")
```

**Step 2c: Specific documentation (firecrawl)**
```bash
# Scrape relevant documentation pages found in perplexity results
opc-run scripts/mcp/firecrawl_scrape.py \
  --url "$FOUND_DOC_URL" \
  --format markdown)
```

**Thorough depth additions:**
- Run all three tools with expanded queries
- Cross-reference findings between sources
- Follow links from initial results for deeper context

### Step 3: Synthesize Findings

Combine results from all sources:

1. **Key Concepts** - Core ideas and terminology
2. **Code Examples** - Working examples from documentation
3. **Best Practices** - Recommended approaches
4. **Pitfalls** - Common mistakes to avoid
5. **Alternatives** - Other options considered
6. **Sources** - URLs for all citations

### Step 4: Write Output

#### Output: `doc` (default)

Write to: `thoughts/shared/research/YYYY-MM-DD-{topic-slug}.md`

```markdown
---
date: {ISO timestamp}
type: external-research
topic: "{topic}"
focus: {focus}
sources: [nia, perplexity, firecrawl]
status: complete
---

# Research: {Topic}

## Summary
{2-3 sentence summary of findings}

## Key Findings

### Library Documentation
{From nia-docs - API references, usage patterns}

### Best Practices (2024-2025)
{From perplexity - recommended approaches}

### Code Examples
```{language}
// Working examples found
```

## Recommendations
- {Recommendation 1}
- {Recommendation 2}

## Pitfalls to Avoid
- {Pitfall 1}
- {Pitfall 2}

## Alternatives Considered
| Option | Pros | Cons |
|--------|------|------|
| {Option 1} | ... | ... |

## Sources
- [{Source 1}]({url1})
- [{Source 2}]({url2})
```

#### Output: `handoff`

Write to: `thoughts/shared/handoffs/{session}/research-{topic-slug}.yaml`

```yaml
---
type: research-handoff
ts: {ISO timestamp}
topic: "{topic}"
focus: {focus}
status: complete
---

goal: Research {topic} for implementation planning
sources_used: [nia, perplexity, firecrawl]

findings:
  key_concepts:
    - {concept1}
    - {concept2}

  code_examples:
    - pattern: "{pattern name}"
      code: |
        // example code

  best_practices:
    - {practice1}
    - {practice2}

  pitfalls:
    - {pitfall1}

recommendations:
  - {rec1}
  - {rec2}

sources:
  - title: "{Source 1}"
    url: "{url1}"
    type: {documentation|article|reference}

for_plan_agent: |
  Based on research, the recommended approach is:
  1. {Step 1}
  2. {Step 2}
  Key libraries: {lib1}, {lib2}
  Avoid: {pitfall1}
```

### Step 5: Return Summary

```
Research Complete

Topic: {topic}
Focus: {focus}
Output: {path to file}

Key findings:
- {Finding 1}
- {Finding 2}
- {Finding 3}

Sources: {N} sources cited

{If handoff output:}
Ready for plan-agent to continue.
```

## Error Handling

If an MCP tool fails (API key missing, rate limited, etc.):

1. **Log the failure** in output:
   ```yaml
   tool_status:
     nia: success
     perplexity: failed (rate limited)
     firecrawl: skipped
   ```

2. **Continue with other sources** - partial results are valuable

3. **Set status appropriately:**
   - `complete` - All requested tools succeeded
   - `partial` - Some tools failed, findings still useful
   - `failed` - No useful results obtained

4. **Note gaps** in findings:
   ```markdown
   ## Gaps
   - Perplexity unavailable - best practices section limited to nia results
   ```

## Examples

### Library Research (Shallow)
```
/research-external library --topic "dependency injection" --library fastapi --registry py_pi
```

### Best Practices (Thorough)
```
/research-external best-practices --topic "error handling in Python async" --depth thorough
```

### General Research for Handoff
```
/research-external general --topic "OAuth2 PKCE flow implementation" --depth thorough --output handoff
```

### Quick Library Lookup
```
/research-external library --topic "useEffect cleanup" --library react
```

## Integration with Other Skills

| After Research | Use Skill | For |
|----------------|-----------|-----|
| `--output handoff` | `plan-agent` | Create implementation plan |
| Code examples found | `implement_task` | Direct implementation |
| Architecture decision | `create_plan` | Detailed planning |
| Library comparison | Present to user | Decision making |

## Required Environment

- `NIA_API_KEY` or `nia` server in mcp_config.json
- `PERPLEXITY_API_KEY` in environment or `~/.claude/.env`
- `FIRECRAWL_API_KEY` and `firecrawl` server in mcp_config.json

## Notes

- **NOT for codebase exploration** - Use `research-codebase` or `scout` for that
- **Always cite sources** - Include URLs for all findings
- **2024-2025 timeframe** - Focus on current best practices
- **Graceful degradation** - Partial results better than no results
