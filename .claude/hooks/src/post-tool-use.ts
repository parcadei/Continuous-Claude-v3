#!/usr/bin/env node
/**
 * PostToolUse Router - Routes to pattern-specific handlers based on PATTERN_TYPE env var.
 *
 * Phase 55 of pattern-aware hooks plan.
 *
 * Detects pattern type from environment and dispatches to appropriate handler:
 * - swarm: logs broadcasts and task completions
 * - jury: tracks vote submissions
 * - pipeline: captures stage artifacts
 * - circuit_breaker: detects failures from tool responses
 * - event_driven: captures published events
 * - Others: pattern-specific post-tool logic
 */
import { readFileSync } from 'fs';

// Import from shared modules
import { detectPattern } from './shared/pattern-router.js';
import type { PostToolUseInput, HookOutput } from './shared/types.js';
import * as swarm from './patterns/swarm.js';
import * as jury from './patterns/jury.js';
import * as pipeline from './patterns/pipeline.js';
import * as generatorCritic from './patterns/generator-critic.js';
import * as hierarchical from './patterns/hierarchical.js';
import * as mapReduce from './patterns/map-reduce.js';
import * as blackboard from './patterns/blackboard.js';
import * as circuitBreaker from './patterns/circuit-breaker.js';
import * as chainOfResponsibility from './patterns/chain-of-responsibility.js';
import * as adversarial from './patterns/adversarial.js';
import * as eventDriven from './patterns/event-driven.js';

// ============================================================================
// MAIN ROUTER
// ============================================================================

async function main() {
  let input: PostToolUseInput;

  try {
    const rawInput = readFileSync(0, 'utf-8');
    input = JSON.parse(rawInput) as PostToolUseInput;
  } catch (err) {
    // Malformed input - return continue for graceful degradation
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  const patternType = detectPattern();

  if (!patternType) {
    // No pattern detected, continue without processing
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  let output: HookOutput;

  try {
    switch (patternType) {
      case 'swarm':
        output = await swarm.onPostToolUse(input);
        break;
      case 'jury':
        output = await jury.onPostToolUse(input);
        break;
      case 'pipeline':
        output = await pipeline.onPostToolUse(input);
        break;
      case 'generator_critic':
        output = await generatorCritic.onPostToolUse(input);
        break;
      case 'hierarchical':
        output = await hierarchical.onPostToolUse(input);
        break;
      case 'map_reduce':
        output = await mapReduce.onPostToolUse(input);
        break;
      case 'blackboard':
        output = await blackboard.onPostToolUse(input);
        break;
      case 'circuit_breaker':
        output = await circuitBreaker.onPostToolUse(input);
        break;
      case 'chain_of_responsibility':
        output = await chainOfResponsibility.onPostToolUse(input);
        break;
      case 'adversarial':
        output = await adversarial.onPostToolUse(input);
        break;
      case 'event_driven':
        output = await eventDriven.onPostToolUse(input);
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
