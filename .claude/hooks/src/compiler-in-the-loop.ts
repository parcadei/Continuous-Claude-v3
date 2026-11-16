/**
 * Compiler-in-the-Loop Hook
 *
 * PostToolUse handler for .lean files:
 * - Runs Lean compiler on written files
 * - Calls Goedel-Prover-V2-8B via LMStudio for tactic suggestions
 * - Stores errors in state file for Stop hook
 * - Provides compiler feedback + AI suggestions to Claude
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { execSync } from 'child_process';
import { dirname, join } from 'path';

// LMStudio endpoint for Goedel-Prover-V2-8B
const LMSTUDIO_BASE_URL = process.env.LMSTUDIO_BASE_URL || 'http://127.0.0.1:1234';
const LMSTUDIO_ENDPOINT = process.env.LMSTUDIO_ENDPOINT || `${LMSTUDIO_BASE_URL}/v1/completions`;
const GOEDEL_ENABLED = process.env.GOEDEL_ENABLED !== 'false'; // Enable by default

// Cache LMStudio availability check for the session
let lmStudioAvailable: boolean | null = null;
let lmStudioCheckedAt: number = 0;
const AVAILABILITY_CACHE_MS = 60000; // Re-check every 60s

interface PostToolUseInput {
  session_id: string;
  hook_event_name: string;
  tool_name: string;
  tool_input: {
    file_path?: string;
    content?: string;
  };
  tool_response: {
    success?: boolean;
    filePath?: string;
  };
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

function readStdin(): string {
  return readFileSync(0, 'utf-8');
}

function ensureStateDir(): void {
  if (!existsSync(STATE_DIR)) {
    mkdirSync(STATE_DIR, { recursive: true });
  }
}

function saveState(state: CompilerState): void {
  ensureStateDir();
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

function runLeanCompiler(filePath: string, cwd: string): { success: boolean; output: string; sorries: string[] } {
  // Add elan to PATH
  const home = process.env.HOME || '';
  const elanBin = join(home, '.elan', 'bin');
  const pathWithElan = `${elanBin}:${process.env.PATH}`;

  try {
    // Try lake build first (for project files), or lean directly for standalone files
    const hasLakefile = existsSync(join(cwd, 'lakefile.lean')) || existsSync(join(cwd, 'lakefile.toml'));
    const cmd = hasLakefile
      ? `cd "${cwd}" && lake build 2>&1`
      : `lean "${filePath}" 2>&1`;

    const output = execSync(cmd, {
      encoding: 'utf-8',
      timeout: 60000,
      maxBuffer: 1024 * 1024,
      env: { ...process.env, PATH: pathWithElan }
    });

    // Check for 'sorry' in the output or file
    const sorries: string[] = [];
    const fileContent = existsSync(filePath) ? readFileSync(filePath, 'utf-8') : '';
    const sorryMatches = fileContent.match(/sorry/g);
    if (sorryMatches) {
      // Extract lines with sorry
      const lines = fileContent.split('\n');
      lines.forEach((line, i) => {
        if (line.includes('sorry')) {
          sorries.push(`Line ${i + 1}: ${line.trim()}`);
        }
      });
    }

    return { success: true, output, sorries };
  } catch (error: any) {
    const output = error.stdout || error.stderr || error.message;
    return { success: false, output, sorries: [] };
  }
}

function extractSorries(filePath: string): string[] {
  if (!existsSync(filePath)) return [];

  const content = readFileSync(filePath, 'utf-8');
  const sorries: string[] = [];
  const lines = content.split('\n');

  lines.forEach((line, i) => {
    if (line.includes('sorry')) {
      sorries.push(`Line ${i + 1}: ${line.trim()}`);
    }
  });

  return sorries;
}

/**
 * Check if LMStudio is available with a quick health check.
 * Caches result for AVAILABILITY_CACHE_MS to avoid repeated checks.
 */
async function checkLMStudioAvailable(): Promise<boolean> {
  // Return cached result if still valid
  const now = Date.now();
  if (lmStudioAvailable !== null && (now - lmStudioCheckedAt) < AVAILABILITY_CACHE_MS) {
    return lmStudioAvailable;
  }

  try {
    const response = await fetch(`${LMSTUDIO_BASE_URL}/v1/models`, {
      method: 'GET',
      signal: AbortSignal.timeout(2000) // 2s timeout - fail fast
    });

    lmStudioAvailable = response.ok;
    lmStudioCheckedAt = now;
    return lmStudioAvailable;
  } catch (err) {
    // Connection refused, timeout, or other network error
    lmStudioAvailable = false;
    lmStudioCheckedAt = now;
    return false;
  }
}

/**
 * Get user-friendly message when LMStudio is not available.
 */
function getLMStudioUnavailableMessage(): string {
  return `
ℹ️ Godel-Prover not available (LMStudio not running at ${LMSTUDIO_BASE_URL})
Lean compiler feedback only. To enable AI tactic suggestions:
1. Start LMStudio
2. Load goedel-prover-v2-8b model
`;
}

/**
 * Call Goedel-Prover-V2-8B via LMStudio for tactic suggestions.
 * Returns suggested tactics or null if unavailable.
 */
interface GoedelResult {
  suggestion: string | null;
  unavailableMessage: string | null;
}

async function getGoedelSuggestions(
  leanCode: string,
  errors: string,
  sorries: string[]
): Promise<GoedelResult> {
  if (!GOEDEL_ENABLED) {
    return { suggestion: null, unavailableMessage: null };
  }

  // Check LMStudio availability first (fast, cached)
  const isAvailable = await checkLMStudioAvailable();
  if (!isAvailable) {
    return { suggestion: null, unavailableMessage: getLMStudioUnavailableMessage() };
  }

  try {
    // Build prompt for Goedel prover
    const prompt = buildGoedelPrompt(leanCode, errors, sorries);

    const response = await fetch(LMSTUDIO_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        max_tokens: 4096,
        temperature: 0.6,
        stop: ['```', '\n\n\n']
      }),
      signal: AbortSignal.timeout(30000) // 30s timeout for actual inference
    });

    if (!response.ok) {
      return { suggestion: null, unavailableMessage: null };
    }

    const data = await response.json() as { choices?: Array<{ text?: string }> };
    const suggestion = data.choices?.[0]?.text?.trim();

    if (!suggestion) {
      return { suggestion: null, unavailableMessage: null };
    }

    return { suggestion, unavailableMessage: null };
  } catch (err) {
    // LMStudio error during inference - don't show unavailable message since health check passed
    return { suggestion: null, unavailableMessage: null };
  }
}

/**
 * Build prompt for Goedel-Prover-V2-8B in the format it expects.
 */
function buildGoedelPrompt(leanCode: string, errors: string, sorries: string[]): string {
  if (sorries.length > 0) {
    // Focus on fixing sorries with proof plan first (APOLLO pattern)
    return `Complete the following Lean 4 code:

\`\`\`lean4
${leanCode}
\`\`\`

The proof has ${sorries.length} incomplete part(s):
${sorries.join('\n')}

Before producing the Lean 4 tactics to formally prove the given theorem, provide a detailed proof plan outlining the main proof steps and strategies.
The plan should highlight key ideas, intermediate lemmas, and proof structures that will guide the construction of the final formal proof.

## Proof Plan
1. What is the goal?
2. What key lemmas or intermediate steps are needed?
3. What tactics will achieve each step?

## Tactics
Provide the tactic(s) to replace the first sorry. Use tactics like: simp, ring, nlinarith, norm_num, exact, apply, rfl, ext, aesop_cat.

Response:`;
  } else {
    // Fix compiler errors
    return `Fix the following Lean 4 code that has compiler errors:

\`\`\`lean4
${leanCode}
\`\`\`

Compiler errors:
${errors.slice(0, 1500)}

Provide ONLY the corrected Lean 4 code or the specific fix needed.

Fix:`;
  }
}

async function main() {
  const input: PostToolUseInput = JSON.parse(readStdin());

  // Only process Write tool on .lean files
  if (input.tool_name !== 'Write') {
    console.log('{}');
    return;
  }

  const filePath = input.tool_input?.file_path || input.tool_response?.filePath || '';

  if (!filePath.endsWith('.lean')) {
    console.log('{}');
    return;
  }

  // Run Lean compiler
  const result = runLeanCompiler(filePath, input.cwd);
  const sorries = extractSorries(filePath);

  // Save state for Stop hook
  const state: CompilerState = {
    session_id: input.session_id,
    file_path: filePath,
    has_errors: !result.success || sorries.length > 0,
    errors: result.output,
    sorries: sorries,
    timestamp: Date.now()
  };
  saveState(state);

  // Get Goedel suggestions if there are errors
  let goedelResult: GoedelResult = { suggestion: null, unavailableMessage: null };
  if (!result.success || sorries.length > 0) {
    const leanCode = existsSync(filePath) ? readFileSync(filePath, 'utf-8') : '';
    goedelResult = await getGoedelSuggestions(leanCode, result.output, sorries);
  }

  // Build Goedel suggestion block
  let goedelBlock = '';
  if (goedelResult.suggestion) {
    goedelBlock = `\n🤖 GOEDEL-PROVER SUGGESTION:\n\n${goedelResult.suggestion}\n`;
  } else if (goedelResult.unavailableMessage) {
    goedelBlock = goedelResult.unavailableMessage;
  }

  // Provide feedback to Claude
  if (!result.success) {
    console.log(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PostToolUse',
        additionalContext: `
⚠️ LEAN COMPILER ERRORS:

${result.output}
${goedelBlock}
APOLLO Pattern: Use 'sorry' to mark failing sub-lemmas, then fix each one.
`
      }
    }));
  } else if (sorries.length > 0) {
    console.log(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PostToolUse',
        additionalContext: `
⚠️ LEAN PROOF INCOMPLETE - ${sorries.length} sorry placeholder(s):

${sorries.join('\n')}
${goedelBlock}
Fix each 'sorry' with a valid proof term or tactic.
`
      }
    }));
  } else {
    console.log(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PostToolUse',
        additionalContext: '✓ Lean proof compiles successfully with no sorries!'
      }
    }));
  }
}

main().catch(err => {
  console.error(err.message);
  process.exit(1);
});
