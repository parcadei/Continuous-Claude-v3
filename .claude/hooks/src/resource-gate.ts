/**
 * Resource Gate Hook (Gate 2)
 * Checks system resources before Task tool execution
 */

import { readFileSync } from 'fs';

interface PreToolUseInput {
  tool_name: string;
  tool_input: Record<string, unknown>;
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

  // Only check resources for Task tool
  if (input.tool_name !== 'Task') {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  try {
    // Call Python resource check
    const { execSync } = await import('child_process');
    const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();

    const result = execSync(
      `cd "${projectDir}" && uv run python -c "
from scripts.agentica_patterns.dynamic_resources import DynamicAllocator, ResourceCircuitBreaker
from scripts.resource_profiler import ResourceProfiler

profiler = ResourceProfiler()
allocator = DynamicAllocator(profiler)
breaker = ResourceCircuitBreaker()

can_spawn, reason = breaker.can_spawn()
if not can_spawn:
    print('BLOCK:' + reason)
else:
    max_agents = allocator.calculate_max_agents()
    print('OK:' + str(max_agents))
"`,
      { encoding: 'utf-8', timeout: 5000 }
    ).trim();

    if (result.startsWith('BLOCK:')) {
      const output: HookOutput = {
        result: 'block',
        message: `Resource Gate: ${result.slice(6)}`
      };
      console.log(JSON.stringify(output));
    } else {
      const output: HookOutput = {
        result: 'continue',
        message: `R:✓ max_agents=${result.slice(3)}`
      };
      console.log(JSON.stringify(output));
    }
  } catch (error) {
    // Graceful degradation - allow if check fails
    console.log(JSON.stringify({
      result: 'continue',
      message: 'R:? (check failed, allowing)'
    }));
  }
}

main().catch(() => {
  console.log(JSON.stringify({ result: 'continue' }));
});
