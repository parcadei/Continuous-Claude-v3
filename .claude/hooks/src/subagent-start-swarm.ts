import { readFileSync } from 'fs';

interface SubagentStartInput {
  session_id: string;
  agent_id?: string | null;  // New in v2.0.43, may be missing in older versions
  agent_type?: string;
}

interface HookOutput {
  result: 'continue';
  message?: string;
}

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

  // Check if we're in a swarm
  const swarmId = process.env.SWARM_ID;

  // If no SWARM_ID or empty string, continue silently
  if (!swarmId) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Get agent_id, handling missing/null cases (older Claude Code versions)
  const agentId = input.agent_id ?? 'unknown';
  const agentType = input.agent_type ?? 'unknown';

  // Log for debugging - this goes to stderr, not stdout
  console.error(`[subagent-start] Agent ${agentId} (type: ${agentType}) joining swarm ${swarmId}`);

  // Always return continue - SubagentStart should never block
  const output: HookOutput = {
    result: 'continue'
  };

  console.log(JSON.stringify(output));
}

main().catch(err => {
  console.error('Uncaught error:', err);
  console.log(JSON.stringify({ result: 'continue' }));
});
