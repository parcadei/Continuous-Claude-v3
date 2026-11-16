import { readFileSync, existsSync } from 'fs';
import { spawnSync } from 'child_process';
import { join } from 'path';

interface PostToolUseInput {
    session_id: string;
    tool_name: string;
    tool_input: Record<string, unknown>;
    tool_response: unknown;
}

interface HookOutput {
    result: 'continue';
    message?: string;
}

// Safe ID pattern: alphanumeric with hyphens/underscores, 1-64 chars
// Blocks shell metacharacters, newlines, quotes, etc.
const SAFE_ID_PATTERN = /^[a-zA-Z0-9_-]{1,64}$/;

async function main() {
    let input: PostToolUseInput;
    try {
        input = JSON.parse(readFileSync(0, 'utf-8'));
    } catch (err) {
        // Invalid JSON input - continue gracefully
        console.log(JSON.stringify({ result: 'continue' }));
        return;
    }

    // Only track Task tool completions
    if (input.tool_name !== 'Task') {
        console.log(JSON.stringify({ result: 'continue' }));
        return;
    }

    const swarmId = process.env.SWARM_ID;
    if (!swarmId) {
        console.log(JSON.stringify({ result: 'continue' }));
        return;
    }

    // Validate SWARM_ID format to prevent injection
    if (!SAFE_ID_PATTERN.test(swarmId)) {
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
        // Extract agent_id from tool_response
        const response = input.tool_response as Record<string, unknown> | null;
        let agentId = 'unknown';
        if (response && typeof response === 'object' && 'agent_id' in response) {
            const rawAgentId = response.agent_id;
            if (typeof rawAgentId === 'string' && rawAgentId.length > 0) {
                agentId = rawAgentId;
            }
        }

        // Record a "started" broadcast to track which agents are in the swarm
        const insert = `
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

# Insert "started" broadcast to track this agent in the swarm
broadcast_id = uuid4().hex[:12]
payload = json.dumps({"type": "task_spawned"})
conn.execute('''
    INSERT INTO broadcasts (id, swarm_id, sender_agent, broadcast_type, payload, created_at)
    VALUES (?, ?, ?, 'started', ?, ?)
''', (broadcast_id, swarm_id, agent_id, payload, datetime.now().isoformat()))
conn.commit()
conn.close()
`;

        // Use spawnSync with argument array to prevent command injection
        const result = spawnSync('python3', ['-c', insert, dbPath, swarmId, agentId], {
            encoding: 'utf-8',
            maxBuffer: 1024 * 1024
        });

        // Even if Python fails, continue gracefully
        if (result.status !== 0) {
            console.error('Task completion tracking error:', result.stderr);
        }

        console.log(JSON.stringify({ result: 'continue' }));
    } catch (err) {
        console.error('Task completion tracking error:', err);
        console.log(JSON.stringify({ result: 'continue' }));
    }
}

main().catch(err => {
    console.error('Uncaught error:', err);
    console.log(JSON.stringify({ result: 'continue' }));
});
