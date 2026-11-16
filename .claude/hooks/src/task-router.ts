#!/usr/bin/env node
/**
 * Task Router - Routes Task tool calls through the unified gate.
 *
 * This PreToolUse hook intercepts Task tool calls and validates them
 * through the unified 3-gate chain before execution:
 *
 * 1. Erotetic Gate - Blocks when unknowns exist in task specification
 * 2. Resources Gate - Blocks when insufficient system resources
 * 3. Composition Gate - Blocks on invalid pattern algebra
 *
 * If gates pass with high confidence (>=0.7) AND pattern detected:
 * - Block vanilla Task
 * - Return message routing to Agentica pattern
 *
 * If gates fail:
 * - ClarificationRequired: Block with unknowns message
 * - ResourcesInsufficient: Block with suggestion message
 * - CompositionInvalid: Block with errors
 *
 * If low confidence or simple task: Continue with vanilla Task
 */
import { readFileSync } from 'fs';
import { spawnSync } from 'child_process';
import type { PreToolUseInput, HookOutput } from './shared/types.js';

// Minimum confidence threshold for routing to Agentica patterns
const CONFIDENCE_THRESHOLD = 0.7;

// Gate failure types from unified_gate.py
interface GateResult {
  success: boolean;
  pattern_used?: string;
  confidence?: number;
  session_id?: string;
  aggregated_output?: unknown;
  errors?: string[];
  total_duration_ms?: number;
  gate_failure?: {
    type: 'ClarificationRequired' | 'ResourcesInsufficient' | 'CompositionInvalid';
    unknowns?: string[];
    bottleneck?: string;
    suggestion?: string;
    errors?: string[];
  };
}

/**
 * Extract the prompt from Task tool input.
 *
 * The Task tool input has a 'prompt' field containing the task description.
 */
function extractPrompt(toolInput: Record<string, unknown>): string | null {
  if (typeof toolInput.prompt === 'string') {
    return toolInput.prompt;
  }
  // Also check for 'description' as a fallback
  if (typeof toolInput.description === 'string') {
    return toolInput.description;
  }
  return null;
}

/**
 * Call unified_gate.py via CLI to validate and route the task.
 *
 * Returns the gate result or null on error.
 */
function callUnifiedGate(prompt: string, sessionId: string): GateResult | null {
  // Escape single quotes in prompt for shell safety
  const escapedPrompt = prompt.replace(/'/g, "'\\''");
  const escapedSessionId = sessionId.replace(/'/g, "'\\''");

  // Build the Python code to call orchestrate_with_gates
  const pythonCode = `
import asyncio
import json
import sys

try:
    from scripts.agentica_patterns.unified_gate import (
        orchestrate_with_gates,
        ClarificationRequired,
        ResourcesInsufficient,
        CompositionInvalid,
    )

    async def main():
        try:
            result = await orchestrate_with_gates(
                prompt='''${escapedPrompt}''',
                session_id='${escapedSessionId}',
            )
            print(json.dumps({
                'success': result.get('success', False),
                'pattern_used': result.get('pattern_used'),
                'confidence': result.get('confidence', 0.5),
                'session_id': result.get('session_id'),
                'aggregated_output': result.get('aggregated_output'),
                'errors': result.get('errors', []),
                'total_duration_ms': result.get('total_duration_ms'),
            }))
        except ClarificationRequired as e:
            print(json.dumps({
                'success': False,
                'gate_failure': {
                    'type': 'ClarificationRequired',
                    'unknowns': e.unknowns,
                },
            }))
        except ResourcesInsufficient as e:
            print(json.dumps({
                'success': False,
                'gate_failure': {
                    'type': 'ResourcesInsufficient',
                    'bottleneck': e.bottleneck,
                    'suggestion': e.suggestion,
                },
            }))
        except CompositionInvalid as e:
            print(json.dumps({
                'success': False,
                'gate_failure': {
                    'type': 'CompositionInvalid',
                    'errors': e.errors,
                },
            }))
        except Exception as e:
            print(json.dumps({
                'success': False,
                'errors': [str(e)],
            }))

    asyncio.run(main())
except ImportError as e:
    # Module not available - return success to allow vanilla Task
    import json
    print(json.dumps({'success': True, 'pattern_used': None}))
except Exception as e:
    import json
    print(json.dumps({'success': False, 'errors': [str(e)]}))
`;

  try {
    const result = spawnSync('uv', ['run', 'python', '-c', pythonCode], {
      cwd: process.env.CLAUDE_PROJECT_DIR || process.cwd(),
      encoding: 'utf-8',
      timeout: 30000, // 30 second timeout
      env: {
        ...process.env,
        PYTHONPATH: process.env.CLAUDE_PROJECT_DIR || process.cwd(),
      },
    });

    if (result.error) {
      console.error('[task-router] Failed to spawn Python:', result.error);
      return null;
    }

    if (result.status !== 0) {
      console.error('[task-router] Python exited with status:', result.status);
      console.error('[task-router] stderr:', result.stderr);
      return null;
    }

    const stdout = result.stdout.trim();
    if (!stdout) {
      return null;
    }

    return JSON.parse(stdout) as GateResult;
  } catch (err) {
    console.error('[task-router] Error calling unified gate:', err);
    return null;
  }
}

/**
 * Determine if a task is "simple" and should bypass pattern routing.
 *
 * Simple tasks are short, single-action tasks that don't benefit
 * from orchestration overhead.
 */
function isSimpleTask(prompt: string): boolean {
  // Short prompts are likely simple tasks
  if (prompt.length < 100) {
    return true;
  }

  // Tasks with explicit "simple" or "quick" keywords
  const simpleKeywords = [
    'quick check',
    'simple task',
    'just do',
    'single file',
    'one liner',
  ];

  const lowerPrompt = prompt.toLowerCase();
  return simpleKeywords.some(keyword => lowerPrompt.includes(keyword));
}

/**
 * Main handler for Task tool PreToolUse hook.
 */
async function main() {
  let input: PreToolUseInput;

  try {
    const rawInput = readFileSync(0, 'utf-8');
    if (!rawInput.trim()) {
      console.log(JSON.stringify({ result: 'continue' }));
      return;
    }
    input = JSON.parse(rawInput) as PreToolUseInput;
  } catch (err) {
    // Malformed input - continue with vanilla Task
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Only handle Task tool
  if (input.tool_name !== 'Task') {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Extract prompt from tool input
  const prompt = extractPrompt(input.tool_input);
  if (!prompt) {
    // No prompt found - continue with vanilla Task
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Skip simple tasks - not worth the overhead
  if (isSimpleTask(prompt)) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Call unified gate to validate and detect pattern
  const sessionId = input.session_id || process.env.CLAUDE_SESSION_ID || 'default';
  const gateResult = callUnifiedGate(prompt, sessionId);

  if (!gateResult) {
    // Gate call failed - continue with vanilla Task (graceful degradation)
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Handle gate failures
  if (gateResult.gate_failure) {
    const failure = gateResult.gate_failure;
    let output: HookOutput;

    switch (failure.type) {
      case 'ClarificationRequired':
        output = {
          result: 'block',
          reason: `Task requires clarification before proceeding. Unknown items: ${
            failure.unknowns?.join(', ') || 'unspecified'
          }. Please provide more details about these aspects.`,
        };
        break;

      case 'ResourcesInsufficient':
        output = {
          result: 'block',
          reason: `Insufficient resources: ${failure.bottleneck} is the bottleneck. ` +
            `Suggestion: ${failure.suggestion || 'Reduce agent count or simplify the task.'}`,
        };
        break;

      case 'CompositionInvalid':
        output = {
          result: 'block',
          reason: `Invalid pattern composition: ${
            failure.errors?.join('; ') || 'composition rules violated'
          }. Please restructure the task.`,
        };
        break;

      default:
        // Unknown failure type - continue with vanilla Task
        output = { result: 'continue' };
    }

    console.log(JSON.stringify(output));
    return;
  }

  // Check if pattern was detected with sufficient confidence
  const patternUsed = gateResult.pattern_used;
  const confidence = gateResult.confidence ?? 0;

  if (patternUsed && confidence >= CONFIDENCE_THRESHOLD) {
    // Block vanilla Task and route to Agentica pattern
    // Escape the prompt for shell safety
    const escapedPrompt = prompt.replace(/'/g, "'\\''").replace(/\n/g, ' ');
    const patternArg = patternUsed.toLowerCase().replace(/[^a-z_]/g, '_');

    const output: HookOutput = {
      result: 'block',
      reason: `🚫 Task blocked - routing to Agentica ${patternUsed} pattern (${(confidence * 100).toFixed(0)}% confidence).

**Run this instead:**
\`\`\`bash
uv run python scripts/agentica_dispatch.py --prompt '${escapedPrompt}' --pattern ${patternArg}
\`\`\`

The unified gate validated this task for pattern-based orchestration.`,
    };
    console.log(JSON.stringify(output));
    return;
  }

  // Low confidence or no pattern - continue with vanilla Task
  console.log(JSON.stringify({ result: 'continue' }));
}

main().catch(err => {
  console.error('[task-router] Uncaught error:', err);
  console.log(JSON.stringify({ result: 'continue' }));
});
