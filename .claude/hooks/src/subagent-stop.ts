/**
 * SubagentStop Router - Pattern-aware hook for agent stop events.
 *
 * Routes SubagentStop hook events to pattern-specific handlers based on
 * the PATTERN_TYPE environment variable.
 *
 * Phase 8 of the pattern-aware hooks architecture.
 * See: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md
 *
 * Supported patterns:
 * - swarm: Broadcasts 'done' message, checks quorum
 * - jury: Handles vote submission, tracks completion
 * - pipeline: Tracks stage completion
 * - generator_critic: Tracks iteration completion
 * - hierarchical: Notifies coordinator of specialist completion
 * - map_reduce: Tracks mapper completion, triggers reducer
 *
 * Environment Variables:
 * - PATTERN_TYPE: Pattern identifier (swarm, jury, etc.)
 * - PATTERN_ID: Unique execution ID for the pattern instance
 * - AGENT_ROLE: Role within pattern (coordinator, worker, juror, etc.)
 */

import { readFileSync } from 'fs';
import { detectPattern } from './shared/pattern-router.js';
import { completeAgent } from './shared/db-utils.js';
import type { SubagentStopInput, HookOutput } from './shared/types.js';
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
// Pattern Handlers (lazy stubs for future patterns)
// =============================================================================

/**
 * Jury pattern handler - Handles juror completion.
 *
 * Logs when a juror completes its voting process.
 */
function handleJury(input: SubagentStopInput): HookOutput {
  const jurorIndex = process.env.JUROR_INDEX;
  const totalJurors = process.env.TOTAL_JURORS;
  const juryId = process.env.JURY_ID || process.env.PATTERN_ID;

  // Log to stderr for debugging
  console.error(
    `[jury] Juror ${jurorIndex} of ${totalJurors} completed for jury ${juryId}`
  );

  return {
    result: 'continue',
    message: `Juror ${jurorIndex} vote submitted.`,
  };
}

/**
 * Pipeline pattern handler - Tracks stage completion.
 */
function handlePipeline(input: SubagentStopInput): HookOutput {
  const stageIndex = process.env.PIPELINE_STAGE_INDEX;
  const totalStages = process.env.PIPELINE_TOTAL_STAGES;
  const pipelineId = process.env.PATTERN_ID;

  console.error(
    `[pipeline] Stage ${stageIndex} of ${totalStages} completed for pipeline ${pipelineId}`
  );

  return { result: 'continue' };
}

/**
 * Generator/Critic pattern handler - Tracks iteration completion.
 */
function handleGeneratorCritic(input: SubagentStopInput): HookOutput {
  const role = process.env.AGENT_ROLE; // 'generator' or 'critic'
  const iteration = process.env.GC_ITERATION;
  const patternId = process.env.PATTERN_ID;

  console.error(
    `[generator_critic] ${role} completed iteration ${iteration} for ${patternId}`
  );

  return { result: 'continue' };
}

/**
 * Hierarchical pattern handler - Notifies coordinator of specialist completion.
 */
function handleHierarchical(input: SubagentStopInput): HookOutput {
  const role = process.env.AGENT_ROLE; // 'coordinator' or 'specialist'
  const coordinatorId = process.env.COORDINATOR_ID;
  const level = process.env.HIERARCHY_LEVEL;
  const patternId = process.env.PATTERN_ID;

  console.error(
    `[hierarchical] ${role} at level ${level} completed for ${patternId}`
  );

  return { result: 'continue' };
}

/**
 * Map/Reduce pattern handler - Tracks mapper completion.
 */
function handleMapReduce(input: SubagentStopInput): HookOutput {
  const role = process.env.AGENT_ROLE; // 'mapper' or 'reducer'
  const mapperIndex = process.env.MAPPER_INDEX;
  const totalMappers = process.env.TOTAL_MAPPERS;
  const patternId = process.env.PATTERN_ID;

  console.error(
    `[map_reduce] ${role} ${mapperIndex}/${totalMappers} completed for ${patternId}`
  );

  return { result: 'continue' };
}


/**
 * Circuit Breaker pattern handler - Tracks primary/fallback completion.
 */
function handleCircuitBreaker(input: SubagentStopInput): HookOutput {
  const role = process.env.AGENT_ROLE; // 'primary' or 'fallback'
  const circuitState = process.env.CIRCUIT_STATE;
  const patternId = process.env.PATTERN_ID;

  console.error(
    `[circuit_breaker] ${role} completed (circuit ${circuitState}) for ${patternId}`
  );

  return { result: 'continue' };
}

/**
 * Chain of Responsibility pattern handler - Tracks handler completion.
 */
function handleChainOfResponsibility(input: SubagentStopInput): HookOutput {
  const priority = process.env.HANDLER_PRIORITY;
  const chainLength = process.env.CHAIN_LENGTH;
  const patternId = process.env.PATTERN_ID;

  console.error(
    `[chain_of_responsibility] Handler ${priority}/${chainLength} completed for ${patternId}`
  );

  return { result: 'continue' };
}

/**
 * Adversarial pattern handler - Tracks advocate/adversary/judge completion.
 */
function handleAdversarial(input: SubagentStopInput): HookOutput {
  const role = process.env.AGENT_ROLE; // 'advocate', 'adversary', or 'judge'
  const round = process.env.ADVERSARIAL_ROUND;
  const patternId = process.env.PATTERN_ID;

  console.error(
    `[adversarial] ${role} completed round ${round} for ${patternId}`
  );

  return { result: 'continue' };
}

/**
 * Event Driven pattern handler - Tracks publisher/subscriber completion.
 */
function handleEventDriven(input: SubagentStopInput): HookOutput {
  const role = process.env.AGENT_ROLE; // 'publisher' or 'subscriber'
  const patternId = process.env.PATTERN_ID;

  console.error(`[event_driven] ${role} completed for ${patternId}`);

  return { result: 'continue' };
}

// =============================================================================
// Main Router
// =============================================================================

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

  // Complete agent in coordination database (fail gracefully)
  const agentId = input.agent_id || input.session_id;
  if (agentId) {
    const result = completeAgent(agentId, 'completed');
    if (!result.success) {
      console.error(`[subagent-stop] Failed to complete agent: ${result.error}`);
    }
  }

  // Detect pattern from environment
  const pattern = detectPattern();

  let output: HookOutput;

  // Route to appropriate pattern handler
  switch (pattern) {
    case 'swarm':
      output = await swarm.onSubagentStop(input);
      break;

    case 'jury':
      output = await jury.onSubagentStop(input);
      break;

    case 'pipeline':
      output = handlePipeline(input);
      break;

    case 'generator_critic':
      output = await generatorCritic.onSubagentStop(input);
      break;

    case 'hierarchical':
      output = await hierarchical.onSubagentStop(input);
      break;

    case 'map_reduce':
      output = await mapReduce.onSubagentStop(input);
      break;

    case 'blackboard':
      output = await blackboard.onSubagentStop(input);
      break;

    case 'circuit_breaker':
      output = await circuitBreaker.onSubagentStop(input);
      break;

    case 'chain_of_responsibility':
      output = await chainOfResponsibility.onSubagentStop(input);
      break;

    case 'adversarial':
      output = await adversarial.onSubagentStop(input);
      break;

    case 'event_driven':
      output = await eventDriven.onSubagentStop(input);
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
