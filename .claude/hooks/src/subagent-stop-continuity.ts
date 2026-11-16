import * as fs from 'fs';
import * as path from 'path';

interface SubagentStopInput {
  session_id: string;
  transcript_path: string;
  permission_mode: string;
  hook_event_name: string;
  stop_hook_active: boolean;
}

interface TranscriptEntry {
  type: string;
  message?: {
    role: string;
    content: string | Array<{ type: string; text?: string; name?: string }>;
  };
  tool_name?: string;
  tool_input?: Record<string, unknown>;
}

async function main() {
  const input: SubagentStopInput = JSON.parse(await readStdin());
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();

  // Prevent infinite loops
  if (input.stop_hook_active) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  try {
    // Parse transcript to understand what agent did
    const agentInfo = parseTranscript(input.transcript_path);

    if (!agentInfo.agentName) {
      // Not a recognized agent, skip
      console.log(JSON.stringify({ result: 'continue' }));
      return;
    }

    // Read agent's output file if it exists
    const outputPath = path.join(
      projectDir,
      '.claude',
      'cache',
      'agents',
      agentInfo.agentName,
      'latest-output.md'
    );

    let outputSummary = '';
    if (fs.existsSync(outputPath)) {
      const content = fs.readFileSync(outputPath, 'utf-8');
      // Extract first 500 chars or executive summary
      const summaryMatch = content.match(/## Executive Summary\n([\s\S]*?)(?=\n##|$)/);
      const goalMatch = content.match(/## Goal\n([\s\S]*?)(?=\n##|$)/);
      const symptomMatch = content.match(/## Symptom\n([\s\S]*?)(?=\n##|$)/);

      outputSummary = summaryMatch?.[1]?.trim() ||
        goalMatch?.[1]?.trim() ||
        symptomMatch?.[1]?.trim() ||
        content.slice(0, 300).trim();
    }

    // Write to agent log for resumability
    writeAgentLog(projectDir, agentInfo, outputPath);

    // Append to continuity ledger
    appendToLedger(projectDir, agentInfo, outputSummary);

    const message = `[SubagentStop] ${agentInfo.agentName} completed. Report: .claude/cache/agents/${agentInfo.agentName}/latest-output.md`;
    console.log(JSON.stringify({ result: 'continue', message }));

  } catch (err) {
    // Don't break on errors, just continue
    console.log(JSON.stringify({ result: 'continue' }));
  }
}

function parseTranscript(transcriptPath: string): { agentName: string | null; task: string; agentId: string | null } {
  let agentName: string | null = null;
  let task = '';
  let agentId: string | null = null;

  try {
    if (!fs.existsSync(transcriptPath)) {
      return { agentName: null, task: '', agentId: null };
    }

    const content = fs.readFileSync(transcriptPath, 'utf-8');
    const lines = content.split('\n').filter(l => l.trim());

    // Look for Task tool invocation to find agent name
    for (const line of lines) {
      try {
        const entry: TranscriptEntry = JSON.parse(line);

        // Look for the Task tool call that spawned this agent
        if (entry.tool_name === 'Task' && entry.tool_input) {
          const subagentType = entry.tool_input.subagent_type as string;
          const prompt = entry.tool_input.prompt as string;

          // Check if it's one of our custom agents
          if ([
            'research-agent', 'plan-agent', 'debug-agent', 'rp-explorer',
            'codebase-analyzer', 'codebase-locator', 'codebase-pattern-finder', 'explore'
          ].includes(subagentType)) {
            agentName = subagentType;
            task = prompt?.slice(0, 200) || '';
            break;
          }
        }

        // Also check for agent file references in messages
        if (entry.message?.content) {
          const content = typeof entry.message.content === 'string'
            ? entry.message.content
            : entry.message.content.map(c => c.text || '').join(' ');

          const agentMatch = content.match(/\.claude\/agents\/([\w-]+)\.md/);
          if (agentMatch) {
            agentName = agentMatch[1];
          }
        }
      } catch {
        // Skip malformed lines
      }
    }
  } catch {
    // Ignore transcript parsing errors
  }

  // Generate agentId from transcript path (contains session info)
  const transcriptName = path.basename(transcriptPath, '.jsonl');
  agentId = `${agentName}-${transcriptName.slice(-8)}`;

  return { agentName, task, agentId };
}

function writeAgentLog(
  projectDir: string,
  agentInfo: { agentName: string | null; task: string; agentId: string | null },
  outputPath: string
): void {
  if (!agentInfo.agentName || !agentInfo.agentId) return;

  const logDir = path.join(projectDir, '.claude', 'cache', 'agents');
  const logFile = path.join(logDir, 'agent-log.jsonl');

  // Ensure directory exists
  if (!fs.existsSync(logDir)) {
    fs.mkdirSync(logDir, { recursive: true });
  }

  const logEntry = {
    agentId: agentInfo.agentId,
    type: agentInfo.agentName,
    task: agentInfo.task.slice(0, 500),
    timestamp: new Date().toISOString(),
    output: outputPath.replace(projectDir, ''),
    status: 'completed',
    canResume: true
  };

  fs.appendFileSync(logFile, JSON.stringify(logEntry) + '\n');
}

function appendToLedger(
  projectDir: string,
  agentInfo: { agentName: string | null; task: string; agentId: string | null },
  outputSummary: string
): void {
  if (!agentInfo.agentName) return;

  // Find ledger file
  const ledgerDir = path.join(projectDir, 'thoughts', 'ledgers');
  const ledgerFiles = fs.readdirSync(ledgerDir)
    .filter(f => f.startsWith('CONTINUITY_CLAUDE-') && f.endsWith('.md'));

  if (ledgerFiles.length === 0) return;

  const mostRecent = ledgerFiles.sort((a, b) => {
    const statA = fs.statSync(path.join(ledgerDir, a));
    const statB = fs.statSync(path.join(ledgerDir, b));
    return statB.mtime.getTime() - statA.mtime.getTime();
  })[0];

  const ledgerPath = path.join(ledgerDir, mostRecent);
  let content = fs.readFileSync(ledgerPath, 'utf-8');

  const timestamp = new Date().toISOString();
  const agentReport = `
### ${agentInfo.agentName} (${timestamp})
- Task: ${agentInfo.task.slice(0, 100)}${agentInfo.task.length > 100 ? '...' : ''}
- Summary: ${outputSummary.slice(0, 200)}${outputSummary.length > 200 ? '...' : ''}
- Output: \`.claude/cache/agents/${agentInfo.agentName}/latest-output.md\`
`;

  // Find or create Agent Reports section
  const agentReportsMatch = content.match(/## Agent Reports\n/);
  if (agentReportsMatch) {
    // Append to existing section
    const insertPos = content.indexOf('## Agent Reports\n') + '## Agent Reports\n'.length;
    content = content.slice(0, insertPos) + agentReport + content.slice(insertPos);
  } else {
    // Create new section before Architecture Summary or at end
    const archMatch = content.indexOf('## Architecture Summary');
    const hooksMatch = content.indexOf('## Hooks Summary');
    const insertBefore = archMatch > 0 ? archMatch : (hooksMatch > 0 ? hooksMatch : content.length);

    content = content.slice(0, insertBefore) + '\n## Agent Reports\n' + agentReport + '\n' + content.slice(insertBefore);
  }

  fs.writeFileSync(ledgerPath, content);
}

async function readStdin(): Promise<string> {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.on('data', chunk => data += chunk);
    process.stdin.on('end', () => resolve(data));
  });
}

main().catch(console.error);
