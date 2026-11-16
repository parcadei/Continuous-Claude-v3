/**
 * Compiler-in-the-Loop Stop Hook
 *
 * Prevents Claude from stopping if there are unresolved Lean errors/sorries.
 * Implements the APOLLO recursive repair pattern.
 */

import { readFileSync, existsSync, unlinkSync } from 'fs';
import { join } from 'path';

interface StopHookInput {
  session_id: string;
  hook_event_name: string;
  stop_hook_active: boolean;
  cwd: string;
}

interface CompilerState {
  session_id: string;
  file_path: string;
  has_errors: boolean;
  errors: string;
  sorries: string[];
  timestamp: number;
}

const STATE_DIR = process.env.CLAUDE_PROJECT_DIR
  ? join(process.env.CLAUDE_PROJECT_DIR, '.claude', 'cache', 'lean')
  : '/tmp/claude-lean';

const STATE_FILE = join(STATE_DIR, 'compiler-state.json');

// Max age for state (5 minutes) - ignore stale state
const MAX_STATE_AGE_MS = 5 * 60 * 1000;

function readStdin(): string {
  return readFileSync(0, 'utf-8');
}

function loadState(): CompilerState | null {
  if (!existsSync(STATE_FILE)) return null;

  try {
    const state: CompilerState = JSON.parse(readFileSync(STATE_FILE, 'utf-8'));

    // Check if state is stale
    if (Date.now() - state.timestamp > MAX_STATE_AGE_MS) {
      unlinkSync(STATE_FILE);
      return null;
    }

    return state;
  } catch {
    return null;
  }
}

function clearState(): void {
  if (existsSync(STATE_FILE)) {
    unlinkSync(STATE_FILE);
  }
}

async function main() {
  const input: StopHookInput = JSON.parse(readStdin());

  // CRITICAL: Prevent infinite loops
  if (input.stop_hook_active) {
    console.log('{}');
    return;
  }

  const state = loadState();

  // No Lean state or no errors - allow stop
  if (!state || !state.has_errors) {
    console.log('{}');
    return;
  }

  // Check if state is for current session
  if (state.session_id !== input.session_id) {
    clearState();
    console.log('{}');
    return;
  }

  // Build repair prompt based on error type
  let repairPrompt: string;

  if (state.sorries.length > 0) {
    repairPrompt = `
🔄 APOLLO REPAIR LOOP - Unresolved 'sorry' placeholders

File: ${state.file_path}

The proof has ${state.sorries.length} incomplete part(s):

${state.sorries.join('\n')}

**Your task:**
1. Pick ONE sorry to fix (start with the simplest)
2. Replace 'sorry' with a valid proof:
   - Try tactics: simp, ring, nlinarith, norm_num, exact, apply
   - Or provide explicit proof term
3. Re-run to check if it compiles

Continue fixing until all sorries are resolved.
`;
  } else {
    repairPrompt = `
🔄 APOLLO REPAIR LOOP - Lean Compiler Errors

File: ${state.file_path}

Errors:
${state.errors.slice(0, 2000)}

**Your task:**
1. Read the error messages carefully
2. If type error: check signatures match
3. If syntax error: check Lean 4 syntax
4. If unknown identifier: check imports
5. Consider using 'sorry' to isolate the failing part, then fix incrementally

Fix the errors and re-write the file.
`;
  }

  // Block stop, inject repair prompt
  console.log(JSON.stringify({
    decision: 'block',
    reason: repairPrompt
  }));
}

main().catch(err => {
  console.error(err.message);
  process.exit(1);
});
