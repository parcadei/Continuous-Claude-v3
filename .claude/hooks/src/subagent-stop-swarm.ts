import { readFileSync, existsSync } from 'fs';
import { spawnSync } from 'child_process';
import { join } from 'path';

interface SubagentStopInput {
  session_id: string;
  agent_id?: string | null;  // New in v2.0.43, may be missing in older versions
  agent_type?: string;
}

interface HookOutput {
  result: 'continue';
  message?: string;
}

// Safe ID pattern: alphanumeric with hyphens/underscores, 1-64 chars
// Blocks shell metacharacters, newlines, quotes, etc.
const SAFE_ID_PATTERN = /^[a-zA-Z0-9_-]{1,64}$/;

async function main() {
  let input: SubagentStopInput;

  try {
    const rawInput = readFileSync(0, 'utf-8');
    if (!rawInput.trim()) {
      // Empty input - continue gracefully
      console.log(JSON.stringify({ result: 'continue' }));
      return;
    }
    input = JSON.parse(rawInput);
  } catch (err) {
    // Invalid JSON input - continue gracefully
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Check if we're in a swarm
  const swarmId = process.env.SWARM_ID;

  // If no SWARM_ID or empty string, continue silently
  if (!swarmId) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Validate SWARM_ID format to prevent injection
  if (!SAFE_ID_PATTERN.test(swarmId)) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Get agent_id, handling missing/null cases (older Claude Code versions)
  const agentId = input.agent_id ?? 'unknown';

  // Validate agent_id format to prevent injection
  if (!SAFE_ID_PATTERN.test(agentId)) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const dbPath = join(projectDir, '.claude', 'cache',
                      'agentica-coordination', 'coordination.db');

  if (!existsSync(dbPath)) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  try {
    // Auto-broadcast "done" message and check if all agents complete
    // Uses broadcasts table only - counts distinct agents
    const query = `
import sqlite3
import json
import sys
from datetime import datetime
from uuid import uuid4

db_path = sys.argv[1]
swarm_id = sys.argv[2]
agent_id = sys.argv[3]

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Insert done broadcast with auto flag
broadcast_id = uuid4().hex[:12]
conn.execute('''
    INSERT INTO broadcasts (id, swarm_id, sender_agent, broadcast_type, payload, created_at)
    VALUES (?, ?, ?, 'done', '{"auto": true}', ?)
''', (broadcast_id, swarm_id, agent_id, datetime.now().isoformat()))
conn.commit()

# Count agents that have broadcast "done" - distinct sender_agent
cursor = conn.execute('''
    SELECT COUNT(DISTINCT sender_agent) as done_count
    FROM broadcasts
    WHERE swarm_id = ? AND broadcast_type = 'done'
''', (swarm_id,))
done_count = cursor.fetchone()[0]

# Count total agents - any agent that has ever broadcast anything in this swarm
cursor = conn.execute('''
    SELECT COUNT(DISTINCT sender_agent) as total_count
    FROM broadcasts
    WHERE swarm_id = ?
''', (swarm_id,))
total_count = cursor.fetchone()[0]

conn.close()
print(json.dumps({'done': done_count, 'total': total_count}))
`;

    // Use spawnSync with argument array to prevent command injection
    const result = spawnSync('python3', ['-c', query, dbPath, swarmId, agentId], {
      encoding: 'utf-8',
      maxBuffer: 1024 * 1024
    });

    if (result.status !== 0) {
      // Python query failed - continue gracefully
      console.error('SubagentStop Python error:', result.stderr);
      console.log(JSON.stringify({ result: 'continue' }));
      return;
    }

    // Parse Python output - wrap in try-catch for malformed JSON safety
    let counts: { done: number; total: number };
    try {
      counts = JSON.parse(result.stdout.trim());
    } catch (parseErr) {
      // Python returned invalid JSON - continue gracefully
      console.log(JSON.stringify({ result: 'continue' }));
      return;
    }

    // Log for debugging - this goes to stderr, not stdout
    console.error(`[subagent-stop] Agent ${agentId} done. Progress: ${counts.done}/${counts.total}`);

    // Check if all agents have completed
    if (counts.done >= counts.total && counts.total > 0) {
      const output: HookOutput = {
        result: 'continue',
        message: 'All agents complete. Consider synthesizing findings into final report.'
      };
      console.log(JSON.stringify(output));
    } else {
      // Not all done yet - continue without message
      console.log(JSON.stringify({ result: 'continue' }));
    }
  } catch (err) {
    console.error('SubagentStop hook error:', err);
    console.log(JSON.stringify({ result: 'continue' }));
  }
}

main().catch(err => {
  console.error('Uncaught error:', err);
  console.log(JSON.stringify({ result: 'continue' }));
});
