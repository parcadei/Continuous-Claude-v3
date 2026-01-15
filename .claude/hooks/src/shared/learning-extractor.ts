/**
 * Learning Extractor - Shared module for auto-learning hooks
 *
 * Extracts structured learnings from conversation events and stores them.
 * Used by PostToolUse, UserPromptSubmit, and SubagentStop hooks.
 */

import { spawnSync } from 'child_process';
import { getOpcDir } from './opc-path.js';

export interface Learning {
  what: string;      // What happened
  why: string;       // Why it worked/failed
  how: string;       // Procedural steps (for replication)
  outcome: 'success' | 'failure' | 'partial';
  tags: string[];
  context?: string;  // Additional context (file paths, error messages, etc.)
}

export interface LearningEvent {
  type: 'edit' | 'test_pass' | 'test_fail' | 'user_confirm' | 'periodic' | 'agent_complete';
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_response?: Record<string, unknown>;
  session_id: string;
  turn_count?: number;
}

/**
 * Store a learning to archival memory via store_learning.py
 */
export async function storeLearning(
  learning: Learning,
  sessionId: string,
  projectDir: string
): Promise<boolean> {
  const opcDir = getOpcDir();
  if (!opcDir) return false;  // Graceful degradation

  // Build args based on outcome
  const args = [
    'run', 'python', 'scripts/core/store_learning.py',
    '--session-id', sessionId
  ];

  // Map learning to store_learning.py interface
  if (learning.outcome === 'success') {
    args.push('--worked', `${learning.what}. ${learning.how}`);
  } else if (learning.outcome === 'failure') {
    args.push('--failed', `${learning.what}. ${learning.why}`);
  } else {
    // Partial/progress - use patterns
    args.push('--patterns', `${learning.what}: ${learning.how}`);
  }

  // Add decisions if there's a why
  if (learning.why && learning.outcome !== 'failure') {
    args.push('--decisions', learning.why);
  }

  const result = spawnSync('uv', args, {
    encoding: 'utf-8',
    cwd: opcDir,
    env: {
      ...process.env,
      PYTHONPATH: opcDir
    },
    timeout: 10000
  });

  return result.status === 0;
}

/**
 * Format learning into storable content
 */
function formatLearningContent(learning: Learning): string {
  const lines: string[] = [];

  lines.push(`What: ${learning.what}`);
  lines.push(`Why: ${learning.why}`);
  lines.push(`How: ${learning.how}`);
  lines.push(`Outcome: ${learning.outcome}`);

  if (learning.context) {
    lines.push(`Context: ${learning.context}`);
  }

  return lines.join('\n');
}

/**
 * Extract learning from a test pass event
 */
export function extractTestPassLearning(
  event: LearningEvent,
  recentEdits: Array<{ file: string; description: string }>
): Learning | null {
  if (!event.tool_response) return null;

  const output = String(event.tool_response.output || '');

  // Detect test pass patterns
  const passPatterns = [
    /(\d+) passed/i,
    /tests? passed/i,
    /ok \(/i,
    /success/i,
    /\u2713/,  // checkmark
  ];

  const isPass = passPatterns.some(p => p.test(output));
  if (!isPass) return null;

  // Build learning from recent edits
  const editSummary = recentEdits
    .map(e => `${e.file}: ${e.description}`)
    .join('; ');

  return {
    what: `Tests passed after: ${editSummary || 'recent changes'}`,
    why: 'Changes addressed the failing tests',
    how: recentEdits.length > 0
      ? `Files modified: ${recentEdits.map(e => e.file).join(', ')}`
      : 'See recent edit history',
    outcome: 'success',
    tags: ['test_pass', 'fix', 'auto_extracted'],
    context: output.slice(0, 200)
  };
}

/**
 * Extract learning from user confirmation
 */
export function extractConfirmationLearning(
  prompt: string,
  recentContext: string
): Learning | null {
  // Detect confirmation patterns
  const confirmPatterns = [
    /\b(works?|working)\b/i,
    /\b(good|great|perfect|nice)\b/i,
    /\b(thanks?|thank you)\b/i,
    /\b(yes|yep|yeah)\b/i,
    /\bthat('s| is) (it|right|correct)\b/i,
  ];

  const isConfirmation = confirmPatterns.some(p => p.test(prompt));
  if (!isConfirmation) return null;

  // Need some recent context to make this meaningful
  if (!recentContext || recentContext.length < 20) return null;

  return {
    what: `User confirmed: "${prompt.slice(0, 50)}"`,
    why: 'Approach/solution worked for user',
    how: recentContext.slice(0, 300),
    outcome: 'success',
    tags: ['user_confirmed', 'solution', 'auto_extracted']
  };
}

/**
 * Generate periodic summary learning
 */
export function extractPeriodicLearning(
  turnCount: number,
  recentActions: string[],
  sessionGoal?: string
): Learning {
  return {
    what: `Turn ${turnCount} checkpoint: ${recentActions.length} actions`,
    why: sessionGoal || 'Session progress tracking',
    how: recentActions.join('; ').slice(0, 500),
    outcome: 'partial',
    tags: ['periodic', 'progress', 'procedural', 'auto_extracted']
  };
}

/**
 * Extract learning from agent completion
 */
export function extractAgentLearning(
  agentType: string,
  agentPrompt: string,
  agentResult: string
): Learning {
  return {
    what: `Agent ${agentType} completed task`,
    why: agentPrompt.slice(0, 200),
    how: `Result: ${agentResult.slice(0, 300)}`,
    outcome: agentResult.toLowerCase().includes('error') ? 'failure' : 'success',
    tags: ['agent', agentType, 'auto_extracted'],
    context: agentPrompt
  };
}

// ==================== Checkpoint Operations ====================

export interface CheckpointData {
  phase: string;
  contextUsage?: number;
  filesModified?: string[];
  unknowns?: string[];
  handoffPath?: string;
}

/**
 * Store a checkpoint to the PostgreSQL checkpoints table via checkpoint.py
 *
 * Checkpoints are designed for crash recovery and session continuity.
 * They track phase progress, context usage, and modified files.
 */
export function storeCheckpoint(
  checkpoint: CheckpointData,
  sessionId: string,
  agentId?: string
): string | null {
  const opcDir = getOpcDir();
  if (!opcDir) return null;  // Graceful degradation

  const args = [
    'run', 'python', 'scripts/core/checkpoint.py', 'create',
    '--session-id', sessionId,
    '--phase', checkpoint.phase
  ];

  if (agentId) {
    args.push('--agent-id', agentId);
  }

  if (checkpoint.contextUsage !== undefined) {
    args.push('--context-usage', checkpoint.contextUsage.toString());
  }

  if (checkpoint.filesModified && checkpoint.filesModified.length > 0) {
    // Use JSON encoding to safely pass arrays with special characters
    args.push('--files-json', JSON.stringify(checkpoint.filesModified));
  }

  if (checkpoint.unknowns && checkpoint.unknowns.length > 0) {
    args.push('--unknowns-json', JSON.stringify(checkpoint.unknowns));
  }

  if (checkpoint.handoffPath) {
    args.push('--handoff-path', checkpoint.handoffPath);
  }

  const result = spawnSync('uv', args, {
    encoding: 'utf-8',
    cwd: opcDir,
    env: {
      ...process.env,
      PYTHONPATH: opcDir
    },
    timeout: 10000
  });

  if (result.status === 0 && result.stdout) {
    // Output is "Created checkpoint: <uuid>"
    const match = result.stdout.match(/Created checkpoint: ([a-f0-9-]+)/i);
    return match ? match[1] : null;
  }

  // Debug logging on failure
  if (result.stderr) {
    console.error(`[checkpoint] storeCheckpoint failed: ${result.stderr}`);
  }

  return null;
}

/**
 * Get the latest checkpoint from the database
 */
export function getLatestCheckpoint(
  sessionId: string,
  agentId?: string
): CheckpointData | null {
  const opcDir = getOpcDir();
  if (!opcDir) return null;

  const args = [
    'run', 'python', 'scripts/core/checkpoint.py', 'get',
    '--session-id', sessionId,
    '--json'
  ];

  if (agentId) {
    args.push('--agent-id', agentId);
  }

  const result = spawnSync('uv', args, {
    encoding: 'utf-8',
    cwd: opcDir,
    env: {
      ...process.env,
      PYTHONPATH: opcDir
    },
    timeout: 10000
  });

  if (result.status === 0 && result.stdout) {
    try {
      const data = JSON.parse(result.stdout);
      return {
        phase: data.phase,
        contextUsage: data.context_usage,
        filesModified: data.files_modified,
        unknowns: data.unknowns,
        handoffPath: data.handoff_path
      };
    } catch {
      return null;
    }
  }

  return null;
}
