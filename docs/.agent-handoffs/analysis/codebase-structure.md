---
root_span_id: 2614d72a-cb0a-47b5-84c3-1263fc71423e
turn_span_id: ec065eea-d622-471c-bbc7-ab2ba236639f
session_id: 2614d72a-cb0a-47b5-84c3-1263fc71423e
---

# Codebase Structure Analysis

## Overview
- **Language:** Python 3.12+ (primary) + TypeScript (hooks)
- **Patterns:** 11 multi-agent orchestration patterns
- **Hooks:** 20 Claude Code hooks (TypeScript)
- **Skills:** 41 Claude Code skills
- **Test Files:** 139 test files (122 unit, 17 integration)

## Directory Structure

```
claude-continuity-kit/
├── .claude/
│   ├── hooks/           # Claude Code hooks (TypeScript + shell wrappers)
│   │   ├── src/         # TypeScript source files
│   │   ├── dist/        # Compiled JavaScript
│   │   └── *.sh         # Shell wrapper scripts
│   ├── skills/          # Claude Code skills (41 SKILL.md files)
│   ├── rules/           # Project rules (.md files)
│   ├── agents/          # Agent configuration files
│   ├── plugins/         # Plugin integrations (braintrust-tracing)
│   └── settings.json    # Hook registration
├── scripts/
│   ├── agentica/        # Multi-agent system
│   │   ├── patterns/    # 11 orchestration patterns
│   │   ├── native_repl/ # Native REPL coordinator
│   │   ├── baseline/    # Reference implementations
│   │   └── examples/    # Usage examples
│   └── *.py             # MCP tool scripts
├── src/
│   └── runtime/         # MCP execution runtime
├── tests/
│   ├── unit/            # Unit tests (122 files)
│   └── integration/     # Integration tests (17 files)
├── servers/             # Generated MCP server wrappers
├── docs/                # Documentation
├── thoughts/            # Ledgers, handoffs, shared plans
└── workspace/           # User scripts (gitignored)
```

## Core Data Structures

### Pattern Primitives (`scripts/agentica/patterns/primitives.py`)

| Name | Type | Line | Purpose |
|------|------|------|---------|
| `ConsensusMode` | Enum | L20 | Voting modes: MAJORITY, UNANIMOUS, THRESHOLD |
| `ConsensusNotReachedError` | Exception | L27 | Raised when voting fails |
| `Consensus` | Class | L36 | Decision-making via agent voting |
| `AggregateMode` | Enum | L227 | Result aggregation: MERGE, CONCAT, BEST |
| `Aggregator` | Class | L234 | Combines multiple agent results |
| `HandoffState` | @dataclass | L378 | State passed between agents in pipelines |

### Pattern Classes (`scripts/agentica/patterns/`)

| Pattern | File | Line | Key Methods |
|---------|------|------|-------------|
| `Swarm` | swarm.py | L39 | `execute(task, agents)` |
| `Pipeline` | pipeline.py | L26 | `run(initial_state)` |
| `Hierarchical` | hierarchical.py | L41 | `execute(task)`, `_decompose_task()` |
| `Jury` | jury.py | L42 | `decide(return_type, question)` |
| `GeneratorCritic` | generator_critic.py | L27 | `run(task)` |
| `CircuitBreaker` | circuit_breaker.py | L35 | `execute(query)` |
| `CircuitState` | circuit_breaker.py | L28 | Enum: CLOSED, OPEN, HALF_OPEN |
| `MapReduce` | map_reduce.py | L24 | `execute(data, chunks)` |
| `ChainOfResponsibility` | chain_of_responsibility.py | L42 | `process(query)` |
| `Handler` | chain_of_responsibility.py | L28 | @dataclass for handler config |
| `Adversarial` | adversarial.py | L24 | `debate(question)`, `resolve(question)` |
| `EventDriven` | event_driven.py | L55 | `publish(event)` |
| `Event` | event_driven.py | L28 | @dataclass for event payload |
| `Subscriber` | event_driven.py | L43 | @dataclass for event handlers |
| `Blackboard` | blackboard.py | L101 | `solve(query)` |
| `BlackboardState` | blackboard.py | L40 | Shared state container |
| `BlackboardResult` | blackboard.py | L94 | @dataclass for results |
| `Specialist` | blackboard.py | L26 | @dataclass for specialist config |

### MCP Runtime (`src/runtime/`)

| Name | File | Line | Purpose |
|------|------|------|---------|
| `ConnectionState` | mcp_client.py | L37 | Enum: UNINITIALIZED, INITIALIZED, CONNECTED |
| `McpClientManager` | mcp_client.py | L51 | Lazy-loading MCP client with state machine |
| `ServerConfig` | config.py | L12 | Pydantic model for server configuration |
| `McpConfig` | config.py | L72 | Pydantic model for MCP config file |
| `NormalizationConfig` | normalize_fields.py | L17 | Field normalization settings |
| `ToolSafety` | generate_test_params.py | L29 | Enum: SAFE, UNSAFE, DANGEROUS |

### Memory & Coordination (`scripts/agentica/`)

| Name | File | Line | Purpose |
|------|------|------|---------|
| `ArchivalFact` | memory_service.py | L48 | @dataclass for stored facts |
| `MemoryService` | memory_service.py | L57 | SQLite-based fact storage |
| `MemoryServicePG` | memory_service_pg.py | L74 | PostgreSQL + pgvector storage |
| `EmbeddingService` | embedding_service.py | L440 | Multi-provider embedding generation |
| `EmbeddingProvider` | embedding_service.py | L44 | ABC for embedding providers |
| `CoordinationDB` | coordination.py | L152 | Agent coordination database |
| `BroadcastType` | coordination.py | L93 | Enum for broadcast message types |
| `BroadcastRecord` | coordination.py | L112 | @dataclass for broadcasts |
| `AgentRecord` | coordination.py | L123 | @dataclass for agent state |
| `TaskRecord` | coordination.py | L139 | @dataclass for task state |

### Span Processing (`scripts/agentica/span_processor.py`)

| Name | Line | Purpose |
|------|------|---------|
| `SpanSummary` | L84 | @dataclass for processed span summaries |
| `SpanDecision` | L107 | @dataclass for extraction decisions |
| `SpanProcessingContext` | L126 | @dataclass for processing context |
| `SpanProcessingResult` | L186 | @dataclass for processing results |
| `SpanProcessor` | L879 | Main span processing orchestrator |

### Session Management (`scripts/agentica/`)

| Name | File | Line | Purpose |
|------|------|------|---------|
| `SessionEntry` | session_tree.py | L40 | @dataclass for session records |
| `Branch` | session_tree.py | L60 | @dataclass for branch metadata |
| `SessionTree` | session_tree.py | L72 | Tree structure for session hierarchy |
| `BeadsTask` | beads_task_graph.py | L71 | @dataclass for task nodes |
| `TaskStatus` | beads_task_graph.py | L38 | Enum: PENDING, RUNNING, COMPLETED, FAILED |
| `BeadsTaskGraph` | beads_task_graph.py | L82 | Task dependency graph |

## Public API Functions

### MCP Runtime (`src/runtime/`)

| Function | File:Line | Signature | Purpose |
|----------|-----------|-----------|---------|
| `get_mcp_client_manager` | mcp_client.py:628 | `() -> McpClientManager` | Singleton accessor |
| `call_mcp_tool` | mcp_client.py:641 | `(tool_id, params) -> Any` | High-level tool caller |
| `generate_wrappers` | generate_wrappers.py:193 | `async (config_path) -> None` | Generate Python wrappers |
| `discover_schemas` | discover_schemas.py:159 | `async (config_path) -> None` | Discover API schemas |
| `main` | harness.py:225 | `() -> NoReturn` | Script execution entry |

### Pattern Methods

| Pattern | Method | Signature | Purpose |
|---------|--------|-----------|---------|
| `Swarm` | `execute` | `(task, agents) -> list[Any]` | Run parallel agents |
| `Pipeline` | `run` | `(initial_state) -> HandoffState` | Execute pipeline stages |
| `Hierarchical` | `execute` | `(task) -> Any` | Decompose and execute |
| `Jury` | `decide` | `(return_type, question) -> Any` | Collect votes, reach consensus |
| `GeneratorCritic` | `run` | `(task) -> HandoffState` | Iterative refinement |
| `CircuitBreaker` | `execute` | `(query) -> Any` | Primary with fallback |
| `MapReduce` | `execute` | `(data, chunks) -> Any` | Parallel map, aggregate reduce |
| `ChainOfResponsibility` | `process` | `(query) -> Any` | Escalating handlers |
| `Adversarial` | `debate` | `(question) -> dict` | Red/blue team debate |
| `EventDriven` | `publish` | `(event) -> list[Any]` | Dispatch to subscribers |
| `Blackboard` | `solve` | `(query) -> BlackboardResult` | Collaborative solving |

## Entry Points

### CLI Commands (pyproject.toml)

| Command | Module | Purpose |
|---------|--------|---------|
| `mcp-exec` | `runtime.harness:main` | Execute MCP-enabled scripts |
| `mcp-generate` | `runtime.generate_wrappers:main` | Generate server wrappers |
| `mcp-generate-discovery` | `runtime.generate_test_params:main` | Generate test parameters |
| `mcp-discover` | `runtime.discover_schemas:main` | Discover API schemas |

### Main Scripts

| Script | Purpose |
|--------|---------|
| `scripts/braintrust_analyze.py` | Analyze Claude Code sessions via Braintrust |
| `scripts/artifact_index.py` | Index artifacts for retrieval |
| `scripts/artifact_query.py` | Query indexed artifacts |
| `scripts/migrate_sqlite_to_postgres.py` | Database migration |
| `scripts/agentica/watch_agents.py` | Monitor agent execution |
| `scripts/agentica/run_hierarchical_swarm.py` | Run hierarchical swarm |

## Pattern Implementations

### Core Patterns (11 total)

| Pattern | File | Key Functions | Description |
|---------|------|---------------|-------------|
| Swarm | `patterns/swarm.py` | `execute()`, `_pattern_env_context()` | Parallel agent execution with aggregation |
| Pipeline | `patterns/pipeline.py` | `run()`, `_pattern_env_context()` | Sequential stage execution |
| Hierarchical | `patterns/hierarchical.py` | `execute()`, `_decompose_task()`, `_execute_subtasks()` | Coordinator decomposes, specialists execute |
| Jury | `patterns/jury.py` | `decide()`, `_spawn_jurors()`, `_collect_votes()` | Multiple agents vote, consensus decides |
| GeneratorCritic | `patterns/generator_critic.py` | `run()`, `_ensure_generator()`, `_ensure_critic()` | Iterative proposal and refinement |
| CircuitBreaker | `patterns/circuit_breaker.py` | `execute()`, `_should_try_primary()` | Primary/fallback with health tracking |
| MapReduce | `patterns/map_reduce.py` | `execute()`, `_map_phase()`, `_reduce_phase()` | Fan-out to mappers, aggregate in reducer |
| ChainOfResponsibility | `patterns/chain_of_responsibility.py` | `process()` | Sequential handler escalation |
| Adversarial | `patterns/adversarial.py` | `debate()`, `resolve()` | Advocate vs adversary with judge |
| EventDriven | `patterns/event_driven.py` | `publish()`, `_dispatch_to_subscriber()` | Event subscription and dispatch |
| Blackboard | `patterns/blackboard.py` | `solve()`, `_run_specialist()`, `_check_completion()` | Shared state collaborative solving |

### Pattern Primitives

| Primitive | Purpose | Methods |
|-----------|---------|---------|
| `Consensus` | Vote-based decisions | `decide()`, `_count_votes()` |
| `Aggregator` | Result combination | `aggregate()`, `_aggregate_merge()`, `_aggregate_concat()` |
| `HandoffState` | State transfer | `add_artifact()`, `merge()`, `record_handoff()` |

## Hook System

### Registered Hooks (.claude/settings.json)

| Event | Hook File | Triggers |
|-------|-----------|----------|
| PreToolUse | pre-tool-use.sh | All tool uses |
| PreCompact | pre-compact-continuity.sh | Before context compaction |
| SessionStart | session-start-continuity.sh | resume, compact, clear |
| SessionStart | braintrust-tracing/session_start.sh | All starts |
| UserPromptSubmit | skill-activation-prompt.sh | User prompts |
| UserPromptSubmit | braintrust-tracing/user_prompt_submit.sh | User prompts |
| PostToolUse | post-tool-use.sh | All tool uses |
| PostToolUse | post-task-complete.sh | Task tool only |
| PostToolUse | typescript-preflight.sh | Edit, Write |
| PostToolUse | handoff-index.sh | Write only |
| PostToolUse | post-tool-use-tracker.sh | Edit, MultiEdit, Write, Bash |
| PostToolUse | braintrust-tracing/post_tool_use.sh | All (*) |
| Stop | stop-coordinator.sh | Agent stop |
| Stop | braintrust-tracing/stop_hook.sh | Agent stop |
| SubagentStart | subagent-start.sh | Subagent spawn |
| SubagentStop | subagent-stop.sh | Subagent complete |
| SubagentStop | subagent-stop-continuity.sh | Subagent complete |
| SessionEnd | session-end-cleanup-swarms.sh | Session end |
| SessionEnd | session-end-cleanup.sh | Session end |
| SessionEnd | session-outcome.sh | Session end |
| SessionEnd | braintrust-tracing/session_end.sh | Session end |

### TypeScript Hook Sources (20 files)

| File | Purpose | Key Interfaces |
|------|---------|----------------|
| session-start-continuity.ts | Load ledger on resume | `SessionStartInput`, `HandoffSummary` |
| session-end-cleanup.ts | Cleanup on session end | `SessionEndInput` |
| session-outcome.ts | Mark session outcome | `SessionEndInput`, `HookOutput` |
| skill-activation-prompt.ts | Detect skill triggers | `HookInput`, `SkillRule`, `MatchedSkill` |
| pre-tool-use-broadcast.ts | Broadcast tool usage | `PreToolUseInput`, `HookOutput` |
| pre-compact-continuity.ts | Save state before compact | `PreCompactInput`, `HookOutput` |
| post-task-complete.ts | Post-task processing | `PostToolUseInput`, `HookOutput` |
| stop-coordinator.ts | Coordinate agent stop | `StopInput`, `HookOutput` |
| stop-swarm-coordinator.ts | Swarm stop coordination | `StopInput`, `HookOutput` |
| subagent-start.ts | Track subagent spawn | `SubagentStartInput`, `HookOutput` |
| subagent-stop.ts | Track subagent complete | `SubagentStopInput`, `HookOutput` |
| subagent-start-swarm.ts | Swarm subagent spawn | `SubagentStartInput`, `HookOutput` |
| subagent-stop-swarm.ts | Swarm subagent complete | `SubagentStopInput`, `HookOutput` |
| subagent-stop-continuity.ts | Subagent state cleanup | `SubagentStopInput`, `TranscriptEntry` |
| session-end-cleanup-swarms.ts | Swarm session cleanup | `SessionEndInput`, `HookOutput` |
| typescript-preflight.ts | TS compile check | `PostToolUseInput`, `HookOutput` |
| handoff-index.ts | Index handoff files | `PostToolUseInput`, `BraintrustState` |
| transcript-parser.ts | Parse transcripts | `TranscriptEntry`, `TodoWriteInput`, `EditWriteInput` |
| pre-tool-use.ts | Pre-tool validation | - |
| post-tool-use.ts | Post-tool processing | - |

### Pattern Hooks (`patterns/`)

| File | Purpose |
|------|---------|
| hierarchical.ts | Hierarchical pattern support |
| hierarchical-test-harness.ts | Testing harness |
| swarm.ts | Swarm pattern support |
| pipeline.ts | Pipeline pattern support |
| jury.ts | Jury pattern support |
| generator-critic.ts | Generator/Critic support |
| circuit-breaker.ts | Circuit breaker support |
| map-reduce.ts | Map/Reduce support |
| chain-of-responsibility.ts | Chain of responsibility |
| adversarial.ts | Adversarial pattern support |
| event-driven.ts | Event-driven support |
| blackboard.ts | Blackboard pattern support |

## Dependencies

### Core Dependencies (pyproject.toml)

| Package | Purpose |
|---------|---------|
| `mcp>=1.0.0` | Model Context Protocol SDK |
| `pydantic>=2.0.0` | Data validation |
| `aiofiles>=23.0.0` | Async file I/O |
| `python-dotenv>=1.0.0` | Environment loading |
| `aiohttp>=3.13.2` | HTTP client |
| `openai>=1.0.0` | OpenAI API |
| `symbolica-agentica>=0.3.1` | Agentica SDK |
| `fastapi>=0.127.0` | Web framework |
| `uvicorn>=0.40.0` | ASGI server |
| `aiosqlite>=0.19.0` | Async SQLite |

### Optional Dependencies

| Group | Packages | Purpose |
|-------|----------|---------|
| `postgres` | asyncpg, pgvector, numpy | PostgreSQL + vector search |
| `agentica` | symbolica-agentica, fastapi, uvicorn, rich | Agent SDK |
| `discovery` | anthropic | Schema discovery |
| `dev` | black, mypy, ruff, pytest, pytest-asyncio | Development tools |

### Internal Module Dependencies

```
scripts/agentica/patterns/
  ├── __init__.py (exports all patterns)
  ├── primitives.py (ConsensusMode, Aggregator, HandoffState)
  └── [11 pattern modules import primitives]

src/runtime/
  ├── mcp_client.py (imports config, exceptions)
  ├── harness.py (imports mcp_client, env_utils, exceptions)
  ├── config.py (Pydantic models)
  └── exceptions.py (base exception classes)
```

## Test Coverage

### Unit Tests (122 files in tests/unit/)

| Module | Test File | Focus |
|--------|-----------|-------|
| Patterns | test_agentica_swarm.py | Swarm execution |
| Patterns | test_agentica_hierarchical.py | Hierarchical decomposition |
| Patterns | test_agentica_jury.py | Voting and consensus |
| Patterns | test_agentica_pipeline.py | Pipeline stages |
| Patterns | test_agentica_circuit_breaker.py | Fallback behavior |
| Patterns | test_agentica_map_reduce.py | Map/reduce phases |
| Patterns | test_agentica_adversarial.py | Debate mechanics |
| Patterns | test_agentica_blackboard.py | Shared state |
| Patterns | test_agentica_event_driven.py | Event dispatch |
| Patterns | test_agentica_chain_of_responsibility.py | Handler escalation |
| Primitives | test_agentica_consensus.py | Voting modes |
| Primitives | test_agentica_aggregator.py | Result merging |
| Primitives | test_agentica_handoff.py | State transfer |
| Memory | test_memory_service.py | SQLite storage |
| Memory | test_memory_service_pg.py | PostgreSQL storage |
| Memory | test_embedding_service.py | Embedding generation |
| Memory | test_vector_search.py | Vector similarity |
| Runtime | test_mcp_client.py | MCP client manager |
| Runtime | test_generate_wrappers.py | Wrapper generation |
| Runtime | test_schema_inference.py | Type inference |
| Hooks | test_pre_tool_use_broadcast.py | Broadcast hook |
| Hooks | test_post_task_complete.py | Task completion |
| Hooks | test_session_end_cleanup.py | Session cleanup |
| Security | test_security_path.py | Path traversal |
| Security | test_security_mutation.py | Mutation testing |
| Security | test_security_threading.py | Thread safety |
| Async | test_async_pool_bugs.py | Pool edge cases |
| Async | test_async_sqlite_bugs.py | SQLite async issues |
| Async | test_async_embedding_bugs.py | Embedding async |
| Async | test_async_memory_races.py | Race conditions |

### Integration Tests (17 files in tests/integration/)

| Test File | Focus |
|-----------|-------|
| test_agentica_server_integration.py | Agentica server |
| test_broadcast_flow.py | Broadcast system |
| test_claude_scope_e2e.py | Claude scope |
| test_memory_e2e.py | Memory system |
| test_postgres_setup.py | PostgreSQL setup |
| test_sqlite_to_postgres_migration.py | Migration |
| test_hook_integration.py | Hook system |
| test_security_e2e.py | Security |
| test_unified_scope_e2e.py | Unified scope |
| test_llm_span_memory_e2e.py | LLM span memory |
| test_pattern_hooks_e2e.py | Pattern hooks |
| test_v3_integration.py | V3 features |

### Coverage Summary

| Area | Test Files | Coverage Level |
|------|------------|----------------|
| Patterns | 24 | High - all 11 patterns tested |
| Memory | 12 | High - both backends tested |
| Runtime | 8 | Medium - core paths tested |
| Hooks | 15 | High - all events tested |
| Security | 8 | High - path, mutation, threading |
| Async | 5 | High - race conditions, bugs |

## Skills (41 total)

| Skill | Purpose |
|-------|---------|
| commit | Git commits without Claude attribution |
| ast-grep-find | AST-based code search |
| morph-search | Fast text search via WarpGrep |
| morph-apply | Fast file editing via Morph API |
| repoprompt | Token-efficient codebase exploration |
| rp-explorer | RepoPrompt explorer agent |
| firecrawl-scrape | Web scraping via Firecrawl |
| github-search | GitHub code/repo search |
| perplexity-search | AI-powered web search |
| nia-docs | Library documentation search |
| qlty-check | Code quality checks |
| create_plan | Create implementation plans |
| implement_plan | Execute plans from thoughts/shared/plans |
| implement_task | Single task implementation agent |
| plan-agent | Planning agent with handoffs |
| validate-agent | Validate tech choices |
| research | Document codebase research |
| research-agent | External research via MCP |
| research-codebase | Codebase documentation |
| repo-research-analyst | Repository analysis |
| test-driven-development | TDD workflow |
| debug | Issue investigation |
| debug-hooks | Hook debugging workflow |
| braintrust-analyze | Session analysis via Braintrust |
| braintrust-tracing | Tracing integration guide |
| compound-learnings | Transform learnings to skills |
| continuity_ledger | Ledger management |
| create_handoff | Create handoff documents |
| resume_handoff | Resume from handoffs |
| describe_pr | PR description generation |
| onboard | Analyze brownfield codebases |
| skill-developer | Create new skills |
| hook-developer | Create new hooks |
| token-burn-debug | Debug token/context issues |
| multi-tool-pipeline | Chain MCP tools |
| agentica-sdk | Agentica SDK guide |
| agentica-spawn | Agentica spawn patterns |
| agentica-server | Agentica server setup |
| agentica-claude-proxy | Claude proxy integration |
| agentica-prompts | Reliable prompt writing |
| recall-reasoning | Search past reasoning |
