import * as fs from 'fs';
import * as path from 'path';

interface SessionEndInput {
  session_id: string;
  transcript_path: string;
  reason: 'clear' | 'logout' | 'prompt_input_exit' | 'other';
}

interface HookOutput {
  result: "continue";
  message?: string;
}

async function readStdin(): Promise<string> {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.on("data", (chunk) => (data += chunk));
    process.stdin.on("end", () => resolve(data));
  });
}

async function main() {
  const input: SessionEndInput = JSON.parse(await readStdin());
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();

  // Only prompt on user-initiated session end, not auto-compaction
  if (input.reason === 'other') {
    console.log(JSON.stringify({ result: "continue" }));
    return;
  }

  // Check if Artifact Index database exists
  const dbPath = path.join(projectDir, '.claude', 'cache', 'artifact-index', 'context.db');
  const dbExists = fs.existsSync(dbPath);

  if (!dbExists) {
    console.log(JSON.stringify({ result: "continue" }));
    return;
  }

  // Find most recent handoff to mark
  const ledgerDir = path.join(projectDir, 'thoughts', 'ledgers');
  let ledgerFiles: string[];
  try {
    ledgerFiles = fs.readdirSync(ledgerDir)
      .filter(f => f.startsWith('CONTINUITY_CLAUDE-') && f.endsWith('.md'))
      .sort((a, b) => {
        const statA = fs.statSync(path.join(ledgerDir, a));
        const statB = fs.statSync(path.join(ledgerDir, b));
        return statB.mtime.getTime() - statA.mtime.getTime();
      });
  } catch {
    console.log(JSON.stringify({ result: "continue" }));
    return;
  }

  if (ledgerFiles.length === 0) {
    console.log(JSON.stringify({ result: "continue" }));
    return;
  }

  const sessionName = ledgerFiles[0]
    .replace('CONTINUITY_CLAUDE-', '')
    .replace('.md', '');

  // Check for handoffs in this session (thoughts/shared/handoffs is tracked in git)
  const handoffDir = path.join(projectDir, 'thoughts', 'shared', 'handoffs', sessionName);
  if (!fs.existsSync(handoffDir)) {
    console.log(JSON.stringify({ result: "continue" }));
    return;
  }

  // Handoff files use date-based naming: YYYY-MM-DD_HH-MM-SS_description.md
  const handoffFiles = fs.readdirSync(handoffDir)
    .filter(f => f.endsWith('.md') && /^\d{4}-\d{2}-\d{2}_/.test(f))
    .sort((a, b) => {
      // Sort by filename (date-based) descending
      return b.localeCompare(a);
    });

  if (handoffFiles.length === 0) {
    console.log(JSON.stringify({ result: "continue" }));
    return;
  }

  const latestHandoff = handoffFiles[0];
  const handoffName = latestHandoff.replace('.md', '');

  const output: HookOutput = {
    result: "continue",
    message: `

─────────────────────────────────────────────────
Session ended: ${sessionName}
Latest handoff: ${handoffName}

To mark outcome and improve future sessions:

  uv run python scripts/artifact_mark.py \\
    --handoff <handoff-id> \\
    --outcome SUCCEEDED|PARTIAL_PLUS|PARTIAL_MINUS|FAILED

To find handoff ID, query the database:

  sqlite3 .claude/cache/artifact-index/context.db \\
    "SELECT id, file_path FROM handoffs WHERE session_name='${sessionName}' ORDER BY indexed_at DESC LIMIT 1"

Outcome meanings:
  SUCCEEDED      - Task completed successfully
  PARTIAL_PLUS   - Mostly done, minor issues remain
  PARTIAL_MINUS  - Some progress, major issues remain
  FAILED         - Task abandoned or blocked
─────────────────────────────────────────────────
`
  };

  console.log(JSON.stringify(output));
}

main().catch(console.error);
