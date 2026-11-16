# Module: Migration Rollback Strategy

## Overview

Snapshot + restore strategy for v2 → v3 migration. Full backup before migration, restore on failure.

---

## Pre-Migration Backup

```bash
#!/bin/bash
# scripts/backup_v2.sh

BACKUP_DIR="backups/v2-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# SQLite databases
cp .claude/cache/temporal-memory/temporal.db "$BACKUP_DIR/"
cp .claude/cache/coordination.db "$BACKUP_DIR/"
cp .claude/cache/learnings.db "$BACKUP_DIR/"

# Configuration
cp .claude/settings.json "$BACKUP_DIR/"
cp -r .claude/skills/ "$BACKUP_DIR/skills/"
cp -r .claude/rules/ "$BACKUP_DIR/rules/"

# Docker volumes (if any)
docker run --rm -v claude_postgres_data:/data -v $(pwd)/$BACKUP_DIR:/backup \
    alpine tar czf /backup/postgres_data.tar.gz /data

# Verify backup
echo "Backup created: $BACKUP_DIR"
ls -la "$BACKUP_DIR"
```

---

## Migration Script

```python
# scripts/migrate_v2_to_v3.py
async def migrate_to_v3(backup_dir: str):
    """Migrate from v2 to v3 with rollback on failure."""

    console.print("[bold]Starting v2 → v3 migration[/bold]")

    try:
        # Phase 1: Backup (already done)
        assert Path(backup_dir).exists(), "Backup required before migration"

        # Phase 2: Start Docker stack
        console.print("Starting Docker stack...")
        await run_docker_compose_up()

        # Phase 3: Migrate temporal memory
        console.print("Migrating temporal memory...")
        await migrate_temporal_to_postgres(
            source=f"{backup_dir}/temporal.db",
            target_url=os.environ["DATABASE_URL"]
        )

        # Phase 4: Migrate coordination DB
        console.print("Migrating coordination database...")
        await migrate_coordination_to_postgres(
            source=f"{backup_dir}/coordination.db",
            target_url=os.environ["DATABASE_URL"]
        )

        # Phase 5: Validate
        console.print("Validating migration...")
        await validate_migration()

        console.print("[green]Migration successful![/green]")

    except Exception as e:
        console.print(f"[red]Migration failed: {e}[/red]")
        console.print("Rolling back...")
        await rollback_to_v2(backup_dir)
        raise
```

---

## Rollback Procedure

```python
async def rollback_to_v2(backup_dir: str):
    """Restore v2 state from backup."""

    console.print("[yellow]Rolling back to v2...[/yellow]")

    # Stop Docker stack
    await run_command("docker-compose down -v")

    # Restore SQLite databases
    shutil.copy(f"{backup_dir}/temporal.db", ".claude/cache/temporal-memory/temporal.db")
    shutil.copy(f"{backup_dir}/coordination.db", ".claude/cache/coordination.db")
    shutil.copy(f"{backup_dir}/learnings.db", ".claude/cache/learnings.db")

    # Restore configuration
    shutil.copy(f"{backup_dir}/settings.json", ".claude/settings.json")
    shutil.rmtree(".claude/skills/")
    shutil.copytree(f"{backup_dir}/skills/", ".claude/skills/")

    console.print("[green]Rollback complete. v2 state restored.[/green]")
```

---

## Validation Checks

```python
async def validate_migration() -> bool:
    """Validate v3 migration was successful."""

    checks = [
        ("PostgreSQL connection", check_postgres_connection),
        ("Redis connection", check_redis_connection),
        ("Temporal facts migrated", check_temporal_facts_count),
        ("Coordination agents migrated", check_agents_count),
        ("Embeddings intact", check_embeddings_exist),
    ]

    all_passed = True
    for name, check_fn in checks:
        try:
            result = await check_fn()
            if result:
                console.print(f"  ✓ {name}")
            else:
                console.print(f"  ✗ {name}")
                all_passed = False
        except Exception as e:
            console.print(f"  ✗ {name}: {e}")
            all_passed = False

    return all_passed
```

---

## Usage

```bash
# 1. Create backup
./scripts/backup_v2.sh

# 2. Run migration
uv run python scripts/migrate_v2_to_v3.py --backup-dir backups/v2-20260101-120000

# 3. If migration fails, it auto-rolls back
# Manual rollback if needed:
uv run python scripts/rollback_to_v2.py --backup-dir backups/v2-20260101-120000
```
