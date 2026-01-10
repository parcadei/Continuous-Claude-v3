/**
 * Stop Hook - Suggest pending learnings and ADRs before session ends.
 *
 * Ported from 8t0 system's pre-stop.sh
 *
 * This hook:
 * 1. Queries memory for OPEN_THREAD entries from current session
 * 2. Shows suggestions for /8t0-learn, /8t0-adr, /8t0-progress
 * 3. Checks for uncommitted git changes
 * 4. Returns systemMessage with suggestions (doesn't block)
 *
 * Uses PostgreSQL memory system instead of file-based queue.
 */

import { existsSync } from 'fs';
import { execSync } from 'child_process';

interface StopInput {
  session_id: string;
  stop_hook_active?: boolean;
}

interface StopHookOutput {
  decision?: 'approve' | 'deny';
  systemMessage?: string;
}

function getSessionId(): string {
  return process.env.COORDINATION_SESSION_ID ||
         process.env.BRAINTRUST_SPAN_ID?.slice(0, 8) ||
         `s-${Date.now().toString(36)}`;
}

function getProjectDir(): string {
  return process.env.CLAUDE_PROJECT_DIR || process.cwd();
}

/**
 * Query memory for OPEN_THREAD entries with specific tags
 */
function queryOpenThreads(tag: string): number {
  const projectDir = getProjectDir();
  const opcDir = `${projectDir}/opc`;

  if (!existsSync(opcDir)) {
    return 0;
  }

  try {
    const result = execSync(`cd "${opcDir}" && PYTHONPATH=. uv run python scripts/core/recall_learnings.py \
      --query "${tag}" --k 20 --text-only 2>/dev/null | grep -c "OPEN_THREAD" || echo "0"`, {
      encoding: 'utf-8',
      timeout: 5000
    });
    return parseInt(result.trim(), 10) || 0;
  } catch {
    return 0;
  }
}

/**
 * Check for uncommitted git changes
 */
function getUncommittedCount(): number {
  const projectDir = getProjectDir();

  if (!existsSync(`${projectDir}/.git`)) {
    return 0;
  }

  try {
    const result = execSync(`git -C "${projectDir}" status --porcelain 2>/dev/null | wc -l`, {
      encoding: 'utf-8',
      timeout: 3000
    });
    return parseInt(result.trim(), 10) || 0;
  } catch {
    return 0;
  }
}

/**
 * Check if progress dashboard needs update
 */
function progressNeedsUpdate(): boolean {
  const projectDir = getProjectDir();

  // Check if .planning directory exists
  if (!existsSync(`${projectDir}/.planning`)) {
    return false;
  }

  // Check if PROGRESS.md exists - if not, might need creation
  if (!existsSync(`${projectDir}/.planning/PROGRESS.md`)) {
    return existsSync(`${projectDir}/.planning/ROADMAP.md`);
  }

  return false;
}

async function readStdin(): Promise<string> {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.on('data', (chunk) => (data += chunk));
    process.stdin.on('end', () => resolve(data));
  });
}

async function main() {
  const input: StopInput = JSON.parse(await readStdin());

  // Prevent infinite loop
  if (input.stop_hook_active) {
    console.log(JSON.stringify({ decision: 'approve' }));
    return;
  }

  const suggestions: string[] = [];

  // Check for learning opportunities (code markers detected)
  const learningCount = queryOpenThreads('8t0-learn code-marker');
  if (learningCount > 0) {
    suggestions.push(`- ${learningCount} code patterns detected → /8t0-learn to capture`);
  }

  // Check for ADR opportunities
  const adrCount = queryOpenThreads('8t0-adr adr-opportunity');
  if (adrCount > 0) {
    suggestions.push(`- ${adrCount} architectural discussions → /8t0-adr to document`);
  }

  // Check if progress needs update
  if (progressNeedsUpdate()) {
    suggestions.push('- Progress dashboard may need update → /8t0-progress');
  }

  // Check for uncommitted changes
  const uncommitted = getUncommittedCount();
  if (uncommitted > 0) {
    suggestions.push(`- ${uncommitted} uncommitted changes → consider /commit`);
  }

  // Output suggestions or approve stop
  let output: StopHookOutput;

  if (suggestions.length > 0) {
    output = {
      systemMessage: `
─────────────────────────────────────────────────
Before stopping, consider:

${suggestions.join('\n')}

Or proceed to stop the session.
─────────────────────────────────────────────────`
    };
  } else {
    output = { decision: 'approve' };
  }

  console.log(JSON.stringify(output));
}

main().catch(() => {
  // On error, just approve to not block session end
  console.log(JSON.stringify({ decision: 'approve' }));
});
