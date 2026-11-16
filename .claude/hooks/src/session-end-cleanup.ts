import * as fs from 'fs';
import * as path from 'path';
import { spawn } from 'child_process';

interface SessionEndInput {
  session_id: string;
  transcript_path: string;
  reason: 'clear' | 'logout' | 'prompt_input_exit' | 'other';
}

async function main() {
  const input: SessionEndInput = JSON.parse(await readStdin());
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();

  try {
    // Update continuity ledger with session end
    const ledgerDir = path.join(projectDir, 'thoughts', 'ledgers');
    const ledgerFiles = fs.readdirSync(ledgerDir)
      .filter(f => f.startsWith('CONTINUITY_CLAUDE-') && f.endsWith('.md'));

    if (ledgerFiles.length > 0) {
      const mostRecent = ledgerFiles.sort((a, b) => {
        const statA = fs.statSync(path.join(ledgerDir, a));
        const statB = fs.statSync(path.join(ledgerDir, b));
        return statB.mtime.getTime() - statA.mtime.getTime();
      })[0];

      const ledgerPath = path.join(ledgerDir, mostRecent);
      let content = fs.readFileSync(ledgerPath, 'utf-8');

      // Update timestamp
      const timestamp = new Date().toISOString();
      content = content.replace(
        /Updated: .*/,
        `Updated: ${timestamp}`
      );

      // Session end notes removed - caused ledger bloat
      // Timestamp update above is sufficient for tracking

      fs.writeFileSync(ledgerPath, content);
    }

    // Clean up old agent cache files (older than 7 days)
    const agentCacheDir = path.join(projectDir, '.claude', 'cache', 'agents');
    if (fs.existsSync(agentCacheDir)) {
      const now = Date.now();
      const maxAge = 7 * 24 * 60 * 60 * 1000; // 7 days

      const agents = fs.readdirSync(agentCacheDir);
      for (const agent of agents) {
        const agentDir = path.join(agentCacheDir, agent);
        const stat = fs.statSync(agentDir);
        if (stat.isDirectory()) {
          const outputFile = path.join(agentDir, 'latest-output.md');
          if (fs.existsSync(outputFile)) {
            const fileStat = fs.statSync(outputFile);
            if (now - fileStat.mtime.getTime() > maxAge) {
              fs.unlinkSync(outputFile);
            }
          }
        }
      }
    }

    // Trigger Braintrust learnings extraction (fire and forget, don't block session end)
    // Uses LLM-as-judge to extract What Worked/Failed/Decisions/Patterns
    const learnScript = path.join(projectDir, 'scripts', 'braintrust_analyze.py');
    const globalScript = path.join(process.env.HOME || '', '.claude', 'scripts', 'braintrust_analyze.py');
    const scriptPath = fs.existsSync(learnScript) ? learnScript : globalScript;

    if (fs.existsSync(scriptPath)) {
      // Use spawn with detached mode so process survives hook exit
      // Pass the ending session's ID explicitly (new session may already be active in Braintrust)

      // For global script, use --with to include deps (works in any project without pyproject.toml)
      // For project script, use regular uv run (project has its own deps)
      const isGlobalScript = scriptPath === globalScript;
      const args = isGlobalScript
        ? ['run', '--with', 'braintrust', '--with', 'openai', '--with', 'aiohttp', 'python', scriptPath, '--learn', '--session-id', input.session_id]
        : ['run', 'python', scriptPath, '--learn', '--session-id', input.session_id];

      const child = spawn('uv', args, {
        cwd: projectDir,
        detached: true,
        stdio: 'ignore'
      });
      child.unref(); // Let parent exit without waiting for child
    }

    console.log(JSON.stringify({ result: 'continue' }));
  } catch (err) {
    // Don't block session end on errors
    console.log(JSON.stringify({ result: 'continue' }));
  }
}

async function readStdin(): Promise<string> {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.on('data', chunk => data += chunk);
    process.stdin.on('end', () => resolve(data));
  });
}

main().catch(console.error);
