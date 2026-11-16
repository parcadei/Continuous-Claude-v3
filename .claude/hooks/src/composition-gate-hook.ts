/**
 * Composition Gate Hook (Gate 3)
 * Validates pattern composition before Task tool execution
 */

import { readFileSync } from 'fs';
import { gate3Composition } from './shared/composition-gate.js';

interface PreToolUseInput {
  tool_name: string;
  tool_input: {
    subagent_type?: string;
    prompt?: string;
  };
}

interface HookOutput {
  result: 'continue' | 'block';
  message?: string;
}

async function readStdin(): Promise<string> {
  return readFileSync(0, 'utf-8');
}

async function main() {
  const input: PreToolUseInput = JSON.parse(await readStdin());

  // Only check composition for Task tool
  if (input.tool_name !== 'Task') {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  const pattern = input.tool_input?.subagent_type;

  if (!pattern) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  try {
    // Validate pattern is valid (gate3Composition throws on invalid)
    gate3Composition(pattern, pattern); // Self-compose to validate
    console.log(JSON.stringify({
      result: 'continue',
      message: `C:✓ ${pattern}`
    }));
  } catch (error) {
    // Graceful degradation
    console.log(JSON.stringify({
      result: 'continue',
      message: 'C:? (check failed, allowing)'
    }));
  }
}

main().catch(() => {
  console.log(JSON.stringify({ result: 'continue' }));
});
