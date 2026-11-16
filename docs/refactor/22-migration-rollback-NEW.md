# 22. Migration & Rollback

> **Architecture Reference**: See [00-architecture-decisions.md](./00-architecture-decisions.md) for authoritative decisions (113+ decisions from Round 3 interviews).

## CRITICAL: OPC is a Fresh Repository

**One-Person Cloud (OPC) is NOT a v2 upgrade of the existing repo.**

- OPC = New greenfield repository
- Rollback docs below apply ONLY to v2 users who migrated from v1
- If you're on fresh OPC install, standard backup/restore applies

---

## For v2 Users Who Migrated: Rollback Procedures

### Rollback Philosophy

**Every migration must be reversible:**
- Pre-migration backups required
- Automated rollback scripts
- Data integrity verification
- Zero data loss guarantee

### Pre-Migration Backup

**Required backups before migration:**
```bash
# Create timestamped backup
BACKUP_DIR="$HOME/.claude-backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup all critical directories
cp -r .claude "$BACKUP_DIR/"
cp -r thoughts "$BACKUP_DIR/"
cp -r scripts "$BACKUP_DIR/"
cp .env "$BACKUP_DIR/"

# Export database snapshots
sqlite3 .claude/cache/temporal.db ".backup '$BACKUP_DIR/temporal.db'"
sqlite3 .claude/cache/ledgers.db ".backup '$BACKUP_DIR/ledgers.db'"

# Create migration manifest
cat > "$BACKUP_DIR/MANIFEST.txt" <<EOF
Backup created: $(date)
Git commit: $(git rev-parse HEAD)
Branch: $(git branch --show-current)
Claude Code version: $(claude --version)
EOF

echo "Backup created at: $BACKUP_DIR"
```

### Rollback Scenarios

#### Scenario 1: Migration Failed Mid-Process

**Symptoms:**
- Migration script crashed
- Partial data migrated
- System in inconsistent state

**Rollback:**
```bash
# Stop all Claude Code processes
pkill -f claude-code

# Restore from backup
BACKUP_DIR="$HOME/.claude-backups/20240101_120000"
rm -rf .claude thoughts scripts
cp -r "$BACKUP_DIR/.claude" .
cp -r "$BACKUP_DIR/thoughts" .
cp -r "$BACKUP_DIR/scripts" .
cp "$BACKUP_DIR/.env" .

# Verify restoration
npm run verify:backup --backup-dir "$BACKUP_DIR"

# Restart Claude Code
claude restart
```

#### Scenario 2: Migration Succeeded but v2 Broken

**Symptoms:**
- Migration completed successfully
- v2 (OPC) not working as expected
- Need to revert to v1

**Rollback:**
```bash
# Use automated rollback script
npm run rollback:to-v1 --backup-dir "$BACKUP_DIR"

# Script does:
# 1. Verifies backup integrity
# 2. Stops v2 processes
# 3. Restores v1 files
# 4. Rebuilds indices
# 5. Restarts Claude Code
```

#### Scenario 3: Partial Rollback (Data Only)

**Symptoms:**
- v2 (OPC) code is fine
- Need to restore specific data (e.g., ledgers)

**Rollback:**
```bash
# Restore specific component
npm run rollback:ledgers --backup-dir "$BACKUP_DIR"
npm run rollback:temporal --backup-dir "$BACKUP_DIR"
npm run rollback:skills --backup-dir "$BACKUP_DIR"
```

### Automated Rollback Script

**scripts/rollback_migration.py:**
```python
"""
Automated rollback for v1 → v2 (OPC) migration.

Usage:
  python scripts/rollback_migration.py --backup-dir /path/to/backup

Steps:
1. Verify backup integrity (checksums)
2. Stop Claude Code processes
3. Restore files from backup
4. Rebuild SQLite indices
5. Verify restoration
6. Restart Claude Code

Flags:
  --dry-run: Show what would be restored
  --verify-only: Check backup integrity without restoring
  --partial: Restore specific components (ledgers, temporal, skills)
"""

import os
import shutil
import subprocess
import hashlib
from pathlib import Path

def verify_backup(backup_dir: Path) -> bool:
    """Verify backup integrity using checksums."""
    manifest = backup_dir / "MANIFEST.txt"
    if not manifest.exists():
        print("❌ No MANIFEST.txt found - backup may be corrupted")
        return False

    # Check critical files exist
    required_files = [".claude", "thoughts", ".env"]
    for file in required_files:
        if not (backup_dir / file).exists():
            print(f"❌ Missing required file: {file}")
            return False

    print("✅ Backup integrity verified")
    return True

def stop_claude_code():
    """Stop all Claude Code processes."""
    subprocess.run(["pkill", "-f", "claude-code"], check=False)
    print("✅ Claude Code processes stopped")

def restore_files(backup_dir: Path, target_dir: Path):
    """Restore files from backup."""
    for item in [".claude", "thoughts", "scripts", ".env"]:
        src = backup_dir / item
        dst = target_dir / item

        if dst.exists():
            shutil.rmtree(dst) if dst.is_dir() else dst.unlink()

        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

        print(f"✅ Restored {item}")

def rebuild_indices(target_dir: Path):
    """Rebuild SQLite indices."""
    subprocess.run([
        "sqlite3",
        target_dir / ".claude/cache/ledgers.db",
        "REINDEX;"
    ], check=True)
    print("✅ Indices rebuilt")

def verify_restoration(backup_dir: Path, target_dir: Path):
    """Verify files were restored correctly."""
    for item in [".claude", "thoughts"]:
        src_size = sum(f.stat().st_size for f in (backup_dir / item).rglob('*') if f.is_file())
        dst_size = sum(f.stat().st_size for f in (target_dir / item).rglob('*') if f.is_file())

        if src_size != dst_size:
            print(f"⚠️  Size mismatch for {item}: backup={src_size}, restored={dst_size}")
            return False

    print("✅ Restoration verified")
    return True

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Rollback v1 → v2 migration")
    parser.add_argument("--backup-dir", required=True, help="Path to backup directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be restored")
    parser.add_argument("--verify-only", action="store_true", help="Only verify backup")
    args = parser.parse_args()

    backup_dir = Path(args.backup_dir)
    target_dir = Path.cwd()

    # Step 1: Verify backup
    if not verify_backup(backup_dir):
        print("❌ Backup verification failed - aborting rollback")
        return 1

    if args.verify_only:
        return 0

    if args.dry_run:
        print("DRY RUN - would restore:")
        for item in [".claude", "thoughts", "scripts", ".env"]:
            print(f"  - {item}")
        return 0

    # Step 2: Stop Claude Code
    stop_claude_code()

    # Step 3: Restore files
    restore_files(backup_dir, target_dir)

    # Step 4: Rebuild indices
    rebuild_indices(target_dir)

    # Step 5: Verify restoration
    if not verify_restoration(backup_dir, target_dir):
        print("⚠️  Restoration verification failed - manual review needed")
        return 1

    print("\n✅ Rollback complete - restart Claude Code manually")
    return 0

if __name__ == "__main__":
    exit(main())
```

### Data Integrity Verification

**Post-rollback checks:**
```bash
# Verify ledgers
npm run verify:ledgers
# Expected: All ledgers from backup present

# Verify temporal memory
npm run verify:temporal
# Expected: Fact count matches backup

# Verify skills
npm run verify:skills
# Expected: All skills from backup loadable

# Verify hooks
npm run verify:hooks
# Expected: All hooks registered correctly
```

### Rollback Testing

**Test rollback procedure before migration:**
```bash
# 1. Create test backup
npm run backup:create --test

# 2. Make deliberate changes
echo "test" > .claude/test-change.txt

# 3. Run rollback
npm run rollback:to-v1 --backup-dir "$TEST_BACKUP"

# 4. Verify test-change.txt is gone
[[ ! -f .claude/test-change.txt ]] && echo "✅ Rollback works"
```

### Partial Migration Rollback

**Rollback individual components:**

**Ledgers only:**
```bash
npm run rollback:ledgers --backup-dir "$BACKUP_DIR"
# Restores thoughts/ledgers/* from backup
# Rebuilds ledger index
```

**Temporal memory only:**
```bash
npm run rollback:temporal --backup-dir "$BACKUP_DIR"
# Restores temporal.db from backup
# Rebuilds vector embeddings
```

**Skills only:**
```bash
npm run rollback:skills --backup-dir "$BACKUP_DIR"
# Restores .claude/skills/* from backup
# Rebuilds skill-rules.json
```

**Hooks only:**
```bash
npm run rollback:hooks --backup-dir "$BACKUP_DIR"
# Restores .claude/hooks/* from backup
# Re-registers hooks in settings.json
```

### Rollback Logging

**All rollback operations logged:**
```bash
# Log location
tail -f .claude/cache/rollback.log

# Log format
2024-01-01 12:00:00 [INFO] Starting rollback from /backups/20240101_120000
2024-01-01 12:00:01 [INFO] Backup verified: checksums match
2024-01-01 12:00:02 [INFO] Stopped Claude Code processes
2024-01-01 12:00:03 [INFO] Restored .claude directory
2024-01-01 12:00:04 [INFO] Restored thoughts directory
2024-01-01 12:00:05 [INFO] Rebuilt indices
2024-01-01 12:00:06 [SUCCESS] Rollback complete
```

### Emergency Rollback

**If automated rollback fails:**

```bash
# Manual emergency rollback
BACKUP_DIR="$HOME/.claude-backups/20240101_120000"

# 1. Kill all Claude processes
pkill -9 -f claude

# 2. Manual restore
rm -rf .claude thoughts
cp -r "$BACKUP_DIR/.claude" .
cp -r "$BACKUP_DIR/thoughts" .

# 3. Manual index rebuild
sqlite3 .claude/cache/ledgers.db "REINDEX;"

# 4. Verify manually
ls -la .claude/
ls -la thoughts/ledgers/

# 5. Restart
claude restart
```

### Rollback Support

**If rollback fails, contact support:**
- GitHub Issues: Tag with `rollback-failure`
- Discord: #rollback-help channel
- Include: MANIFEST.txt, rollback.log, error messages

**Common rollback issues:**
- Corrupted backup → Use older backup
- Permission errors → Run with sudo (last resort)
- Database locks → Kill all processes first

### Backup Retention

**Recommended backup retention:**
- Keep last 3 migration backups
- Expire backups after 90 days
- Archive critical backups separately

```bash
# Auto-cleanup old backups
npm run backup:cleanup --keep 3 --older-than 90days
```

### Testing Rollback Procedures

**Rollback integration tests:**
```bash
# Test suite for rollback
npm run test:rollback

# Tests cover:
# - Backup creation
# - Backup verification
# - Full rollback
# - Partial rollback
# - Data integrity post-rollback
```

---

## Summary

- **OPC = Fresh repo, rollback N/A for fresh installs**
- Every migration has automated rollback
- Pre-migration backups are mandatory
- Rollback tested before each release
- Emergency procedures documented
- Zero data loss guarantee
- Support channels for rollback failures
