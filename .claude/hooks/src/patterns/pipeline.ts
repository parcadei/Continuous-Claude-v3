/**
 * Unified Pipeline Pattern Handlers
 *
 * Implements pipeline coordination logic for sequential stage execution:
 * - onSubagentStart: Inject stage context
 * - onSubagentStop: Track stage completion
 * - onPreToolUse: Inject upstream artifacts
 * - onStop: Provide pipeline completion summary
 *
 * Environment Variables:
 * - PIPELINE_ID: Pipeline identifier (required for pipeline operations)
 * - PIPELINE_STAGE_INDEX: Index of this stage (0-indexed)
 * - PIPELINE_TOTAL_STAGES: Total number of stages in pipeline
 * - CLAUDE_PROJECT_DIR: Project directory for DB path
 */

import { existsSync } from 'fs';

// Import shared utilities
import { getDbPath, runPythonQuery, isValidId } from '../shared/db-utils.js';
import type {
  SubagentStartInput,
  SubagentStopInput,
  PreToolUseInput,
  PostToolUseInput,
  StopInput,
  HookOutput
} from '../shared/types.js';

// Re-export types for convenience
export type {
  SubagentStartInput,
  SubagentStopInput,
  PreToolUseInput,
  PostToolUseInput,
  StopInput,
  HookOutput
};

// =============================================================================
// onSubagentStart Handler
// =============================================================================

/**
 * Handles SubagentStart hook for pipeline pattern.
 * Injects stage context message.
 * Always returns 'continue' - never blocks agent start.
 */
export async function onSubagentStart(input: SubagentStartInput): Promise<HookOutput> {
  const pipelineId = process.env.PIPELINE_ID;

  // If no PIPELINE_ID, continue silently (not in a pipeline)
  if (!pipelineId) {
    return { result: 'continue' };
  }

  // Validate PIPELINE_ID format
  if (!isValidId(pipelineId)) {
    return { result: 'continue' };
  }

  const stageIndex = parseInt(process.env.PIPELINE_STAGE_INDEX || '0', 10);
  const totalStages = parseInt(process.env.PIPELINE_TOTAL_STAGES || '1', 10);

  // Log for debugging - this goes to stderr, not stdout
  console.error(`[pipeline] Stage ${stageIndex} of ${totalStages} starting for pipeline ${pipelineId}`);

  // Inject stage context message
  let message = `You are Stage ${stageIndex + 1} of ${totalStages} in a pipeline.`;

  if (stageIndex === 0) {
    message += ' This is the first stage. Process the initial input and pass your output to the next stage.';
  } else if (stageIndex === totalStages - 1) {
    message += ' This is the final stage. Process the upstream outputs and produce the final result.';
  } else {
    message += ' Process the upstream outputs and pass your results to the next stage.';
  }

  return {
    result: 'continue',
    message
  };
}

// =============================================================================
// onSubagentStop Handler
// =============================================================================

/**
 * Handles SubagentStop hook for pipeline pattern.
 * Marks stage as completed in database.
 * Injects next stage or completion message.
 */
export async function onSubagentStop(input: SubagentStopInput): Promise<HookOutput> {
  const pipelineId = process.env.PIPELINE_ID;

  // If no PIPELINE_ID, continue silently
  if (!pipelineId) {
    return { result: 'continue' };
  }

  // Validate PIPELINE_ID format
  if (!isValidId(pipelineId)) {
    return { result: 'continue' };
  }

  const agentId = input.agent_id ?? 'unknown';

  // Validate agent_id format
  if (!isValidId(agentId)) {
    return { result: 'continue' };
  }

  const stageIndex = parseInt(process.env.PIPELINE_STAGE_INDEX || '0', 10);
  const totalStages = parseInt(process.env.PIPELINE_TOTAL_STAGES || '1', 10);
  const dbPath = getDbPath();

  if (!existsSync(dbPath)) {
    return { result: 'continue' };
  }

  try {
    // Mark stage as completed and check pipeline progress
    const query = `
import sqlite3
import json
import sys
from datetime import datetime

db_path = sys.argv[1]
pipeline_id = sys.argv[2]
stage_index = sys.argv[3]
agent_id = sys.argv[4]

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Create table if not exists
conn.execute('''
    CREATE TABLE IF NOT EXISTS pipeline_stages (
        id TEXT PRIMARY KEY,
        pipeline_id TEXT NOT NULL,
        stage_index INTEGER NOT NULL,
        agent_id TEXT,
        status TEXT DEFAULT 'pending',
        output TEXT,
        created_at TEXT NOT NULL
    )
''')
conn.execute('''
    CREATE INDEX IF NOT EXISTS idx_pipeline_stages
        ON pipeline_stages(pipeline_id, stage_index)
''')

# Insert or update stage completion
stage_id = f"{pipeline_id}_stage_{stage_index}"
conn.execute('''
    INSERT OR REPLACE INTO pipeline_stages (id, pipeline_id, stage_index, agent_id, status, created_at)
    VALUES (?, ?, ?, ?, 'completed', ?)
''', (stage_id, pipeline_id, int(stage_index), agent_id, datetime.now().isoformat()))
conn.commit()

# Count completed stages
cursor = conn.execute('''
    SELECT COUNT(*) as completed_count
    FROM pipeline_stages
    WHERE pipeline_id = ? AND status = 'completed'
''', (pipeline_id,))
completed_count = cursor.fetchone()[0]

conn.close()
print(json.dumps({'completed': completed_count}))
`;

    const result = runPythonQuery(query, [dbPath, pipelineId, stageIndex.toString(), agentId]);

    if (!result.success) {
      console.error('SubagentStop Python error:', result.stderr);
      return { result: 'continue' };
    }

    // Parse Python output
    let counts: { completed: number };
    try {
      counts = JSON.parse(result.stdout);
    } catch (parseErr) {
      return { result: 'continue' };
    }

    // Log for debugging
    console.error(`[pipeline] Stage ${stageIndex} done. Progress: ${counts.completed}/${totalStages}`);

    // Check if this is the final stage
    if (stageIndex === totalStages - 1 && counts.completed >= totalStages) {
      return {
        result: 'continue',
        message: 'Pipeline complete! All stages have finished execution. Review the final output.'
      };
    } else if (counts.completed < totalStages) {
      return {
        result: 'continue',
        message: `Stage ${stageIndex + 1} complete. Pipeline progress: ${counts.completed}/${totalStages} stages done.`
      };
    }

    return { result: 'continue' };
  } catch (err) {
    console.error('SubagentStop hook error:', err);
    return { result: 'continue' };
  }
}

// =============================================================================
// onPreToolUse Handler
// =============================================================================

/**
 * Handles PreToolUse hook for pipeline pattern.
 * Injects upstream stage outputs as context.
 * Allows all tools (no blocking).
 */
export async function onPreToolUse(input: PreToolUseInput): Promise<HookOutput> {
  const pipelineId = process.env.PIPELINE_ID;

  // If no PIPELINE_ID, continue silently
  if (!pipelineId) {
    return { result: 'continue' };
  }

  // Validate PIPELINE_ID format
  if (!isValidId(pipelineId)) {
    return { result: 'continue' };
  }

  const stageIndex = parseInt(process.env.PIPELINE_STAGE_INDEX || '0', 10);
  const dbPath = getDbPath();

  // First stage has no upstream artifacts
  if (stageIndex === 0) {
    return { result: 'continue' };
  }

  if (!existsSync(dbPath)) {
    return { result: 'continue' };
  }

  try {
    // Fetch upstream stage outputs
    const query = `
import sqlite3
import json
import sys

db_path = sys.argv[1]
pipeline_id = sys.argv[2]
stage_index = sys.argv[3]

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Get all completed stages before this one
cursor = conn.execute('''
    SELECT stage_index, output
    FROM pipeline_stages
    WHERE pipeline_id = ? AND stage_index < ? AND status = 'completed'
    ORDER BY stage_index
''', (pipeline_id, int(stage_index)))

upstream = []
for row in cursor.fetchall():
    upstream.append({
        'stage': row[0],
        'output': row[1]
    })

conn.close()
print(json.dumps({'upstream': upstream}))
`;

    const result = runPythonQuery(query, [dbPath, pipelineId, stageIndex.toString()]);

    if (!result.success) {
      return { result: 'continue' };
    }

    // Parse Python output
    let data: { upstream: Array<{ stage: number; output: string | null }> };
    try {
      data = JSON.parse(result.stdout);
    } catch (parseErr) {
      return { result: 'continue' };
    }

    // Inject upstream outputs as context
    if (data.upstream.length > 0) {
      let message = 'UPSTREAM STAGE OUTPUTS:\n';
      for (const stage of data.upstream) {
        message += `\nStage ${stage.stage + 1}: ${stage.output || '(no output recorded)'}\n`;
      }
      message += '\nUse these outputs to inform your stage processing.';

      return {
        result: 'continue',
        message
      };
    }

    return { result: 'continue' };
  } catch (err) {
    console.error('PreToolUse hook error:', err);
    return { result: 'continue' };
  }
}

// =============================================================================
// onPostToolUse Handler
// =============================================================================

/**
 * Handles PostToolUse hook for pipeline pattern.
 * Currently no-op for pipeline pattern.
 */
export async function onPostToolUse(input: PostToolUseInput): Promise<HookOutput> {
  // No special handling needed for pipeline pattern
  return { result: 'continue' };
}

// =============================================================================
// onStop Handler
// =============================================================================

/**
 * Handles Stop hook for pipeline pattern.
 * Provides pipeline status summary.
 * Does not block - pipeline stages are sequential, not parallel.
 */
export async function onStop(input: StopInput): Promise<HookOutput> {
  // Prevent infinite loops - if we're already in a stop hook, continue
  if (input.stop_hook_active) {
    return { result: 'continue' };
  }

  const pipelineId = process.env.PIPELINE_ID;

  if (!pipelineId) {
    return { result: 'continue' };
  }

  // Validate PIPELINE_ID format
  if (!isValidId(pipelineId)) {
    return { result: 'continue' };
  }

  const totalStages = parseInt(process.env.PIPELINE_TOTAL_STAGES || '0', 10);
  const dbPath = getDbPath();

  if (!existsSync(dbPath)) {
    return { result: 'continue' };
  }

  try {
    // Query pipeline status
    const query = `
import sqlite3
import json
import sys

db_path = sys.argv[1]
pipeline_id = sys.argv[2]

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Count completed stages
cursor = conn.execute('''
    SELECT COUNT(*) as completed_count
    FROM pipeline_stages
    WHERE pipeline_id = ? AND status = 'completed'
''', (pipeline_id,))
completed_count = cursor.fetchone()[0]

# Get stage outputs
stages = []
cursor = conn.execute('''
    SELECT stage_index, status, output
    FROM pipeline_stages
    WHERE pipeline_id = ?
    ORDER BY stage_index
''', (pipeline_id,))
for row in cursor.fetchall():
    stages.append({
        'index': row[0],
        'status': row[1],
        'output': row[2]
    })

conn.close()
print(json.dumps({'completed': completed_count, 'stages': stages}))
`;

    const result = runPythonQuery(query, [dbPath, pipelineId]);

    if (!result.success) {
      return { result: 'continue' };
    }

    // Parse Python output
    let data: {
      completed: number;
      stages: Array<{ index: number; status: string; output: string | null }>
    };
    try {
      data = JSON.parse(result.stdout);
    } catch (parseErr) {
      return { result: 'continue' };
    }

    // Provide status summary
    let message = `Pipeline Status: ${data.completed}/${totalStages} stages completed.\n\n`;

    if (data.stages.length > 0) {
      message += 'STAGE STATUS:\n';
      for (const stage of data.stages) {
        const statusSymbol = stage.status === 'completed' ? '✓' : '○';
        message += `${statusSymbol} Stage ${stage.index + 1}: ${stage.status}\n`;
      }
    }

    if (data.completed >= totalStages) {
      message += '\nAll stages complete!';
    } else {
      message += `\n${totalStages - data.completed} stage(s) remaining.`;
    }

    return {
      result: 'continue',
      message
    };
  } catch (err) {
    console.error('Stop hook error:', err);
    return { result: 'continue' };
  }
}
