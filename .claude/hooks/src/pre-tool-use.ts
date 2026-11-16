#!/usr/bin/env node
/**
 * PreToolUse Router - Routes to pattern-specific handlers based on PATTERN_TYPE env var.
 *
 * Phase 6 of pattern-aware hooks plan.
 *
 * Detects pattern type from environment and dispatches to appropriate handler:
 * - swarm: injects broadcasts from other agents
 * - jury: enforces vote isolation in strict mode
 * - pipeline: injects upstream stage artifacts
 * - Others: returns continue (graceful degradation)
 */
import { readFileSync, existsSync } from 'fs';
import { spawnSync } from 'child_process';

// Import from shared modules
import { detectPattern, isValidId, SAFE_ID_PATTERN } from './shared/pattern-router.js';
import { getDbPath, runPythonQuery } from './shared/db-utils.js';
import type { PreToolUseInput, HookOutput } from './shared/types.js';
import { readResourceState } from './shared/resource-reader.js';
import * as swarm from './patterns/swarm.js';
import * as jury from './patterns/jury.js';
import * as hierarchical from './patterns/hierarchical.js';
import * as generatorCritic from './patterns/generator-critic.js';
import * as blackboard from './patterns/blackboard.js';
import * as mapReduce from './patterns/map-reduce.js';
import * as chainOfResponsibility from './patterns/chain-of-responsibility.js';
import * as eventDriven from './patterns/event-driven.js';
import * as adversarial from './patterns/adversarial.js';

// ============================================================================
// SWARM HANDLER - Delegates to patterns/swarm.ts
// ============================================================================

async function handleSwarm(input: PreToolUseInput): Promise<HookOutput> {
  return swarm.onPreToolUse(input);
}

// ============================================================================
// JURY HANDLER - Delegates to patterns/jury.ts
// ============================================================================

async function handleJury(input: PreToolUseInput): Promise<HookOutput> {
  return jury.onPreToolUse(input);
}

// ============================================================================
// PIPELINE HANDLER - Injects upstream artifacts
// ============================================================================

async function handlePipeline(input: PreToolUseInput): Promise<HookOutput> {
  const pipelineId = process.env.PATTERN_ID;
  const stageIndex = process.env.PIPELINE_STAGE_INDEX;

  if (!pipelineId || !isValidId(pipelineId)) {
    return { result: 'continue' };
  }

  const currentStage = parseInt(stageIndex || '0', 10);
  if (currentStage === 0) {
    // First stage, no upstream artifacts
    return { result: 'continue' };
  }

  const dbPath = getDbPath();
  if (!existsSync(dbPath)) {
    return { result: 'continue' };
  }

  try {
    // Query for upstream stage artifacts
    const query = `
import sqlite3
import json
import sys

db_path = sys.argv[1]
pipeline_id = sys.argv[2]
current_stage = int(sys.argv[3])

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")
conn.row_factory = sqlite3.Row

# Get all artifacts from upstream stages
cursor = conn.execute('''
    SELECT stage_index, artifact_type, artifact_path, artifact_content, created_at
    FROM pipeline_artifacts
    WHERE pipeline_id = ? AND stage_index < ?
    ORDER BY stage_index ASC, created_at DESC
''', (pipeline_id, current_stage))

artifacts = []
for row in cursor.fetchall():
    artifacts.append({
        'stage': row['stage_index'],
        'type': row['artifact_type'],
        'path': row['artifact_path'],
        'content': row['artifact_content'],
        'time': row['created_at']
    })

print(json.dumps(artifacts))
`;

    const result = runPythonQuery(query, [dbPath, pipelineId, String(currentStage)]);

    if (!result.success) {
      return { result: 'continue' };
    }

    const artifacts = JSON.parse(result.stdout || '[]');

    if (artifacts.length > 0) {
      let contextMessage = '\n--- UPSTREAM PIPELINE ARTIFACTS ---\n';
      for (const a of artifacts) {
        contextMessage += `[Stage ${a.stage}] ${a.type}:\n`;
        if (a.path) {
          contextMessage += `  Path: ${a.path}\n`;
        }
        if (a.content) {
          try {
            const parsed = JSON.parse(a.content);
            contextMessage += `  Content: ${JSON.stringify(parsed)}\n`;
          } catch {
            contextMessage += `  Content: ${a.content}\n`;
          }
        }
      }
      contextMessage += '-----------------------------------\n';

      return {
        result: 'continue',
        message: contextMessage
      };
    }
    return { result: 'continue' };
  } catch (err) {
    return { result: 'continue' };
  }
}

// ============================================================================
// PLACEHOLDER HANDLERS - For patterns not yet implemented
// ============================================================================

async function handleGeneratorCritic(input: PreToolUseInput): Promise<HookOutput> {
  // TODO: Implement in Phase 23
  return { result: 'continue' };
}

async function handleHierarchical(input: PreToolUseInput): Promise<HookOutput> {
  // TODO: Implement in Phase 27
  return { result: 'continue' };
}

async function handleMapReduce(input: PreToolUseInput): Promise<HookOutput> {
  // TODO: Implement in Phase 31
  return { result: 'continue' };
}


async function handleCircuitBreaker(input: PreToolUseInput): Promise<HookOutput> {
  // TODO: Implement in Phase 39
  return { result: 'continue' };
}

async function handleChainOfResponsibility(input: PreToolUseInput): Promise<HookOutput> {
  // TODO: Implement in Phase 43
  return { result: 'continue' };
}

async function handleAdversarial(input: PreToolUseInput): Promise<HookOutput> {
  // TODO: Implement in Phase 47
  return { result: 'continue' };
}

async function handleEventDriven(input: PreToolUseInput): Promise<HookOutput> {
  // TODO: Implement in Phase 51
  return { result: 'continue' };
}

// ============================================================================
// MAIN ROUTER
// ============================================================================

async function main() {
  let input: PreToolUseInput;

  try {
    const rawInput = readFileSync(0, 'utf-8');
    input = JSON.parse(rawInput) as PreToolUseInput;
  } catch (err) {
    // Malformed input - return continue for graceful degradation
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // ============================================================================
  // PHASE 6: Hard Limit Block - Prevent agent spawning when at resource limit
  // ============================================================================
  if (input.tool_name === 'Task') {
    const resourceState = readResourceState();
    if (resourceState && resourceState.activeAgents >= resourceState.maxAgents) {
      console.log(JSON.stringify({
        result: 'block',
        reason: `Agent limit reached: ${resourceState.activeAgents}/${resourceState.maxAgents} agents running. ` +
          `Wait for existing agents to complete or terminate idle ones.`
      }));
      return;
    }

  }

  const patternType = detectPattern();

  if (!patternType) {
    // No pattern detected, continue without injection
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  let output: HookOutput;

  try {
    switch (patternType) {
      case 'swarm':
        output = await handleSwarm(input);
        break;
      case 'jury':
        output = await handleJury(input);
        break;
      case 'pipeline':
        output = await handlePipeline(input);
        break;
      case 'generator_critic':
        output = await generatorCritic.onPreToolUse(input);
        break;
      case 'hierarchical':
        output = await hierarchical.onPreToolUse(input);
        break;
      case 'map_reduce':
        output = await mapReduce.onPreToolUse(input);
        break;
      case 'blackboard':
        output = await blackboard.onPreToolUse(input);
        break;
      case 'circuit_breaker':
        output = await handleCircuitBreaker(input);
        break;
      case 'chain_of_responsibility':
        output = await chainOfResponsibility.onPreToolUse(input);
        break;
      case 'adversarial':
        output = await adversarial.onPreToolUse(input);
        break;
      case 'event_driven':
        output = await eventDriven.onPreToolUse(input);
        break;
      default:
        output = { result: 'continue' };
    }
  } catch (err) {
    // Handler error - graceful degradation
    output = { result: 'continue' };
  }

  console.log(JSON.stringify(output));
}

main().catch(err => {
  console.error('Uncaught error:', err);
  console.log(JSON.stringify({ result: 'continue' }));
});
