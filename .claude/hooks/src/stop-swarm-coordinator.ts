import { readFileSync, existsSync } from 'fs';
import { spawnSync } from 'child_process';
import { join } from 'path';

interface StopInput {
    session_id: string;
    stop_hook_active?: boolean;
}

interface HookOutput {
    result: 'continue' | 'block';
    message?: string;
}

// Safe ID pattern: alphanumeric with hyphens/underscores, 1-64 chars
// Blocks shell metacharacters, newlines, quotes, etc.
const SAFE_ID_PATTERN = /^[a-zA-Z0-9_-]{1,64}$/;

async function main() {
    let input: StopInput;
    try {
        input = JSON.parse(readFileSync(0, 'utf-8'));
    } catch (err) {
        // Invalid JSON input - continue gracefully
        console.log(JSON.stringify({ result: 'continue' }));
        return;
    }

    // Prevent infinite loops - if we're already in a stop hook, continue
    if (input.stop_hook_active) {
        console.log(JSON.stringify({ result: 'continue' }));
        return;
    }

    // Check if we're in a swarm
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
        // Query broadcasts table only - completed_tasks may not exist in production schema.
        // Logic: Count agents that broadcast "done" vs total agents that have ever broadcast.
        // This works because every agent must broadcast at least once to participate.
        const query = `
import sqlite3
import json
import sys

db_path = sys.argv[1]
swarm_id = sys.argv[2]

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Count agents that have broadcast "done" - these have completed their work
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
        const result = spawnSync('python3', ['-c', query, dbPath, swarmId], {
            encoding: 'utf-8',
            maxBuffer: 1024 * 1024
        });

        if (result.status !== 0) {
            // Python query failed - continue gracefully
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

        if (counts.done < counts.total) {
            const waiting = counts.total - counts.done;
            console.log(JSON.stringify({
                result: 'block',
                message: `Waiting for ${waiting} agent(s) to complete. Synthesize results when all agents broadcast 'done'.`
            }));
        } else {
            console.log(JSON.stringify({ result: 'continue' }));
        }
    } catch (err) {
        console.error('Stop hook error:', err);
        console.log(JSON.stringify({ result: 'continue' }));
    }
}

main().catch(err => {
    console.error('Uncaught error:', err);
    console.log(JSON.stringify({ result: 'continue' }));
});
