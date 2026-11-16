# Module: Upgrade Path (v2 → v3)

## Overview

Migration guide for existing v2 users. The setup wizard auto-detects v2 installations, backs up configurations, and migrates data.

---

## Version Comparison

| Feature | v2 | v3 |
|---------|----|----|
| Agent spawning | Task tool | `claude -p` headless |
| Coordination DB | SQLite | PostgreSQL |
| Memory | Ledger files | Ledger + Temporal + pgvector |
| Hooks | Manual registration | Auto-discovery |
| Patterns | Not implemented | 11 patterns + Sentinel |
| TUI | Basic `monitor.tui` | Full dashboard |
| Math | Not included | Optional module |

---

## Migration Steps

### 1. Backup (Automatic)

The setup wizard creates a timestamped backup:

```
.claude/backup/
└── 20260101_143022/
    ├── settings.json
    ├── skills/
    ├── hooks/
    └── cache/
```

### 2. Database Migration

#### Ledger Data → PostgreSQL

```python
# scripts/migrate_ledgers.py
async def migrate_ledgers_to_temporal():
    """Migrate ledger files to temporal memory."""

    ledger_dir = Path("thoughts/ledgers")

    for ledger_file in ledger_dir.glob("CONTINUITY_CLAUDE-*.md"):
        session_name = ledger_file.stem.replace("CONTINUITY_CLAUDE-", "")

        # Parse ledger
        ledger_content = ledger_file.read_text()
        facts = parse_ledger_to_facts(ledger_content)

        # Store in temporal memory
        store = await create_temporal_store(session_id=session_name)
        await store.record(turn=1, facts=facts)

        logger.info(f"Migrated {ledger_file.name}: {len(facts)} facts")
```

#### SQLite Coordination → PostgreSQL

```python
# scripts/migrate_coordination.py
async def migrate_coordination():
    """Migrate SQLite coordination to PostgreSQL."""

    sqlite_path = Path(".claude/cache/coordination.db")
    if not sqlite_path.exists():
        return

    # Read from SQLite
    async with aiosqlite.connect(sqlite_path) as sqlite_db:
        agents = await sqlite_db.execute_fetchall("SELECT * FROM agents")
        broadcasts = await sqlite_db.execute_fetchall("SELECT * FROM broadcasts")

    # Write to PostgreSQL
    async with pg_pool.acquire() as conn:
        for agent in agents:
            await conn.execute("""
                INSERT INTO agents (agent_id, session_id, premise, status, spawned_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT DO NOTHING
            """, *agent)

        for broadcast in broadcasts:
            await conn.execute("""
                INSERT INTO blackboard (swarm_id, sender_agent, message_type, payload)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
            """, *broadcast)
```

### 3. Hook Migration

#### Auto-Discovery Transition

v2 hooks in `settings.json` continue to work. Add auto-discovery alongside:

```json
{
  "hooks": {
    "discovery": "hybrid",  // "manual" (v2) + "auto" (v3)
    "PreToolUse": [
      // v2 manual entries preserved
      {
        "hooks": [{"command": ".claude/hooks/old-hook.sh"}]
      }
    ]
  }
}
```

#### Rename for Auto-Discovery

```bash
# v2 naming (won't auto-discover)
.claude/hooks/my-pretool-hook.sh

# v3 naming (auto-discovers)
.claude/hooks/pre-tool-use-my-hook.sh
```

Migration script:

```bash
#!/bin/bash
# scripts/migrate_hook_names.sh

cd .claude/hooks

for hook in *.sh; do
    case "$hook" in
        *pretool* | *pre-tool*)
            new_name="pre-tool-use-${hook}"
            ;;
        *posttool* | *post-tool*)
            new_name="post-tool-use-${hook}"
            ;;
        *)
            continue
            ;;
    esac

    if [[ "$hook" != "$new_name" ]]; then
        echo "Renaming $hook -> $new_name"
        mv "$hook" "$new_name"
    fi
done
```

### 4. Settings Migration

```python
# scripts/migrate_settings.py
def migrate_settings():
    """Migrate settings.json to v3 format."""

    settings_path = Path(".claude/settings.json")
    settings = json.loads(settings_path.read_text())

    # Add v3 defaults
    settings.setdefault("version", "3.0")
    settings.setdefault("hooks", {}).setdefault("discovery", "hybrid")
    settings.setdefault("database", {
        "backend": "postgres",
        "sqlite_fallback": True,
    })
    settings.setdefault("patterns", {
        "enabled": True,
        "default_timeout": 300,
    })

    # Preserve v2 settings
    # (nothing removed, only added)

    settings_path.write_text(json.dumps(settings, indent=2))
```

### 5. Skill Rules Migration

v2 skill-rules.json is compatible. Add orchestration patterns:

```python
# scripts/migrate_skill_rules.py
def migrate_skill_rules():
    """Add orchestration patterns to skill-rules.json."""

    rules_path = Path(".claude/skills/skill-rules.json")
    rules = json.loads(rules_path.read_text())

    # Upgrade version
    rules["version"] = "2.0"

    # Add orchestration section if missing
    if "orchestration" not in rules:
        rules["orchestration"] = {
            "swarm": {
                "type": "pattern",
                "description": "Parallel research",
                "promptTriggers": {
                    "keywords": ["swarm", "parallel research"],
                }
            },
            "sentinel": {
                "type": "pattern",
                "description": "Quality monitoring",
                "promptTriggers": {
                    "keywords": ["sentinel", "monitor"],
                }
            },
            # ... other patterns
        }

    rules_path.write_text(json.dumps(rules, indent=2))
```

---

## Rollback Plan

If migration fails, restore from backup:

```bash
# Restore v2 configuration
cp -r .claude/backup/YYYYMMDD_HHMMSS/* .claude/

# Remove v3 database (if created)
docker compose -f docker/docker-compose.yml down -v

# Clear any v3 cache
rm -rf .claude/cache/v3/
```

---

## Breaking Changes

| Change | Impact | Workaround |
|--------|--------|------------|
| Task tool → `claude -p` | Custom task spawning code | Update to use `spawn_agent()` |
| SQLite → PostgreSQL | Local-only setups | Set `sqlite_fallback: true` |
| Hook naming | Old hooks don't auto-discover | Rename or use hybrid mode |

---

## Compatibility Mode

Run v3 with v2 compatibility:

```json
// .claude/settings.json
{
  "compatibility": {
    "v2_mode": true,
    "use_sqlite": true,
    "manual_hooks_only": true
  }
}
```

This disables:
- PostgreSQL requirement
- Hook auto-discovery
- Pattern orchestration

Useful for gradual migration.

---

## Migration Command

```bash
# Full automated migration
uv run python scripts/setup_wizard.py --upgrade-from-v2

# Step-by-step migration
uv run python scripts/migrate_ledgers.py
uv run python scripts/migrate_coordination.py
uv run python scripts/migrate_settings.py
uv run python scripts/migrate_skill_rules.py
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/migrate_ledgers.py` | Ledger → temporal memory |
| `scripts/migrate_coordination.py` | SQLite → PostgreSQL |
| `scripts/migrate_settings.py` | Settings v2 → v3 |
| `scripts/migrate_skill_rules.py` | Add orchestration patterns |
| `scripts/migrate_hook_names.sh` | Rename for auto-discovery |

## Documentation

Update these docs for v3:
- `docs/getting-started.md` - New setup flow
- `docs/configuration.md` - New options
- `docs/patterns.md` - Pattern usage guide
- `CHANGELOG.md` - v3 release notes
