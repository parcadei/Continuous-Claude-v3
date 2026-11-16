/**
 * Stop Coordinator Router - Pattern-aware hook for Stop events.
 *
 * Routes Stop hook events to pattern-specific handlers based on
 * the PATTERN_TYPE environment variable.
 *
 * Phase 10 of the pattern-aware hooks architecture.
 * See: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md
 *
 * Supported patterns:
 * - swarm: Blocks coordinator until all agents broadcast 'done'
 * - jury: Tallies votes and returns verdict summary
 * - pipeline: Synthesizes pipeline output from all stages
 * - generator_critic: Reports final iteration status
 * - hierarchical: Reports synthesis status
 * - map_reduce: Reports reducer completion
 *
 * Environment Variables:
 * - PATTERN_TYPE: Pattern identifier (swarm, jury, etc.)
 * - PATTERN_ID: Unique execution ID for the pattern instance
 * - AGENT_ROLE: Role within pattern (coordinator, worker, juror, etc.)
 */

import { readFileSync, existsSync } from 'fs';
import { detectPattern } from './shared/pattern-router.js';
import { getDbPath, runPythonQuery, isValidId } from './shared/db-utils.js';
import type { StopInput, HookOutput } from './shared/types.js';
import * as swarm from './patterns/swarm.js';
import * as jury from './patterns/jury.js';
import * as hierarchical from './patterns/hierarchical.js';
import * as generatorCritic from './patterns/generator-critic.js';
import * as blackboard from './patterns/blackboard.js';
import * as circuitBreaker from './patterns/circuit-breaker.js';
import * as mapReduce from './patterns/map-reduce.js';
import * as chainOfResponsibility from './patterns/chain-of-responsibility.js';
import * as eventDriven from './patterns/event-driven.js';
import * as adversarial from './patterns/adversarial.js';

// =============================================================================
// Jury Pattern Handler
// =============================================================================

/**
 * Jury pattern Stop handler - Tallies votes and returns verdict.
 *
 * Blocks coordinator if not all jurors have voted.
 * Returns verdict summary when all votes are in.
 */
async function handleJuryStop(input: StopInput): Promise<HookOutput> {
  // Prevent infinite loops
  if (input.stop_hook_active) {
    return { result: 'continue' };
  }

  const juryId = process.env.JURY_ID || process.env.PATTERN_ID;
  const totalJurorsStr = process.env.TOTAL_JURORS;

  if (!juryId) {
    return { result: 'continue' };
  }

  // Validate jury ID
  if (!isValidId(juryId)) {
    return { result: 'continue' };
  }

  const totalJurors = parseInt(totalJurorsStr || '0', 10);
  if (totalJurors <= 0) {
    return { result: 'continue' };
  }

  const dbPath = getDbPath();

  if (!existsSync(dbPath)) {
    return { result: 'continue' };
  }

  try {
    // Query jury votes
    const query = `
import sqlite3
import json
import sys

db_path = sys.argv[1]
jury_id = sys.argv[2]

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Check if jury_votes table exists
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jury_votes'")
if not cursor.fetchone():
    print(json.dumps({'votes': [], 'count': 0}))
    conn.close()
    exit(0)

# Get all votes for this jury
cursor = conn.execute('''
    SELECT juror_id, vote, reasoning
    FROM jury_votes
    WHERE jury_id = ?
    ORDER BY created_at
''', (jury_id,))

votes = []
for row in cursor.fetchall():
    votes.append({
        'juror': row[0],
        'vote': row[1],
        'reasoning': row[2]
    })

conn.close()
print(json.dumps({'votes': votes, 'count': len(votes)}))
`;

    const result = runPythonQuery(query, [dbPath, juryId]);

    if (!result.success) {
      console.error('Jury Stop Python error:', result.stderr);
      return { result: 'continue' };
    }

    // Parse Python output
    let voteData: { votes: Array<{juror: string; vote: string; reasoning: string}>; count: number };
    try {
      voteData = JSON.parse(result.stdout);
    } catch (parseErr) {
      return { result: 'continue' };
    }

    // Check if all jurors have voted
    if (voteData.count < totalJurors) {
      const waiting = totalJurors - voteData.count;
      return {
        result: 'block',
        message: `Waiting for ${waiting} juror(s) to vote. ${voteData.count}/${totalJurors} votes received.`
      };
    }

    // Tally votes
    const tally: Record<string, number> = {};
    for (const v of voteData.votes) {
      tally[v.vote] = (tally[v.vote] || 0) + 1;
    }

    // Find majority
    let maxVote = '';
    let maxCount = 0;
    for (const [vote, count] of Object.entries(tally)) {
      if (count > maxCount) {
        maxVote = vote;
        maxCount = count;
      }
    }

    const tallyStr = Object.entries(tally)
      .map(([v, c]) => `${v}: ${c}`)
      .join(', ');

    return {
      result: 'continue',
      message: `Jury verdict: ${maxVote} (${tallyStr}). All ${totalJurors} jurors have voted.`
    };
  } catch (err) {
    console.error('Jury Stop hook error:', err);
    return { result: 'continue' };
  }
}

// =============================================================================
// Pipeline Pattern Handler
// =============================================================================

/**
 * Pipeline pattern Stop handler - Synthesizes pipeline output.
 *
 * Returns summary of all completed stages.
 */
async function handlePipelineStop(input: StopInput): Promise<HookOutput> {
  // Prevent infinite loops
  if (input.stop_hook_active) {
    return { result: 'continue' };
  }

  const pipelineId = process.env.PATTERN_ID;
  const totalStagesStr = process.env.PIPELINE_TOTAL_STAGES;

  if (!pipelineId) {
    return { result: 'continue' };
  }

  // Validate pipeline ID
  if (!isValidId(pipelineId)) {
    return { result: 'continue' };
  }

  const dbPath = getDbPath();

  if (!existsSync(dbPath)) {
    return { result: 'continue' };
  }

  try {
    // Query pipeline stages
    const query = `
import sqlite3
import json
import sys

db_path = sys.argv[1]
pipeline_id = sys.argv[2]

conn = sqlite3.connect(db_path)

# Check if pipeline_stages table exists
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_stages'")
if not cursor.fetchone():
    print(json.dumps({'stages': [], 'completed': 0}))
    conn.close()
    exit(0)

# Get all stages for this pipeline
cursor = conn.execute('''
    SELECT stage_index, stage_name, status, output
    FROM pipeline_stages
    WHERE pipeline_id = ?
    ORDER BY stage_index
''', (pipeline_id,))

stages = []
completed = 0
for row in cursor.fetchall():
    stage = {
        'index': row[0],
        'name': row[1],
        'status': row[2],
        'output': json.loads(row[3]) if row[3] else None
    }
    stages.append(stage)
    if row[2] == 'completed':
        completed += 1

conn.close()
print(json.dumps({'stages': stages, 'completed': completed}))
`;

    const result = runPythonQuery(query, [dbPath, pipelineId]);

    if (!result.success) {
      console.error('Pipeline Stop Python error:', result.stderr);
      return { result: 'continue' };
    }

    // Parse Python output
    let pipelineData: { stages: Array<{index: number; name: string; status: string; output: unknown}>; completed: number };
    try {
      pipelineData = JSON.parse(result.stdout);
    } catch (parseErr) {
      return { result: 'continue' };
    }

    const totalStages = parseInt(totalStagesStr || '0', 10) || pipelineData.stages.length;

    // Build synthesis message
    const stageNames = pipelineData.stages.map(s => s.name || `stage-${s.index}`).join(' -> ');
    const completedCount = pipelineData.completed;

    return {
      result: 'continue',
      message: `Pipeline complete: ${completedCount}/${totalStages} stages. Stages: ${stageNames}`
    };
  } catch (err) {
    console.error('Pipeline Stop hook error:', err);
    return { result: 'continue' };
  }
}

// =============================================================================
// Generator/Critic Pattern Handler
// =============================================================================

/**
 * Generator/Critic pattern Stop handler.
 */
async function handleGeneratorCriticStop(input: StopInput): Promise<HookOutput> {
  if (input.stop_hook_active) {
    return { result: 'continue' };
  }

  const patternId = process.env.PATTERN_ID;
  const iteration = process.env.GC_ITERATION;

  console.error(`[generator_critic] Stop for ${patternId}, iteration ${iteration}`);

  return { result: 'continue' };
}

// =============================================================================
// Hierarchical Pattern Handler
// =============================================================================

/**
 * Hierarchical pattern Stop handler.
 */
async function handleHierarchicalStop(input: StopInput): Promise<HookOutput> {
  if (input.stop_hook_active) {
    return { result: 'continue' };
  }

  const patternId = process.env.PATTERN_ID;
  const role = process.env.AGENT_ROLE;

  console.error(`[hierarchical] ${role} stopping for ${patternId}`);

  return { result: 'continue' };
}

// =============================================================================
// Map/Reduce Pattern Handler
// =============================================================================

/**
 * Map/Reduce pattern Stop handler.
 */
async function handleMapReduceStop(input: StopInput): Promise<HookOutput> {
  if (input.stop_hook_active) {
    return { result: 'continue' };
  }

  const patternId = process.env.PATTERN_ID;
  const role = process.env.AGENT_ROLE;

  console.error(`[map_reduce] ${role} stopping for ${patternId}`);

  return { result: 'continue' };
}

// =============================================================================
// Main Router
// =============================================================================

async function main() {
  let input: StopInput;

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

  // Detect pattern from environment
  const pattern = detectPattern();

  let output: HookOutput;

  // Route to appropriate pattern handler
  switch (pattern) {
    case 'swarm':
      output = await swarm.onStop(input);
      break;

    case 'jury':
      output = await jury.onStop(input);
      break;

    case 'pipeline':
      output = await handlePipelineStop(input);
      break;

    case 'generator_critic':
      output = await generatorCritic.onStop(input);
      break;

    case 'hierarchical':
      output = await hierarchical.onStop(input);
      break;

    case 'map_reduce':
      output = await mapReduce.onStop(input);
      break;

    case 'blackboard':
      output = await blackboard.onStop(input);
      break;

    case 'circuit_breaker':
      output = await circuitBreaker.onStop(input);
      break;

    case 'chain_of_responsibility':
      output = await chainOfResponsibility.onStop(input);
      break;

    case 'adversarial':
      output = await adversarial.onStop(input);
      break;

    case 'event_driven':
      output = await eventDriven.onStop(input);
      break;

    default:
      // No pattern detected or unknown pattern - continue silently
      output = { result: 'continue' };
  }

  console.log(JSON.stringify(output));
}

main().catch((err) => {
  console.error('Uncaught error:', err);
  console.log(JSON.stringify({ result: 'continue' }));
});
