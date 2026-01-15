/**
 * PostToolUse Hook - Updates session heartbeat for coordination layer.
 *
 * This hook:
 * 1. Updates the session's last_heartbeat timestamp in PostgreSQL
 * 2. Updates the project field if session ID was reused from another project
 * 3. Runs on every tool use to keep the session marked as active
 *
 * Part of the coordination layer architecture (Phase 1).
 */

import { runPgQuery } from './shared/db-utils-pg.js';
import { readSessionId, getProject } from './shared/session-id.js';
import type { HookOutput } from './shared/types.js';

/**
 * Main entry point for the heartbeat hook.
 * Updates session heartbeat in the database.
 */
export function main(): void {
  // Skip if coordination is disabled
  if (process.env.CONTINUOUS_CLAUDE_COORDINATION !== 'true') {
    console.log(JSON.stringify({ result: 'continue' } as HookOutput));
    return;
  }

  // Use readSessionId() directly - returns null if no persisted session
  // (getSessionId() always returns a value via fallback, which would cause
  // UPDATE to silently affect 0 rows if the ID doesn't exist in DB)
  const sessionId = readSessionId();
  const project = getProject();

  // Skip if no persisted session ID - nothing to update
  if (!sessionId) {
    console.log(JSON.stringify({ result: 'continue' } as HookOutput));
    return;
  }

  // Update heartbeat and project field
  // NOTE: We match only on session ID (not project) because a session ID might
  // be reused when switching projects. Updating the project field ensures the
  // session is associated with the current project.
  const pythonCode = `
import sys
import asyncio
import asyncpg
import os

session_id = sys.argv[1]
project = sys.argv[2]
# Connection URL from environment - no hardcoded credentials
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL')
if not pg_url:
    print('CONTINUOUS_CLAUDE_DB_URL or DATABASE_URL not set', file=sys.stderr)
    sys.exit(1)

async def main():
    try:
        # 5 second timeout to avoid hanging on unreachable DB
        conn = await asyncio.wait_for(asyncpg.connect(pg_url), timeout=5.0)
    except asyncio.TimeoutError:
        print('connection_timeout', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'connection_error: {e}', file=sys.stderr)
        sys.exit(1)
    try:
        result = await conn.execute('''
            UPDATE sessions
            SET last_heartbeat = NOW(), project = $2
            WHERE id = $1
        ''', session_id, project)
        # Check if any row was updated
        if result == 'UPDATE 0':
            print('no_session_found', file=sys.stderr)
        else:
            print('ok')
    finally:
        await conn.close()

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [sessionId, project]);
  if (!result.success && result.stderr) {
    console.error(`[heartbeat] WARNING: ${result.stderr}`);
  }

  console.log(JSON.stringify({ result: 'continue' } as HookOutput));
}

main();
