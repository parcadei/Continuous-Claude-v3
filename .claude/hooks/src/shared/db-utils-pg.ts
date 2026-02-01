/**
 * PostgreSQL database utilities for Claude Code hooks.
 *
 * Migrated from SQLite (db-utils.ts) to PostgreSQL.
 * Uses coordination_pg.py via Python subprocess for queries.
 *
 * Exports:
 * - getPgConnectionString(): Returns PostgreSQL connection string
 * - runPgQuery(): Executes async Python query via coordination_pg
 * - getActiveAgentCountPg(): Returns count of running agents from PostgreSQL
 * - queryBroadcasts(): Query blackboard messages for swarm coordination
 * - queryPipelineArtifacts(): Query pipeline artifacts for upstream context
 */

import { spawnSync } from 'child_process';
import type { QueryResult } from './types.js';
import { requireOpcDir } from './opc-path.js';

// Re-export SAFE_ID_PATTERN and isValidId from pattern-router for convenience
export { SAFE_ID_PATTERN, isValidId } from './pattern-router.js';

/**
 * Get the PostgreSQL connection string.
 *
 * Checks environment variables in priority order:
 * 1. CONTINUOUS_CLAUDE_DB_URL (canonical)
 * 2. DATABASE_URL (backwards compat)
 * 3. OPC_POSTGRES_URL (legacy)
 * 4. Default local development connection
 *
 * @returns PostgreSQL connection string
 */
export function getPgConnectionString(): string {
  return process.env.CONTINUOUS_CLAUDE_DB_URL ||
    process.env.DATABASE_URL ||
    process.env.OPC_POSTGRES_URL ||
    'postgresql://claude:claude_dev@localhost:5434/continuous_claude';
}

/**
 * Execute a PostgreSQL query via coordination_pg.py.
 *
 * Uses spawnSync with uv run to execute async Python code.
 * The Python code receives arguments via sys.argv.
 *
 * @param pythonCode - Python code to execute (receives args via sys.argv)
 * @param args - Arguments passed to Python (sys.argv[1], sys.argv[2], ...)
 * @returns QueryResult with success, stdout, and stderr
 */
export function runPgQuery(pythonCode: string, args: string[] = []): QueryResult {
  const opcDir = requireOpcDir();

  // Wrap the Python code to use asyncio.run() for async queries
  const wrappedCode = `
import sys
import os
import asyncio
import json

# Add opc to path for imports
sys.path.insert(0, '${opcDir.replace(/\\/g, '/')}')
os.chdir('${opcDir.replace(/\\/g, '/')}')

${pythonCode}
`;

  try {
    const result = spawnSync('uv', ['run', 'python', '-c', wrappedCode, ...args], {
      encoding: 'utf-8',
      maxBuffer: 1024 * 1024,
      timeout: 3000,  // 3 second timeout (reduced for faster startup)
      cwd: opcDir,
      env: {
        ...process.env,
        CONTINUOUS_CLAUDE_DB_URL: getPgConnectionString(),
      },
    });

    return {
      success: result.status === 0,
      stdout: result.stdout?.trim() || '',
      stderr: result.stderr || '',
    };
  } catch (err) {
    return {
      success: false,
      stdout: '',
      stderr: String(err),
    };
  }
}

/**
 * Query broadcasts/blackboard messages from PostgreSQL.
 *
 * Queries the blackboard table for messages in a swarm that
 * the current agent hasn't read yet.
 *
 * @param swarmId - Swarm identifier
 * @param agentId - Current agent identifier (to exclude from sender)
 * @param limit - Maximum number of messages to return
 * @returns Array of broadcast messages
 */
export function queryBroadcasts(
  swarmId: string,
  agentId: string,
  limit: number = 10
): { success: boolean; broadcasts: BroadcastMessage[] } {
  const pythonCode = `
from scripts.agentica_patterns.coordination_pg import CoordinationDBPg
import json

swarm_id = sys.argv[1]
agent_id = sys.argv[2]
limit = int(sys.argv[3])

async def main():
    async with CoordinationDBPg() as db:
        # Query blackboard for messages this agent hasn't read
        messages = await db.read_from_blackboard(swarm_id, agent_id)

        # Limit results
        messages = messages[:limit]

        # Convert to JSON-serializable format
        result = []
        for msg in messages:
            result.append({
                'sender': msg.sender_agent,
                'type': msg.message_type,
                'payload': msg.payload,
                'time': msg.created_at.isoformat() if msg.created_at else None
            })

        print(json.dumps(result))

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [swarmId, agentId, String(limit)]);

  if (!result.success) {
    return { success: false, broadcasts: [] };
  }

  try {
    const broadcasts = JSON.parse(result.stdout || '[]') as BroadcastMessage[];
    return { success: true, broadcasts };
  } catch {
    return { success: false, broadcasts: [] };
  }
}

/**
 * Query pipeline artifacts from PostgreSQL.
 *
 * Queries the pipeline_artifacts table for artifacts from upstream stages.
 *
 * @param pipelineId - Pipeline identifier
 * @param currentStage - Current stage index (will get artifacts from earlier stages)
 * @returns Array of pipeline artifacts
 */
export function queryPipelineArtifacts(
  pipelineId: string,
  currentStage: number
): { success: boolean; artifacts: PipelineArtifact[] } {
  const pythonCode = `
import asyncpg
import json
import os

pipeline_id = sys.argv[1]
current_stage = int(sys.argv[2])
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5432/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        # Query pipeline artifacts from upstream stages
        rows = await conn.fetch('''
            SELECT stage_index, artifact_type, artifact_path, artifact_content, created_at
            FROM pipeline_artifacts
            WHERE pipeline_id = $1 AND stage_index < $2
            ORDER BY stage_index ASC, created_at DESC
        ''', pipeline_id, current_stage)

        artifacts = []
        for row in rows:
            artifacts.append({
                'stage': row['stage_index'],
                'type': row['artifact_type'],
                'path': row['artifact_path'],
                'content': row['artifact_content'],
                'time': row['created_at'].isoformat() if row['created_at'] else None
            })

        print(json.dumps(artifacts))
    finally:
        await conn.close()

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [pipelineId, String(currentStage)]);

  if (!result.success) {
    return { success: false, artifacts: [] };
  }

  try {
    const artifacts = JSON.parse(result.stdout || '[]') as PipelineArtifact[];
    return { success: true, artifacts };
  } catch {
    return { success: false, artifacts: [] };
  }
}

/**
 * Get count of active (running) agents from PostgreSQL.
 *
 * Queries the agents table for agents with status='running'.
 *
 * @returns Number of running agents, or 0 on any error
 */
export function getActiveAgentCountPg(): number {
  const pythonCode = `
from scripts.agentica_patterns.coordination_pg import CoordinationDBPg
import json

async def main():
    async with CoordinationDBPg() as db:
        agents = await db.get_running_agents()
        print(len(agents))

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode);

  if (!result.success) {
    return 0;
  }

  const count = parseInt(result.stdout, 10);
  return isNaN(count) ? 0 : count;
}

/**
 * Register a new agent in PostgreSQL.
 *
 * @param agentId - Unique agent identifier
 * @param sessionId - Session that spawned the agent
 * @param pattern - Coordination pattern (swarm, hierarchical, etc.)
 * @param pid - Process ID for orphan detection
 * @returns Object with success boolean and any error message
 */
export function registerAgentPg(
  agentId: string,
  sessionId: string,
  pattern: string | null = null,
  pid: number | null = null
): { success: boolean; error?: string } {
  const pythonCode = `
from scripts.agentica_patterns.coordination_pg import CoordinationDBPg
import json

agent_id = sys.argv[1]
session_id = sys.argv[2]
pattern = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != 'null' else None
pid = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] != 'null' else None

async def main():
    try:
        async with CoordinationDBPg() as db:
            await db.register_agent(
                agent_id=agent_id,
                session_id=session_id,
                pattern=pattern,
                pid=pid
            )
        print('ok')
    except Exception as e:
        print(f'error: {e}')

asyncio.run(main())
`;

  const args = [
    agentId,
    sessionId,
    pattern || 'null',
    pid !== null ? String(pid) : 'null',
  ];

  const result = runPgQuery(pythonCode, args);

  if (!result.success || result.stdout !== 'ok') {
    return {
      success: false,
      error: result.stderr || result.stdout || 'Unknown error',
    };
  }

  return { success: true };
}

/**
 * Mark an agent as completed in PostgreSQL.
 *
 * @param agentId - Agent identifier to complete
 * @param status - Final status ('completed' or 'failed')
 * @param errorMessage - Optional error message for failed status
 * @returns Object with success boolean and any error message
 */
export function completeAgentPg(
  agentId: string,
  status: string = 'completed',
  errorMessage: string | null = null
): { success: boolean; error?: string } {
  const pythonCode = `
from scripts.agentica_patterns.coordination_pg import CoordinationDBPg
import json

agent_id = sys.argv[1]
status = sys.argv[2]
error_message = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != 'null' else None

async def main():
    try:
        async with CoordinationDBPg() as db:
            await db.complete_agent(
                agent_id=agent_id,
                status=status,
                result_summary=error_message
            )
        print('ok')
    except Exception as e:
        print(f'error: {e}')

asyncio.run(main())
`;

  const args = [
    agentId,
    status,
    errorMessage || 'null',
  ];

  const result = runPgQuery(pythonCode, args);

  if (!result.success || result.stdout !== 'ok') {
    return {
      success: false,
      error: result.stderr || result.stdout || 'Unknown error',
    };
  }

  return { success: true };
}

// Type definitions for broadcast messages
export interface BroadcastMessage {
  sender: string;
  type: string;
  payload: Record<string, unknown>;
  time: string | null;
}

// Type definitions for pipeline artifacts
export interface PipelineArtifact {
  stage: number;
  type: string;
  path: string | null;
  content: string | null;
  time: string | null;
}

// =============================================================================
// COORDINATION LAYER: Session Registration
// =============================================================================

/**
 * Register a session in the coordination layer.
 *
 * @param sessionId - Unique session identifier
 * @param project - Project directory path
 * @param workingOn - Description of current task
 * @returns Object with success boolean and any error message
 */
export function registerSession(
  sessionId: string,
  project: string,
  workingOn: string = ''
): { success: boolean; error?: string } {
  const pythonCode = `
import asyncpg
import os
from datetime import datetime

session_id = sys.argv[1]
project = sys.argv[2]
working_on = sys.argv[3] if len(sys.argv) > 3 else ''
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5432/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        # Create table if not exists
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                project TEXT NOT NULL,
                working_on TEXT,
                started_at TIMESTAMP DEFAULT NOW(),
                last_heartbeat TIMESTAMP DEFAULT NOW()
            )
        ''')

        # Upsert session
        await conn.execute('''
            INSERT INTO sessions (id, project, working_on, started_at, last_heartbeat)
            VALUES ($1, $2, $3, NOW(), NOW())
            ON CONFLICT (id) DO UPDATE SET
                working_on = EXCLUDED.working_on,
                last_heartbeat = NOW()
        ''', session_id, project, working_on)

        print('ok')
    finally:
        await conn.close()

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [sessionId, project, workingOn]);

  if (!result.success || result.stdout !== 'ok') {
    return {
      success: false,
      error: result.stderr || result.stdout || 'Unknown error',
    };
  }

  return { success: true };
}

/**
 * Get active sessions from the coordination layer.
 *
 * @param project - Optional project filter
 * @returns Array of active sessions
 */
export function getActiveSessions(project?: string): {
  success: boolean;
  sessions: SessionInfo[];
} {
  const pythonCode = `
import asyncpg
import os
import json
from datetime import datetime, timedelta

project_filter = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != 'null' else None
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5432/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        # Get sessions active in last 5 minutes
        cutoff = datetime.utcnow() - timedelta(minutes=5)

        if project_filter:
            rows = await conn.fetch('''
                SELECT id, project, working_on, started_at, last_heartbeat
                FROM sessions
                WHERE project = $1 AND last_heartbeat > $2
                ORDER BY started_at DESC
            ''', project_filter, cutoff)
        else:
            rows = await conn.fetch('''
                SELECT id, project, working_on, started_at, last_heartbeat
                FROM sessions
                WHERE last_heartbeat > $1
                ORDER BY started_at DESC
            ''', cutoff)

        sessions = []
        for row in rows:
            sessions.append({
                'id': row['id'],
                'project': row['project'],
                'working_on': row['working_on'],
                'started_at': row['started_at'].isoformat() if row['started_at'] else None,
                'last_heartbeat': row['last_heartbeat'].isoformat() if row['last_heartbeat'] else None
            })

        print(json.dumps(sessions))
    except Exception as e:
        print(json.dumps([]))
    finally:
        await conn.close()

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [project || 'null']);

  if (!result.success) {
    return { success: false, sessions: [] };
  }

  try {
    const sessions = JSON.parse(result.stdout || '[]') as SessionInfo[];
    return { success: true, sessions };
  } catch {
    return { success: false, sessions: [] };
  }
}

/**
 * Check if a session is still active (heartbeat within threshold).
 *
 * @param sessionId - Session ID to check
 * @param thresholdMs - Maximum age of heartbeat in milliseconds (default 5 min)
 * @returns true if session is active, false if stale or not found
 */
export function isSessionActive(
  sessionId: string,
  thresholdMs: number = 5 * 60 * 1000
): boolean {
  const thresholdSeconds = Math.floor(thresholdMs / 1000);

  const pythonCode = `
import asyncpg
import os
from datetime import datetime, timezone

session_id = sys.argv[1]
threshold_seconds = int(sys.argv[2])
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5434/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        row = await conn.fetchrow('''
            SELECT last_heartbeat FROM sessions
            WHERE id = $1
        ''', session_id)

        if not row or not row['last_heartbeat']:
            print('false')
            return

        # Check if heartbeat is within threshold
        heartbeat = row['last_heartbeat']
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        age_seconds = (now - heartbeat).total_seconds()

        if age_seconds <= threshold_seconds:
            print('true')
        else:
            print('false')
    finally:
        await conn.close()

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [sessionId, String(thresholdSeconds)]);

  if (!result.success) {
    // On error, assume not active (allow edit)
    return false;
  }

  return result.stdout.trim() === 'true';
}

// =============================================================================
// COORDINATION LAYER: File Claims
// =============================================================================

/**
 * Check if a file is claimed by another session.
 *
 * @param filePath - Path to the file
 * @param project - Project directory
 * @param mySessionId - Current session ID
 * @returns Claim info if claimed by another session
 */
export function checkFileClaim(
  filePath: string,
  project: string,
  mySessionId: string
): { claimed: boolean; claimedBy?: string; claimedAt?: string } {
  const pythonCode = `
import asyncpg
import os
import json

file_path = sys.argv[1]
project = sys.argv[2]
my_session_id = sys.argv[3]
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5432/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        # Create table if not exists
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS file_claims (
                file_path TEXT,
                project TEXT,
                session_id TEXT,
                claimed_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (file_path, project)
            )
        ''')

        row = await conn.fetchrow('''
            SELECT session_id, claimed_at FROM file_claims
            WHERE file_path = $1 AND project = $2 AND session_id != $3
        ''', file_path, project, my_session_id)

        if row:
            print(json.dumps({
                'claimed': True,
                'claimedBy': row['session_id'],
                'claimedAt': row['claimed_at'].isoformat() if row['claimed_at'] else None
            }))
        else:
            print(json.dumps({'claimed': False}))
    finally:
        await conn.close()

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [filePath, project, mySessionId]);

  if (!result.success) {
    return { claimed: false };
  }

  try {
    return JSON.parse(result.stdout || '{"claimed": false}');
  } catch {
    return { claimed: false };
  }
}

/**
 * Claim a file for the current session.
 *
 * @param filePath - Path to the file
 * @param project - Project directory
 * @param sessionId - Session claiming the file
 */
export function claimFile(
  filePath: string,
  project: string,
  sessionId: string
): { success: boolean } {
  const pythonCode = `
import asyncpg
import os

file_path = sys.argv[1]
project = sys.argv[2]
session_id = sys.argv[3]
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5432/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        await conn.execute('''
            INSERT INTO file_claims (file_path, project, session_id, claimed_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (file_path, project) DO UPDATE SET
                session_id = EXCLUDED.session_id,
                claimed_at = NOW()
        ''', file_path, project, session_id)
        print('ok')
    finally:
        await conn.close()

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [filePath, project, sessionId]);
  return { success: result.success && result.stdout === 'ok' };
}

// =============================================================================
// COORDINATION LAYER: Findings
// =============================================================================

/**
 * Broadcast a finding to the coordination layer.
 *
 * @param sessionId - Session that discovered the finding
 * @param topic - Topic/category of the finding
 * @param finding - The finding content
 * @param relevantTo - Array of files/topics this is relevant to
 */
export function broadcastFinding(
  sessionId: string,
  topic: string,
  finding: string,
  relevantTo: string[] = []
): { success: boolean } {
  const pythonCode = `
import asyncpg
import os
import json

session_id = sys.argv[1]
topic = sys.argv[2]
finding = sys.argv[3]
relevant_to = json.loads(sys.argv[4]) if len(sys.argv) > 4 else []
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5432/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        # Create table if not exists
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS findings (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                finding TEXT NOT NULL,
                relevant_to TEXT[],
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        await conn.execute('''
            INSERT INTO findings (session_id, topic, finding, relevant_to)
            VALUES ($1, $2, $3, $4)
        ''', session_id, topic, finding, relevant_to)
        print('ok')
    finally:
        await conn.close()

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [
    sessionId,
    topic,
    finding,
    JSON.stringify(relevantTo),
  ]);
  return { success: result.success && result.stdout === 'ok' };
}

/**
 * Get relevant findings for a topic or file.
 *
 * @param query - Topic or file path to search for
 * @param excludeSessionId - Session to exclude (usually current session)
 * @param limit - Maximum findings to return
 */
export function getRelevantFindings(
  query: string,
  excludeSessionId: string,
  limit: number = 5
): { success: boolean; findings: FindingInfo[] } {
  const pythonCode = `
import asyncpg
import os
import json

query = sys.argv[1]
exclude_session = sys.argv[2]
limit = int(sys.argv[3])
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5432/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        # Search by topic match or relevance
        rows = await conn.fetch('''
            SELECT session_id, topic, finding, relevant_to, created_at
            FROM findings
            WHERE session_id != $1
              AND (topic ILIKE '%' || $2 || '%'
                   OR $2 = ANY(relevant_to)
                   OR finding ILIKE '%' || $2 || '%')
            ORDER BY created_at DESC
            LIMIT $3
        ''', exclude_session, query, limit)

        findings = []
        for row in rows:
            findings.append({
                'session_id': row['session_id'],
                'topic': row['topic'],
                'finding': row['finding'],
                'relevant_to': row['relevant_to'],
                'created_at': row['created_at'].isoformat() if row['created_at'] else None
            })

        print(json.dumps(findings))
    except Exception as e:
        print(json.dumps([]))
    finally:
        await conn.close()

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [query, excludeSessionId, String(limit)]);

  if (!result.success) {
    return { success: false, findings: [] };
  }

  try {
    const findings = JSON.parse(result.stdout || '[]') as FindingInfo[];
    return { success: true, findings };
  } catch {
    return { success: false, findings: [] };
  }
}

// Type definitions for sessions
export interface SessionInfo {
  id: string;
  project: string;
  working_on: string;
  started_at: string | null;
  last_heartbeat: string | null;
}

// Type definitions for findings
export interface FindingInfo {
  session_id: string;
  topic: string;
  finding: string;
  relevant_to: string[];
  created_at: string | null;
}

// =============================================================================
// COORDINATION LAYER: Agent Messaging (LISTEN/NOTIFY)
// =============================================================================

// Type definitions for agent messages
export interface AgentMessage {
  id: number;
  channel: string;
  sender_id: string;
  recipient_id: string | null;
  message_type: string;
  payload: Record<string, unknown>;
  created_at: string | null;
  read_at: string | null;
}

/**
 * Send a message to an agent or broadcast to a channel.
 *
 * Uses PostgreSQL LISTEN/NOTIFY for real-time delivery.
 *
 * @param channel - Channel name (e.g., 'swarm_123', 'project_abc')
 * @param senderId - Sender agent/session ID
 * @param messageType - Type of message (e.g., 'task_complete', 'error', 'status')
 * @param payload - Message payload object
 * @param recipientId - Optional specific recipient (null = broadcast)
 * @returns Object with success boolean and message ID
 */
export function sendAgentMessage(
  channel: string,
  senderId: string,
  messageType: string,
  payload: Record<string, unknown> = {},
  recipientId: string | null = null
): { success: boolean; messageId?: number; error?: string } {
  const pythonCode = `
import asyncpg
import os
import json

channel = sys.argv[1]
sender_id = sys.argv[2]
message_type = sys.argv[3]
payload = json.loads(sys.argv[4])
recipient_id = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] != 'null' else None
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5434/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        # Insert message (trigger will send NOTIFY)
        row = await conn.fetchrow('''
            INSERT INTO agent_messages (channel, sender_id, recipient_id, message_type, payload)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING id
        ''', channel, sender_id, recipient_id, message_type, json.dumps(payload))

        print(json.dumps({'success': True, 'id': row['id']}))
    except Exception as e:
        print(json.dumps({'success': False, 'error': str(e)}))
    finally:
        await conn.close()

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [
    channel,
    senderId,
    messageType,
    JSON.stringify(payload),
    recipientId || 'null'
  ]);

  if (!result.success) {
    return { success: false, error: result.stderr || 'Query failed' };
  }

  try {
    const parsed = JSON.parse(result.stdout || '{}');
    if (parsed.success) {
      return { success: true, messageId: parsed.id };
    }
    return { success: false, error: parsed.error || 'Unknown error' };
  } catch {
    return { success: false, error: 'Failed to parse response' };
  }
}

/**
 * Get unread messages for an agent/session.
 *
 * @param recipientId - Recipient agent/session ID
 * @param channel - Optional channel filter
 * @param markAsRead - Whether to mark messages as read (default: true)
 * @returns Array of unread messages
 */
export function getAgentMessages(
  recipientId: string,
  channel: string | null = null,
  markAsRead: boolean = true
): { success: boolean; messages: AgentMessage[] } {
  const pythonCode = `
import asyncpg
import os
import json

recipient_id = sys.argv[1]
channel = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != 'null' else None
mark_as_read = sys.argv[3] == 'true' if len(sys.argv) > 3 else True
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5434/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        # Build query based on filters
        if channel:
            rows = await conn.fetch('''
                SELECT id, channel, sender_id, recipient_id, message_type, payload, created_at, read_at
                FROM agent_messages
                WHERE (recipient_id = $1 OR recipient_id IS NULL)
                  AND channel = $2
                  AND read_at IS NULL
                ORDER BY created_at ASC
            ''', recipient_id, channel)
        else:
            rows = await conn.fetch('''
                SELECT id, channel, sender_id, recipient_id, message_type, payload, created_at, read_at
                FROM agent_messages
                WHERE (recipient_id = $1 OR recipient_id IS NULL)
                  AND read_at IS NULL
                ORDER BY created_at ASC
            ''', recipient_id)

        messages = []
        ids = []
        for row in rows:
            ids.append(row['id'])
            messages.append({
                'id': row['id'],
                'channel': row['channel'],
                'sender_id': row['sender_id'],
                'recipient_id': row['recipient_id'],
                'message_type': row['message_type'],
                'payload': dict(row['payload']) if row['payload'] else {},
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                'read_at': None
            })

        # Mark as read if requested
        if mark_as_read and ids:
            await conn.execute('''
                UPDATE agent_messages SET read_at = NOW()
                WHERE id = ANY($1)
            ''', ids)

        print(json.dumps(messages))
    finally:
        await conn.close()

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [
    recipientId,
    channel || 'null',
    markAsRead ? 'true' : 'false'
  ]);

  if (!result.success) {
    return { success: false, messages: [] };
  }

  try {
    const messages = JSON.parse(result.stdout || '[]') as AgentMessage[];
    return { success: true, messages };
  } catch {
    return { success: false, messages: [] };
  }
}

/**
 * Subscribe to a channel and get the LISTEN command.
 *
 * Note: For real-time listening, agents need to maintain a persistent connection.
 * This function returns the SQL command to execute for LISTEN.
 *
 * @param channel - Channel name to subscribe to
 * @returns LISTEN command string
 */
export function getListenCommand(channel: string): string {
  return `LISTEN agent_${channel};`;
}

// =============================================================================
// COORDINATION LAYER: Agent Tracking (Ralph Error Escalation)
// =============================================================================

// Type definitions for agents
export interface AgentInfo {
  id: string;
  session_id: string;
  parent_agent_id: string | null;
  agent_type: string;
  status: 'running' | 'completed' | 'failed' | 'stalled';
  task_description: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  result_summary: string | null;
}

/**
 * Register a new agent for tracking.
 *
 * @param agentId - Unique agent identifier
 * @param sessionId - Parent session ID
 * @param agentType - Type of agent (kraken, spark, arbiter, etc.)
 * @param taskDescription - Description of the task
 * @param parentAgentId - Optional parent agent ID for hierarchical tracking
 */
export function trackAgent(
  agentId: string,
  sessionId: string,
  agentType: string,
  taskDescription: string | null = null,
  parentAgentId: string | null = null
): { success: boolean; error?: string } {
  const pythonCode = `
import asyncpg
import os

agent_id = sys.argv[1]
session_id = sys.argv[2]
agent_type = sys.argv[3]
task_description = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != 'null' else None
parent_agent_id = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] != 'null' else None
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5434/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        await conn.execute('''
            INSERT INTO agents (id, session_id, agent_type, task_description, parent_agent_id, status)
            VALUES ($1, $2, $3, $4, $5, 'running')
            ON CONFLICT (id) DO UPDATE SET
                status = 'running',
                task_description = EXCLUDED.task_description,
                started_at = NOW(),
                completed_at = NULL,
                error_message = NULL
        ''', agent_id, session_id, agent_type, task_description, parent_agent_id)
        print('ok')
    except Exception as e:
        print(f'error: {e}')
    finally:
        await conn.close()

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [
    agentId,
    sessionId,
    agentType,
    taskDescription || 'null',
    parentAgentId || 'null'
  ]);

  if (!result.success || result.stdout !== 'ok') {
    return { success: false, error: result.stderr || result.stdout };
  }
  return { success: true };
}

/**
 * Update agent status (completed or failed).
 *
 * @param agentId - Agent identifier
 * @param status - New status
 * @param errorMessage - Error message if failed
 * @param resultSummary - Summary of results if completed
 */
export function updateAgentStatus(
  agentId: string,
  status: 'completed' | 'failed' | 'stalled',
  errorMessage: string | null = null,
  resultSummary: string | null = null
): { success: boolean; error?: string } {
  const pythonCode = `
import asyncpg
import os

agent_id = sys.argv[1]
status = sys.argv[2]
error_message = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != 'null' else None
result_summary = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != 'null' else None
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5434/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        await conn.execute('''
            UPDATE agents SET
                status = $2,
                completed_at = NOW(),
                error_message = $3,
                result_summary = $4
            WHERE id = $1
        ''', agent_id, status, error_message, result_summary)
        print('ok')
    except Exception as e:
        print(f'error: {e}')
    finally:
        await conn.close()

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [
    agentId,
    status,
    errorMessage || 'null',
    resultSummary || 'null'
  ]);

  if (!result.success || result.stdout !== 'ok') {
    return { success: false, error: result.stderr || result.stdout };
  }
  return { success: true };
}

/**
 * Get agents for a session, optionally filtered by status.
 *
 * @param sessionId - Session ID to query
 * @param status - Optional status filter
 * @returns List of agents
 */
export function getSessionAgents(
  sessionId: string,
  status: string | null = null
): { success: boolean; agents: AgentInfo[] } {
  const pythonCode = `
import asyncpg
import os
import json

session_id = sys.argv[1]
status_filter = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != 'null' else None
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5434/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        if status_filter:
            rows = await conn.fetch('''
                SELECT id, session_id, parent_agent_id, agent_type, status,
                       task_description, started_at, completed_at, error_message, result_summary
                FROM agents
                WHERE session_id = $1 AND status = $2
                ORDER BY started_at DESC
            ''', session_id, status_filter)
        else:
            rows = await conn.fetch('''
                SELECT id, session_id, parent_agent_id, agent_type, status,
                       task_description, started_at, completed_at, error_message, result_summary
                FROM agents
                WHERE session_id = $1
                ORDER BY started_at DESC
            ''', session_id)

        agents = []
        for row in rows:
            agents.append({
                'id': row['id'],
                'session_id': row['session_id'],
                'parent_agent_id': row['parent_agent_id'],
                'agent_type': row['agent_type'],
                'status': row['status'],
                'task_description': row['task_description'],
                'started_at': row['started_at'].isoformat() if row['started_at'] else None,
                'completed_at': row['completed_at'].isoformat() if row['completed_at'] else None,
                'error_message': row['error_message'],
                'result_summary': row['result_summary']
            })
        print(json.dumps(agents))
    finally:
        await conn.close()

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [sessionId, status || 'null']);

  if (!result.success) {
    return { success: false, agents: [] };
  }

  try {
    const agents = JSON.parse(result.stdout || '[]') as AgentInfo[];
    return { success: true, agents };
  } catch {
    return { success: false, agents: [] };
  }
}

/**
 * Get failed or stalled agents that can be resumed.
 *
 * @param sessionId - Optional session filter
 * @returns List of resumable agents
 */
export function getResumableAgents(
  sessionId: string | null = null
): { success: boolean; agents: AgentInfo[] } {
  const pythonCode = `
import asyncpg
import os
import json
from datetime import datetime, timezone, timedelta

session_id = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != 'null' else None
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5434/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        # Get failed agents and stalled running agents (no update in 10 min)
        stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=10)

        if session_id:
            rows = await conn.fetch('''
                SELECT id, session_id, parent_agent_id, agent_type, status,
                       task_description, started_at, completed_at, error_message, result_summary
                FROM agents
                WHERE session_id = $1
                  AND (status IN ('failed', 'stalled')
                       OR (status = 'running' AND started_at < $2))
                ORDER BY started_at DESC
            ''', session_id, stale_threshold)
        else:
            rows = await conn.fetch('''
                SELECT id, session_id, parent_agent_id, agent_type, status,
                       task_description, started_at, completed_at, error_message, result_summary
                FROM agents
                WHERE status IN ('failed', 'stalled')
                   OR (status = 'running' AND started_at < $1)
                ORDER BY started_at DESC
                LIMIT 20
            ''', stale_threshold)

        agents = []
        for row in rows:
            agents.append({
                'id': row['id'],
                'session_id': row['session_id'],
                'parent_agent_id': row['parent_agent_id'],
                'agent_type': row['agent_type'],
                'status': row['status'] if row['status'] != 'running' else 'stalled',
                'task_description': row['task_description'],
                'started_at': row['started_at'].isoformat() if row['started_at'] else None,
                'completed_at': row['completed_at'].isoformat() if row['completed_at'] else None,
                'error_message': row['error_message'],
                'result_summary': row['result_summary']
            })
        print(json.dumps(agents))
    finally:
        await conn.close()

asyncio.run(main())
`;

  const result = runPgQuery(pythonCode, [sessionId || 'null']);

  if (!result.success) {
    return { success: false, agents: [] };
  }

  try {
    const agents = JSON.parse(result.stdout || '[]') as AgentInfo[];
    return { success: true, agents };
  } catch {
    return { success: false, agents: [] };
  }
}
