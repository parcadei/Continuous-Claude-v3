# rigg: Model-Agnostic Multi-Agent TUI Harness

## Executive Summary

**rigg** is a model-agnostic multi-agent TUI harness with BYOK (Bring Your Own Keys) support. It provides a unified interface for orchestrating AI agents across 15+ providers, with first-class support for local models.

| Attribute | Value |
|-----------|-------|
| Name | rigg |
| Runtime | Bun (TypeScript) |
| SDK | Custom (not Vercel AI SDK) |
| TUI | Custom ANSI renderer (pi-tui inspired) |
| Persistence | PostgreSQL (full) / SQLite (lite mode) |

## Core Principles

### Opinionated Setup
- **Docker required** for full features (PostgreSQL + Redis auto-managed)
- **SQLite lite mode** available for quick starts without Docker
- Convention over configuration - sensible defaults that work out of the box

### Headless Primary
- TUI is optional - rigg runs headless by default
- Daemon-based architecture enables automation and CI/CD integration
- TUI attaches to running sessions when needed

### Multi-Provider First
- 15+ providers supported from day one
- Local models (LMStudio, Ollama) as first-class citizens, not afterthoughts
- Full multimedia support: images, PDFs, files across all capable providers

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        rigg CLI                             │
│              (TUI application, optional)                    │
└─────────────────────────┬───────────────────────────────────┘
                          │ Unix Socket
┌─────────────────────────▼───────────────────────────────────┐
│                        Daemon                               │
│          (Central coordinator, HumanLayer-style)            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Session Mgmt │  │ Cost Tracker │  │ Agent Orchestrator│  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      @rigg/sdk                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Provider Abstraction (15+ providers, unified API)     │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │ Transform Pipeline (messages, tools, responses)       │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │ Tool Simulation (mock/stub for testing)               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    Docker Stack                             │
│  ┌──────────────────┐  ┌────────────────────────────────┐  │
│  │ PostgreSQL       │  │ Redis (pub/sub, caching)        │  │
│  │ (sessions, mem)  │  │                                  │  │
│  └──────────────────┘  └────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Components

**@rigg/sdk**
- Provider abstraction layer with unified API
- Transform pipeline for message/tool/response normalization
- Tool simulation for testing and development

**rigg CLI**
- Full TUI application with custom ANSI renderer
- Keyboard-driven interface (vim-style bindings)
- Multi-pane layout with session tree visualization

**Daemon**
- Central coordinator via Unix socket
- Session lifecycle management
- Cost tracking and rate limiting
- Agent orchestration coordinator

**Docker Stack**
- PostgreSQL for sessions, memory, and audit logs
- Redis for pub/sub between agents and caching
- Auto-managed via `rigg up` / `rigg down`

## Key Features

### Multi-Agent Patterns

| Pattern | Description | Use Case |
|---------|-------------|----------|
| **Swarm** | Parallel agents, synthesized results | Research, exploration |
| **Jury** | Independent voting, majority wins | High-stakes validation |
| **Pipeline** | Sequential handoff (A → B → C) | Linear workflows |
| **Hierarchical** | Coordinator → specialists → grunts | Complex implementation |
| **Generator/Critic** | Propose → critique → iterate | Refinement tasks |
| **Map/Reduce** | Fan out → aggregate | Parallel processing |

### Session Branching

Git-style session management with visual tree display:

```
main ─────○─────○─────○
              │
              └─ experiment/fast-path ─────○─────○
                                      │
                                      └─ experiment/alt-approach ─────○
```

- Branch from any point in history
- Compare branches side-by-side
- Merge sessions with conflict resolution

### Multi-Repo Workspaces

Work across multiple repositories in a single session:

- `@repo1` / `@repo2` references for cross-repo context
- `Ctrl+1` / `Ctrl+2` / `Ctrl+3` for quick workspace switching
- Unified search across all workspace repos

### Erotetic Question Decomposition

Z3-backed question decomposition with decision theory:

- Decomposes complex questions into sub-questions
- Prioritizes by information value (expected entropy reduction)
- Tracks question dependencies and prerequisites

### Temporal Memory

Integrated temporal memory system:

- Facts with validity windows (`valid_from` / `valid_until`)
- Automatic memory decay and consolidation
- Query-time temporal context awareness

### Cost Tracking

Live cost tracking with pricing updates:

- Per-session and per-agent cost breakdown
- Budget alerts and limits
- Cost comparison across providers for same task

### Collaborative Team Mode

Git-style collaboration (not real-time):

- Team members work on branches
- Merge sessions with conflict resolution
- Audit trail of all changes
- No real-time sync complexity

## Supported Providers

### Cloud Providers
- OpenAI (GPT-4, GPT-4o, o1, o3)
- Anthropic (Claude 3.5, Claude 4)
- Google (Gemini 2.0, Gemini Pro)
- Mistral (Large, Medium, Small)
- Cohere (Command R+)
- AI21 (Jamba)
- Perplexity (Online models)
- Groq (Fast inference)
- Together AI
- Fireworks
- DeepSeek

### Local Models
- **LMStudio** - GUI-based local inference
- **Ollama** - CLI-based local models
- **vLLM** - High-throughput serving
- **llama.cpp** - Direct GGUF inference

## Quick Start

```bash
# Install
bun install -g @rigg/cli

# Initialize (creates config, starts Docker if available)
rigg init

# Start a session
rigg chat

# Or headless mode
rigg run --prompt "Analyze this codebase" --output results.json
```

## Document Index

| Document | Description |
|----------|-------------|
| [01-sdk](./01-sdk.md) | @rigg/sdk API reference |
| [02-cli](./02-cli.md) | CLI commands and TUI keybindings |
| [03-daemon](./03-daemon.md) | Daemon architecture and Unix socket API |
| [04-agents](./04-agents.md) | Multi-agent patterns and orchestration |
| [05-sessions](./05-sessions.md) | Session management and branching |
| [06-memory](./06-memory.md) | Temporal memory integration |
| [07-providers](./07-providers.md) | Provider configuration and capabilities |
| [08-deployment](./08-deployment.md) | Docker, lite mode, and team setup |
