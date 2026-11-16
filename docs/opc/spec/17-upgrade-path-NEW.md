# 17. Upgrade Path

> **Architecture Reference**: See [00-architecture-decisions.md](./00-architecture-decisions.md) for authoritative decisions (113+ decisions from Round 3 interviews).

## CRITICAL: OPC is a Fresh Repository

**One-Person Cloud (OPC) is NOT a v2 upgrade of the existing repo.**

- OPC = New greenfield repository
- Clean slate implementation
- Zero backward compatibility constraints
- Migration docs below apply ONLY to v2 users wanting to move to OPC

If you're starting fresh, just clone OPC. The upgrade path is for existing v2 users only.

---

## For Existing v2 Users: Migration to OPC

### Version Strategy

**Semantic Versioning:**
- v1.x = Current implementation (hooks/skills/ledgers)
- v2.0 = Refactored architecture (OPC - fresh repo)
- Breaking changes documented in CHANGELOG.md

### Migration Checklist

**Phase 1: Preparation**
```bash
# Backup current state
cp -r .claude .claude.backup
cp -r thoughts thoughts.backup

# Archive temporal memory
npm run temporal:archive --session-id all

# Export ledgers
find thoughts/ledgers -name "*.md" -exec cp {} /tmp/ledgers-backup/ \;
```

**Phase 2: Install OPC**
```bash
# Clone fresh OPC repository (NOT upgrade in place)
git clone https://github.com/cosimo/one-person-cloud.git
cd one-person-cloud

# Setup wizard (handles .env, SQLite, MCP servers)
npm run setup:wizard
```

**Phase 3: Migrate Data**
```bash
# Import ledgers
npm run migrate:ledgers --from /tmp/ledgers-backup

# Import temporal memory
npm run migrate:temporal --from /path/to/v1/thoughts/memory

# Import skills (auto-converts to v2 format)
npm run migrate:skills --from /path/to/v1/.claude/skills
```

**Phase 4: Verify**
```bash
# Smoke tests
npm run test:integration

# Verify ledgers queryable
npm run ledger:list

# Check temporal memory
npm run temporal:query --limit 10
```

### Breaking Changes (v1 → v2 / OPC)

**Hooks:**
- Shell → TypeScript migration
- New hook event types
- Settings schema change

**Skills:**
- SKILL.md v5 → v6 format
- Trigger patterns now in skill-rules.json
- Allowed-tools validation stricter

**Ledgers:**
- File format unchanged
- New SQLite index for queries
- Archival system for old ledgers

**Temporal Memory:**
- PostgreSQL replaces SQLite (for v2 OPC only)
- Schema migration automatic
- Fact embeddings preserved

### Rollback Plan

See [22-migration-rollback.md](./22-migration-rollback.md) for detailed rollback procedures.

**Quick rollback:**
```bash
# Restore v1 backup
rm -rf .claude thoughts
cp -r .claude.backup .claude
cp -r thoughts.backup thoughts

# Restart Claude Code
claude restart
```

### Compatibility Matrix

| Feature | v1.x | v2.0 (OPC) | Notes |
|---------|------|------|-------|
| Hooks (shell) | ✓ | Deprecated | Migrate to TypeScript |
| Hooks (TS) | - | ✓ | New format |
| Skills v5 | ✓ | ✓ | Auto-upgrade |
| Skills v6 | - | ✓ | New features |
| Ledgers | ✓ | ✓ | Same format |
| Temporal (SQLite) | ✓ | ✓ | Legacy mode |
| Temporal (Postgres) | - | ✓ | Production |
| Agentica | ✓ | ✓ | Same API |

### Migration Scripts

**scripts/migrate_v1_to_v2.py:**
```python
"""
Migrates v1 data to v2 (OPC) format.

Usage:
  python scripts/migrate_v1_to_v2.py --from /path/to/v1 --to /path/to/opc

Steps:
1. Copy ledgers (no format change)
2. Migrate skills (v5 → v6)
3. Migrate temporal memory (SQLite → Postgres)
4. Migrate hooks (shell → TypeScript)
5. Update settings.json schema
"""
```

**Hooks migration:**
```bash
# Auto-convert shell hooks to TypeScript
npm run migrate:hooks --from /path/to/v1/.claude/hooks
```

**Skills migration:**
```bash
# Auto-upgrade SKILL.md v5 → v6
npm run migrate:skills --from /path/to/v1/.claude/skills
```

### User Communication

**Announce v2 (OPC) release:**
- Blog post explaining OPC is a new repo
- Migration guide for v1 users
- Breaking changes highlighted
- Rollback instructions provided

**Deprecation timeline:**
- v1.x: Security fixes only (6 months)
- v2.0 (OPC): Active development
- v1.x EOL: 12 months post-v2 release

### Testing Migration

**Integration test suite:**
```bash
# Test v1 → v2 (OPC) migration
npm run test:migration

# Verify data integrity
npm run verify:ledgers
npm run verify:temporal
npm run verify:skills
```

**Manual verification:**
1. Load ledger from v1 backup - should parse correctly
2. Query temporal fact from v1 - should retrieve
3. Trigger skill from v1 - should activate (upgraded format)
4. Run hook from v1 - should warn + suggest migration

### Documentation Updates

**Update these docs for v2 (OPC):**
- README.md - Add "Upgrading from v1" section
- CHANGELOG.md - List all breaking changes
- CONTRIBUTING.md - Update dev setup for v2
- .claude/skills/*/SKILL.md - Update version references

### Support Channels

**For migration issues:**
- GitHub Discussions: "v1 → v2 Migration"
- Discord: #migration-help channel
- Email: support@opc.dev (escalations)

**Common migration issues:**
- Hook event mismatches → Auto-migrate script
- Skill trigger conflicts → skill-rules.json validator
- Temporal schema errors → Manual SQL fixes

---

## Summary

- **OPC = Fresh repo, not in-place upgrade**
- Migration path provided for v1 users
- Automated migration scripts for all components
- Rollback plan tested and documented
- 12-month support window for v1.x
- Breaking changes clearly communicated
