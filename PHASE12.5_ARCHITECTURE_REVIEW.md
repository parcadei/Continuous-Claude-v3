# Phase 12.5 Stop Hook Architecture Review
## Jury Panel Assessment

**Reviewer Role:** Architecture Validator
**Review Date:** 2025-12-28
**Files Reviewed:**
- `.claude/hooks/src/stop-swarm-coordinator.ts` (TypeScript handler)
- `.claude/hooks/stop-swarm-coordinator.sh` (Shell wrapper)
- `.claude/settings.json` (Hook registration)
- `scripts/agentica/coordination.py` (Database schema)
- `thoughts/shared/plans/2025-12-28-user-triggered-agentica.md` (Plan reference)

---

## VERDICT: NEEDS_CHANGES

**Overall Assessment:** Implementation has solid foundations but contains three architectural mismatches that must be resolved before approval.

---

## ARCHITECTURE FINDINGS

### 1. [HIGH] Database Schema Mismatch - completed_tasks Missing swarm_id

**Issue:** The Stop hook queries `completed_tasks` table for total agent count:
```sql
SELECT COUNT(DISTINCT agent_id) as total_count
FROM completed_tasks
WHERE swarm_id = ?
```

**Problem:** The actual `completed_tasks` schema in `coordination.py:50-61` has NO `swarm_id` column:
```sql
CREATE TABLE IF NOT EXISTS completed_tasks (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    pattern TEXT,
    input_summary TEXT,
    output_summary TEXT,
    output_type TEXT,
    artifacts TEXT,
    duration_ms INTEGER,
    completed_at TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);
```

**Impact:** HIGH
- Hook will execute SQL with non-existent column → Query fails silently
- `result.status !== 0` triggers graceful degradation → Always returns `continue`
- Stop hook never actually blocks, defeating its entire purpose
- Swarm completion is never detected

**Root Cause:** The plan (Phase 12.7) mentions tracking task completions but doesn't extend the schema. The hook assumes a schema that doesn't exist yet.

**Fix Required:** One of two options:

**Option A (Recommended): Track completion via agents table + broadcasts**
```
- Query agents table for SWARM_ID-linked agents
- Check broadcasts for DONE type (already exists)
- Comparison: agents with spawned_at != NULL vs broadcasts with type='done'
```

**Option B: Extend completed_tasks with swarm_id**
```sql
ALTER TABLE completed_tasks ADD COLUMN swarm_id TEXT;
CREATE INDEX idx_completed_tasks_swarm ON completed_tasks(swarm_id);
```
Then populate swarm_id when tasks are recorded (requires PostToolUse hook coordination).

---

### 2. [HIGH] Unsafe Query Parameter Passing via Shell Escaping

**Issue:** TypeScript handler uses string escaping that's vulnerable to injection:

```typescript
// Line 69-70 of stop-swarm-coordinator.ts
const result = spawnSync('python3', ['-c', query, dbPath, swarmId], {
    encoding: 'utf-8',
    maxBuffer: 1024 * 1024
});
```

**Analysis:**
- `query` is a multi-line Python script passed as a string argument
- Python receives it via `sys.argv[1]`, then executes via implicit `python3 -c "..."`
- This is ACTUALLY safe because `spawnSync()` uses argument array semantics (args are separate)
- HOWEVER: The plan comment in lines 88-89 shows intent to use `execSync` with manual escaping

**BUT** - Compare to PreToolUse hook pattern (line 600-603 of plan):
```typescript
const result = execSync(
    `python3 -c "${query.replace(/"/g, '\\"')}" "${dbPath}" "${swarmId}"`,
    ...
);
```

**Issue:** The plan shows `execSync()` with string interpolation (vulnerable), but the actual implementation uses safer `spawnSync()`. This creates consistency problem.

**Impact:** MEDIUM
- Current code is safer than planned code
- But inconsistency with PreToolUse hook creates maintenance risk
- Future developers may align to PreToolUse pattern (regressing security)

**Fix Required:**
- Add comment explaining WHY spawnSync with array is used (security best practice)
- Ensure PreToolUse hook also uses spawnSync() for consistency
- Document in code: "Use spawnSync() with array arguments, NOT execSync() with string interpolation"

---

### 3. [MEDIUM] Missing SWARM_ID Registration in agents Table

**Issue:** The plan architecture (lines 52-56) shows agents spawned with `SWARM_ID` environment variable:
```
Agents spawn with SWARM_ID environment variable
- SWARM_ID=<uuid>
- AGENT_ROLE=<specialist|coordinator>
- PATTERN_TYPE=<swarm|hierarchical|...>
```

**Problem:** There's no hook that registers the agent in the `agents` table with the SWARM_ID association. The hook only queries broadcasts and completed_tasks, with no upward link to agents.

**Impact:** MEDIUM
- `agents.id` exists but has no swarm_id field
- Can't join agents → broadcasts via swarm
- Can't track which agents belong to which swarms at agent registration time
- Requires runtime inference: "which agents did we see in broadcasts?"

**Architecture Concern:** The Stop hook is trying to count agents via completed_tasks, but agents are registered via a different table with no swarm linkage.

**Fix Required:** Either:
1. Add `swarm_id` column to `agents` table and register it in SubagentStart hook
2. Or: Rethink counting logic to use broadcasts table as source of truth for agent participation

---

### 4. [MEDIUM] Race Condition: Database Creation vs. Query

**Issue:** Lines 37-40 of stop-swarm-coordinator.ts:
```typescript
if (!existsSync(dbPath)) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
}
```

**Problem:**
- First agent in swarm doesn't have coordination.db yet (no broadcasts created)
- Stop hook runs → DB doesn't exist → returns `continue`
- User can stop immediately, preventing swarm from starting

**Impact:** LOW-MEDIUM
- Swarm startup is vulnerable in first milliseconds
- Race window is small but real in fast local execution
- More likely to affect test scenarios than real usage

**Fix Required:**
- Initialize coordination.db eagerly when SWARM_ID is detected
- OR: Return `block` (not continue) if SWARM_ID set but DB missing (indicates setup in progress)

---

### 5. [LOW] Inconsistent Error Message Language

**Issue:** Line 106 of stop-swarm-coordinator.ts:
```typescript
message: `Waiting for ${waiting} agent(s) to complete. Synthesize results when all agents broadcast 'done'.`
```

**Problem:**
- The error message assumes user understands "broadcast 'done'" concept
- Users may not have explicitly called broadcast_done() themselves
- SubagentStop hook broadcasts automatically (per plan Phase 18.5), so this is transparent to user

**Impact:** LOW
- Message is confusing but not functionally wrong
- Suggests user action that may already be happening

**Fix Required:**
- Change message to: `Waiting for ${waiting} agent(s) to complete. Use agents to finish their tasks.`
- Or document what triggers 'done' broadcasts (SubagentStop hook)

---

### 6. [LOW] Hook Lifecycle Assumption Not Documented

**Issue:** Plan line 89-94 shows Stop hook in lifecycle:
```
SubagentStop Hook (agent completion)
  ↓
Stop Hook (coordinator stop attempt)
  ↓
SessionEnd Hook (cleanup)
```

**Problem:**
- Stop hook assumes SubagentStop hook has already run for all agents
- No documentation that these must be coordinated
- No version check for Claude Code v2.0.43 (when SubagentStop became available)

**Impact:** LOW
- Architecture assumes SubagentStop exists
- If Claude Code version predates SubagentStop, this breaks
- No graceful fallback

**Fix Required:**
- Add comment: "Requires Claude Code v2.0.43+ (SubagentStop hook support)"
- Add version check if possible, or document dependency clearly

---

## RECOMMENDATIONS

### Critical Path (Must fix before approval):

1. **Resolve completed_tasks schema mismatch**
   - Decision: Use Option A (agents + broadcasts) or Option B (extend schema)
   - Prefer Option A (simpler, no migration needed)
   - Update SQL query in hook to match actual schema

2. **Document security choice (spawnSync vs execSync)**
   - Add code comment explaining array argument safety
   - Align PreToolUse hook to use same pattern
   - Create SECURITY_HOOKS.md documenting proper patterns

3. **Add swarm_id linkage to agents table**
   - Either add field + register in SubagentStart, OR
   - Document that swarm membership is inferred from broadcasts
   - Add comment explaining the design choice

### Important (Should fix before merge):

4. **Handle DB creation race condition**
   - Initialize coordination.db in SubagentStart hook
   - Add test case for fast stop scenario

5. **Improve user-facing message**
   - Clarify what "broadcast 'done'" means
   - Reference SubagentStop hook documentation

### Nice-to-have (Can follow up):

6. **Document version dependency**
   - Add comment about Claude Code v2.0.43 requirement
   - Consider adding version check in future

---

## INTEGRATION POINTS VERIFIED ✓

### Positive findings:

1. **Hook Pattern Consistency** ✓
   - Shell wrapper → TypeScript handler pattern correct
   - Compiled .mjs file exists and is up-to-date
   - Follows `.claude/hooks/` conventions properly

2. **Settings.json Registration** ✓
   - Registered at correct location: `hooks.Stop[0].hooks[0]`
   - Command path correct: `$CLAUDE_PROJECT_DIR/.claude/hooks/stop-swarm-coordinator.sh`
   - No timeout specified (correct for blocking hook)

3. **Input Validation** ✓
   - `stop_hook_active` check prevents loops correctly
   - `SAFE_ID_PATTERN` validation prevents injection (proper defense-in-depth)
   - JSON parsing has try-catch with graceful degradation

4. **Graceful Error Handling** ✓
   - Database unavailable → continue (safe)
   - Python query failure → continue (safe)
   - JSON parse error → continue (safe)
   - Uncaught exceptions → caught and logged (safe)

5. **Environment Variable Usage** ✓
   - SWARM_ID checked before use
   - CLAUDE_PROJECT_DIR with fallback to process.cwd() (correct)
   - No hardcoded paths

---

## ARCHITECTURE DIAGRAM CONSISTENCY

Comparing implementation to plan line 89-94:

```
Plan expectation:
| PreToolUse Hook (broadcast injection)
           ↓
| SubagentStop Hook (auto-broadcast done)
           ↓
| Stop Hook (block until all done) ← CURRENT REVIEW
           ↓
| SessionEnd Hook (cleanup)
```

**Status:** Architecture aligns, but implementation details don't match (schema issue #1).

---

## TESTING IMPLICATIONS

Current test strategy (plan Phase 20) will FAIL because:

1. Hook queries `completed_tasks.swarm_id` (doesn't exist)
2. Total count always returns NULL → comparison always false
3. Hook always returns `continue` (even when agents aren't done)
4. Test expecting blocking behavior gets pass-through

**Recommendation:** Fix schema issue before running integration tests.

---

## SECURITY ASSESSMENT

### Threat Model Alignment

✓ **Path traversal:** Not applicable (no file paths used)
✓ **SQL injection:** SAFE - Uses parameterized queries with `?` placeholders
✓ **Command injection:** SAFE - Uses spawnSync() with array arguments
⚠ **Timing attacks:** N/A but note: Database queries are unauthenticated (acceptable for local dev tool)
✓ **Resource exhaustion:** Agent spawn() validates separately; hook is read-only

### Security Debt

- No rate limiting (acceptable for local tool)
- No authentication (acceptable for single-developer tool)
- Broadcasts stored in plaintext (acceptable per SECURITY.md assumptions)

---

## SUMMARY TABLE

| Finding | Category | Severity | Blocking | Fix Status |
|---------|----------|----------|----------|-----------|
| Completed_tasks schema mismatch | Architecture | HIGH | YES | Requires decision |
| Query parameter safety docs | Documentation | MEDIUM | NO | Add comment |
| Missing swarm_id in agents table | Design | MEDIUM | YES | Requires schema extension |
| Database creation race condition | Robustness | MEDIUM | NO | Add initialization |
| User message clarity | UX | LOW | NO | Improve text |
| Version dependency doc | Documentation | LOW | NO | Add comment |

---

## FINAL VERDICT

**Status:** NEEDS_CHANGES

**Blocking Issues:** 3 (must resolve before merge)
- Database schema mismatch (HIGH)
- Agent/swarm linkage (MEDIUM, but required for correctness)
- Race condition on DB creation (MEDIUM)

**Non-blocking Issues:** 3 (should fix, low risk)
- Documentation/clarity items

**Recommended Action:**
1. Fix schema issue using Option A (agents + broadcasts approach)
2. Extend agents table with swarm_id OR document swarm membership inference
3. Initialize coordination.db in SubagentStart hook
4. Add security comments to spawnSync pattern
5. Re-run architecture review before approval

**Estimated remediation time:** 2-3 hours including testing

---

## ARCHITECT NOTES

The implementation shows good defensive coding practices (error handling, input validation, argument safety). The problems are primarily **schema/design gaps**, not code quality issues.

The team clearly understood the pattern and security model. The issues stem from partial implementation across multiple phases:
- Phase 12.5 (this hook) assumes completed_tasks has swarm_id
- Phase 12.7 (PostToolUse tracking) would add that column
- But they're being reviewed independently

**Recommendation to team:** When phases have data dependencies, integrate them before architecture review.

---

*Review completed by Jury Panel Architecture Validator*
*Classification: Architecture Review - NEEDS_CHANGES*
