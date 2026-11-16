/**
 * SubagentStart Router - Pattern-aware hook for agent startup events.
 *
 * Routes SubagentStart hook events to pattern-specific handlers based on
 * the PATTERN_TYPE environment variable.
 *
 * Phase 4 of the pattern-aware hooks architecture.
 * See: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md
 *
 * Supported patterns:
 * - swarm: Logs agent joining, enables broadcasts
 * - jury: Injects isolation context for independent voting
 * - pipeline: Injects stage context and upstream artifacts
 * - generator_critic: Injects role context (generator/critic)
 * - hierarchical: Injects coordinator/specialist context
 * - map_reduce: Injects mapper/reducer context
 *
 * Environment Variables:
 * - PATTERN_TYPE: Pattern identifier (swarm, jury, etc.)
 * - PATTERN_ID: Unique execution ID for the pattern instance
 * - AGENT_ROLE: Role within pattern (coordinator, worker, juror, etc.)
 */

import { readFileSync } from 'fs';
import { detectPattern } from './shared/pattern-router.js';
import { registerAgent, detectAndTagSwarm } from './shared/db-utils.js';
import type { SubagentStartInput, HookOutput } from './shared/types.js';
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
import * as pipeline from './patterns/pipeline.js';

// =============================================================================
// Pattern Handlers (lazy stubs for future patterns)
// =============================================================================

/**
 * Jury pattern handler - Injects isolation context for jurors.
 *
 * Jurors should vote independently without seeing each other's votes.
 * This handler injects a system reminder about vote isolation.
 */
function handleJury(input: SubagentStartInput): HookOutput {
  const jurorIndex = process.env.JUROR_INDEX;
  const totalJurors = process.env.TOTAL_JURORS;
  const juryId = process.env.JURY_ID || process.env.PATTERN_ID;
  const isolation = process.env.JURY_ISOLATION;

  // Log to stderr for debugging
  console.error(
    `[jury] Juror ${jurorIndex} of ${totalJurors} starting for jury ${juryId}`
  );

  // Inject isolation context message
  let message = `You are Juror ${jurorIndex} of ${totalJurors} in an independent jury panel.`;
  message += ' Vote based solely on your own analysis.';
  message += ' Do not attempt to coordinate with or influence other jurors.';

  if (isolation === 'strict') {
    message += ' STRICT ISOLATION: Your vote will be recorded independently.';
  }

  return {
    result: 'continue',
    message,
  };
}

// =============================================================================
// Main Router
// =============================================================================

async function main() {
  let input: SubagentStartInput;

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

  // Detect pattern from environment, default to "task" for vanilla spawns
  const pattern = detectPattern() || 'task';

  // Register agent in coordination database (fail gracefully)
  const agentId = input.agent_id || input.session_id;
  if (agentId) {
    const result = registerAgent(
      agentId,
      input.session_id,
      pattern,
      process.pid
    );
    if (!result.success) {
      console.error(`[subagent-start] Failed to register agent: ${result.error}`);
    }

    // Auto-detect swarm pattern: if multiple agents spawned concurrently
    // in the same session, retroactively tag them as "swarm"
    if (pattern === 'task') {
      const isSwarm = detectAndTagSwarm(input.session_id);
      if (isSwarm) {
        console.error(`[subagent-start] Detected swarm pattern for session ${input.session_id}`);
      }
    }
  }

  let output: HookOutput;

  // Route to appropriate pattern handler
  switch (pattern) {
    case 'swarm':
      output = await swarm.onSubagentStart(input);
      break;

    case 'jury':
      output = await jury.onSubagentStart(input);
      break;

    case 'pipeline':
      output = await pipeline.onSubagentStart(input);
      break;

    case 'generator_critic':
      output = await generatorCritic.onSubagentStart(input);
      break;

    case 'hierarchical':
      output = await hierarchical.onSubagentStart(input);
      break;

    case 'map_reduce':
      output = await mapReduce.onSubagentStart(input);
      break;

    case 'blackboard':
      output = await blackboard.onSubagentStart(input);
      break;

    case 'circuit_breaker':
      output = await circuitBreaker.onSubagentStart(input);
      break;

    case 'chain_of_responsibility':
      output = await chainOfResponsibility.onSubagentStart(input);
      break;

    case 'adversarial':
      output = await adversarial.onSubagentStart(input);
      break;

    case 'event_driven':
      output = await eventDriven.onSubagentStart(input);
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
