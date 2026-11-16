# Temporal Archival Strategy

**Reference:** See [00-architecture-decisions.md](./00-architecture-decisions.md) for authoritative Round 3 decisions (113+ total decisions).

## Overview

Archive obsolete temporal memory, deprecated agents, and legacy artifacts to maintain system clarity while preserving historical context.

## Goals

1. **Reduce Noise**: Remove obsolete data from active queries
2. **Preserve History**: Keep artifacts for archaeological debugging
3. **Clear Signal**: Active data represents current truth
4. **Easy Rollback**: Unarchive if needed

## Archive Paths

Per Round 3 decisions, all archives go to `docs/archive/`:

```
docs/archive/
  agents/                  # Deprecated agent definitions (from .claude/agents/)
    2025-01-01-oracle.md  # Oracle agent (replaced by SpawnQueue)
    2025-01-01-nexus.md   # Nexus agent (replaced by routing)

  temporal/                # Archived temporal memory sessions
    2024-12-sessions/     # Sessions from December 2024
    2025-01-sessions/     # Sessions from January 2025

  ledgers/                 # Completed/obsolete ledgers (from thoughts/ledgers/)
    2024-12-project-x.md  # Completed project ledger

  plans/                   # Completed plans (from thoughts/shared/plans/)
    2024-12-feature-y.md  # Implemented and deployed plan

  handoffs/                # Archived handoffs (from thoughts/shared/handoffs/)
    2024-12-migration/    # Completed migration handoff

  reviews/                 # Review artifacts (from /review workflow)
    2025-01-pr-123/       # Review for PR #123

  sandbox-experiments/     # Sandbox prototypes (from .claude/sandbox/)
    2025-01-auth-proto/   # Auth middleware prototype

  skills/                  # Deprecated skills (from .claude/skills/)
    2024-12-old-skill/    # Skill replaced by newer version

  hooks/                   # Deprecated hooks (from .claude/hooks/)
    2024-12-old-hook.sh   # Hook replaced by newer implementation
```

## 18 Core Agents Reference

Per Round 3 architecture decisions, the core 18 agents are:

**Tier 1: Meta-Orchestration (3 agents)**
1. **Maestro** - Main orchestrator, workflow coordination
2. **Nexus** - (DEPRECATED - replaced by routing layer)
3. **Oracle** - (DEPRECATED - replaced by SpawnQueue)

**Tier 2: Planning & Analysis (5 agents)**
4. **Scout** - Codebase reconnaissance
5. **Surveyor** - System mapping and dependency analysis
6. **Architect** - System design and architecture
7. **Pathfinder** - Implementation path planning
8. **Atlas** - Documentation and knowledge mapping

**Tier 3: Implementation (4 agents)**
9. **Pioneer** - New feature implementation
10. **Phoenix** - Refactoring and technical debt
11. **Spark** - Quick fixes and patches
12. **Liaison** - Cross-system integration

**Tier 4: Quality & Validation (6 agents)**
13. **Critic** - Code review and critique
14. **Judge** - Architectural decisions
15. **Sentinel** - Security and compliance
16. **Warden** - Resource management
17. **Validator** - Test validation
18. **Chronicler** - Session documentation

**Note**: Oracle and Nexus are now deprecated (archived to `docs/archive/agents/`) as their responsibilities moved to:
- **Oracle** → **SpawnQueue** (spawn coordination)
- **Nexus** → **Routing Layer** (task routing)

## Archival Triggers

### Automatic Archival

1. **Temporal Sessions**: Archive sessions >90 days old
2. **Completed Plans**: Archive when implementation verified
3. **Deprecated Agents**: Archive when replaced (e.g., Oracle → SpawnQueue)
4. **Sandbox Experiments**: Archive after promotion or abandonment

### Manual Archival

User-triggered via:
```bash
# Archive specific ledger
.claude/scripts/archive-ledger.sh thoughts/ledgers/completed-project.md

# Archive temporal sessions before date
.claude/scripts/archive-temporal.sh --before 2024-12-01

# Archive deprecated agent
.claude/scripts/archive-agent.sh .claude/agents/oracle.md
```

## Archival Process

### Step 1: Identify Candidates

```typescript
// List archive candidates
interface ArchiveCandidate {
  path: string;
  type: 'temporal' | 'ledger' | 'plan' | 'agent' | 'skill' | 'hook';
  reason: string;
  lastModified: Date;
}

async function identifyCandidates(): Promise<ArchiveCandidate[]> {
  // Temporal: >90 days old
  // Ledgers: marked as [COMPLETED]
  // Plans: implementation deployed
  // Agents: marked as [DEPRECATED]
}
```

### Step 2: Create Archive

```bash
# Archive structure preserves context
docs/archive/agents/2025-01-01-oracle.md

# Archive metadata
---
archived_date: 2025-01-01
original_path: .claude/agents/oracle.md
reason: Replaced by SpawnQueue
replacement: SpawnQueue (scripts/agentica_patterns/spawn_queue.py)
---

[original content]
```

### Step 3: Update References

```typescript
// Update cross-references
async function updateReferences(archived: ArchiveCandidate) {
  // Find files referencing archived artifact
  const refs = await findReferences(archived.path);

  // Add deprecation notice
  for (const ref of refs) {
    await addDeprecationNotice(ref, archived);
  }
}
```

### Step 4: Verify Archival

```bash
# Ensure no broken references
.claude/scripts/verify-archive.sh

# Checks:
# - No active ledgers reference archived artifacts
# - No active agents reference deprecated agents
# - Archive metadata is complete
```

## Query Exclusion

Archived data excluded from active queries:

```sql
-- Temporal query (exclude archived)
SELECT * FROM temporal_memory
WHERE session_id NOT IN (
  SELECT session_id FROM archived_sessions
)
AND created_at > DATE('now', '-90 days');
```

```typescript
// Agent discovery (exclude archived)
async function discoverAgents(): Promise<Agent[]> {
  const agentFiles = await glob('.claude/agents/*.md');
  // Does NOT include docs/archive/agents/
  return parseAgents(agentFiles);
}
```

## Unarchival Process

If archived artifact needed:

```bash
# Unarchive agent
.claude/scripts/unarchive.sh docs/archive/agents/2025-01-01-oracle.md

# Restores to:
.claude/agents/oracle.md

# Updates metadata:
# - Sets unarchived_date
# - Adds restoration reason
```

## Archive Retention

### Retention Policy

| Artifact Type | Retention | Reason |
|---------------|-----------|--------|
| Temporal sessions | Indefinite | Debugging historical sessions |
| Completed ledgers | 1 year | Reference for similar projects |
| Implemented plans | 1 year | Template for future planning |
| Deprecated agents | Indefinite | Architectural archaeology |
| Sandbox experiments | 90 days | Prototypes rarely referenced |
| Review artifacts | 6 months | PR context preservation |

### Cleanup Strategy

After retention period:
1. **Compress**: tar.gz old archives
2. **Move to cold storage**: S3/backup drive
3. **Update index**: Maintain searchable index of archived content

## Migration Example: Oracle → SpawnQueue

### Before Archival

```
.claude/agents/oracle.md         # Active
thoughts/ledgers/project-x.md    # References oracle.md
```

### Archival Process

1. **Mark deprecated**:
   ```markdown
   # .claude/agents/oracle.md
   ---
   status: DEPRECATED
   deprecated_date: 2025-01-01
   replacement: SpawnQueue
   ---
   ```

2. **Update references**:
   ```markdown
   # thoughts/ledgers/project-x.md
   ## Agents Used
   - ~~Oracle~~ (deprecated, now SpawnQueue)
   - Scout
   ```

3. **Archive**:
   ```bash
   mv .claude/agents/oracle.md docs/archive/agents/2025-01-01-oracle.md
   ```

4. **Add metadata**:
   ```markdown
   # docs/archive/agents/2025-01-01-oracle.md
   ---
   archived_date: 2025-01-01
   original_path: .claude/agents/oracle.md
   reason: Replaced by SpawnQueue for spawn coordination
   replacement: SpawnQueue (scripts/agentica_patterns/spawn_queue.py)
   references:
     - thoughts/ledgers/project-x.md (updated with replacement)
   ---
   ```

## Archive Index

Maintain searchable index:

```typescript
// docs/archive/INDEX.md
interface ArchiveIndex {
  agents: {
    oracle: {
      archived: '2025-01-01',
      path: 'docs/archive/agents/2025-01-01-oracle.md',
      replacement: 'SpawnQueue'
    }
  },
  temporal: {
    '2024-12-sessions': {
      archived: '2025-01-01',
      path: 'docs/archive/temporal/2024-12-sessions/',
      count: 127
    }
  }
}
```

## Monitoring

### Archive Metrics

Track:
- Archive growth rate (MB/month)
- Unarchival requests (are we archiving too aggressively?)
- Broken references after archival (validation gaps)

### Alerts

Warn if:
- Active file references archived artifact (broken reference)
- Archive size grows >10GB (compression/cleanup needed)
- Unarchival frequency >5/month (retention policy too aggressive)

## Testing

```typescript
// Test archival process
test('archive preserves all metadata', async () => {
  const original = await readFile('.claude/agents/oracle.md');
  await archiveAgent('oracle');
  const archived = await readFile('docs/archive/agents/2025-01-01-oracle.md');

  expect(archived).toContain(original);
  expect(archived).toContain('archived_date:');
  expect(archived).toContain('reason:');
});

// Test query exclusion
test('temporal queries exclude archived sessions', async () => {
  await archiveTemporalSessions({ before: '2024-12-01' });
  const results = await queryTemporalMemory('test query');

  expect(results).not.toContainSessionsBefore('2024-12-01');
});
```

## Related Decisions

From [00-architecture-decisions.md](./00-architecture-decisions.md):

- **Archive Paths**: All archives → `docs/archive/` (not thoughts/archive/)
- **18 Core Agents**: Oracle and Nexus deprecated, archived to `docs/archive/agents/`
- **SpawnQueue**: Replaces Oracle for spawn coordination
- **Routing Layer**: Replaces Nexus for task routing
- **Sandbox Integration**: Sandbox experiments → `docs/archive/sandbox-experiments/`
- **Review Workflow**: Review artifacts → `docs/archive/reviews/`

## References

- [Temporal Memory Assessment](./02-temporal-memory-assessment.md) - Temporal session archival
- [Agent Orchestration](./05-agent-orchestration.md) - Agent lifecycle (including deprecation)
- [Sandbox Environment](./14-sandbox.md) - Sandbox experiment archival
- [Architecture Map](./01-architecture-map.md) - Current vs deprecated architecture
