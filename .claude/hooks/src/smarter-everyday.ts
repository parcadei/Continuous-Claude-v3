#!/usr/bin/env node
/**
 * Smarter Everyday Hook
 *
 * L2 Defense Layer: Detects when a session finds the FINAL solution to a
 * complex problem after multiple attempts. Builds a "victory" library that
 * makes the system smarter over time.
 *
 * Hook: PostToolUse
 * Matcher: Edit|Write|Bash|TaskUpdate
 *
 * State Machine:
 *   IDLE          - No active problem-solving tracked
 *   ATTEMPTING    - Editing file X (problem started)
 *   TESTING       - Ran test after edit
 *   CANDIDATE     - Test passed, watching for finality
 *   VICTORY       - Confirmed final solution
 *
 * A solution is FINAL when:
 *   1. It passes AND we move on (3+ turns without editing same file)
 *   2. User confirms it ("It's working now")
 *   3. Task is marked complete
 *
 * State file: .claude/smarter-everyday-state.json
 */

import * as fs from 'fs';
import * as path from 'path';

interface PostToolUseInput {
  session_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_response: unknown;
}

interface HookOutput {
  continue: boolean;
  systemMessage?: string;
}

type State = 'IDLE' | 'ATTEMPTING' | 'TESTING' | 'CANDIDATE' | 'VICTORY';

interface FailureRecord {
  turn: number;
  error: string;
}

interface SmarterState {
  session_id: string;
  state: State;
  tracked_file: string | null;
  attempts: number;
  failures: FailureRecord[];
  candidate_turn: number | null;
  last_edit_content: string | null;
  test_command: string | null;
  context: string | null;
  current_turn: number;
}

// Test command patterns
const TEST_COMMANDS = [
  /\b(npm|yarn|pnpm)\s+(run\s+)?test/i,
  /\bpytest\b/i,
  /\bcargo\s+test\b/i,
  /\bgo\s+test\b/i,
  /\bjest\b/i,
  /\bvitest\b/i,
  /\bmocha\b/i,
  /\bmake\s+test\b/i,
  /\bnpm\s+run\s+check/i,
  /\btsc\s+--noEmit/i,
];

// Success indicators in test output
const SUCCESS_PATTERNS = [
  /\bpassed\b/i,
  /\bpassing\b/i,
  /\b0\s+(failures?|errors?)\b/i,
  /[\u2713\u2714\u221A]/,  // Check marks
  /All tests passed/i,
  /PASS\s/,
  /Tests:\s+\d+\s+passed/i,
  /OK\s*\(/i,
];

// Failure indicators in test output
const FAILURE_PATTERNS = [
  /\bfailed\b/i,
  /\bfailing\b/i,
  /\berror\b/i,
  /\bexception\b/i,
  /\b[1-9]\d*\s+(failures?|errors?)\b/i,
  /[\u2717\u2718\u00D7]/,  // X marks
  /FAILED/,
  /Tests:\s+\d+\s+failed/i,
];

// Turns to wait before declaring victory (no edit to tracked file)
const VICTORY_TURN_THRESHOLD = 3;

function getStateFilePath(projectDir: string): string {
  return path.join(projectDir, '.claude', 'smarter-everyday-state.json');
}

function loadState(stateFile: string, sessionId: string): SmarterState {
  const defaultState: SmarterState = {
    session_id: sessionId,
    state: 'IDLE',
    tracked_file: null,
    attempts: 0,
    failures: [],
    candidate_turn: null,
    last_edit_content: null,
    test_command: null,
    context: null,
    current_turn: 0,
  };

  if (!fs.existsSync(stateFile)) {
    return defaultState;
  }

  try {
    const data = JSON.parse(fs.readFileSync(stateFile, 'utf-8'));
    // Reset if different session
    if (data.session_id !== sessionId) {
      return defaultState;
    }
    return { ...defaultState, ...data };
  } catch {
    return defaultState;
  }
}

function saveState(stateFile: string, state: SmarterState): void {
  const dir = path.dirname(stateFile);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(stateFile, JSON.stringify(state, null, 2));
}

function isTestCommand(command: string): boolean {
  return TEST_COMMANDS.some(pattern => pattern.test(command));
}

function isTestSuccess(output: string): boolean {
  const hasSuccess = SUCCESS_PATTERNS.some(p => p.test(output));
  const hasFailure = FAILURE_PATTERNS.some(p => p.test(output));
  return hasSuccess && !hasFailure;
}

function isTestFailure(output: string): boolean {
  return FAILURE_PATTERNS.some(p => p.test(output));
}

function extractErrorMessage(output: string): string {
  // Try to extract the most relevant error line
  const lines = output.split('\n');

  // Look for common error patterns
  for (const line of lines) {
    if (/error:|exception:|failed:/i.test(line)) {
      return line.trim().slice(0, 200);
    }
  }

  // Fall back to first non-empty line that looks like an error
  for (const line of lines) {
    if (line.trim() && /\b(error|fail|exception)\b/i.test(line)) {
      return line.trim().slice(0, 200);
    }
  }

  return 'Unknown error';
}

function getOpcDir(): string {
  return process.env.CLAUDE_OPC_DIR ||
    path.join(process.env.HOME || process.env.USERPROFILE || '', 'continuous-claude', 'opc');
}

async function storeVictoryLearning(state: SmarterState, projectDir: string): Promise<boolean> {
  const opcDir = getOpcDir();

  // Build rich learning content
  const failedApproaches = state.failures
    .map(f => f.error)
    .filter((v, i, a) => a.indexOf(v) === i)  // unique
    .slice(0, 3)
    .join('; ');

  const content = `Problem solved after ${state.attempts} attempts.
File: ${state.tracked_file}
Solution: ${state.last_edit_content || 'Final edit'}
${failedApproaches ? `Failed approaches: ${failedApproaches}` : ''}
Test: ${state.test_command || 'Unknown test command'}`;

  const script = 'scripts/core/store_learning.py';
  const escapedContent = content.slice(0, 2000).replace(/"/g, '\\"');
  const contextStr = `Victory: ${state.context || state.tracked_file}`;
  const tagsStr = `victory,verified,attempts:${state.attempts}`;
  const cmd = `uv run python ${script} --session-id "${state.session_id}" --type WORKING_SOLUTION --content "${escapedContent}" --context "${contextStr}" --tags "${tagsStr}" --confidence high --project-dir "${projectDir}"`;

  try {
    const { execSync } = require('child_process');
    execSync(cmd, {
      encoding: 'utf-8',
      cwd: opcDir,
      timeout: 60000,
      stdio: ['pipe', 'pipe', 'pipe'],
      shell: true
    });
    return true;
  } catch {
    return false;
  }
}

function processTransition(
  state: SmarterState,
  toolName: string,
  toolInput: Record<string, unknown>,
  toolResponse: unknown,
  projectDir: string
): { newState: SmarterState; message: string | null } {

  const newState = { ...state, current_turn: state.current_turn + 1 };
  let message: string | null = null;

  // Handle Edit/Write - file modifications
  if (toolName === 'Edit' || toolName === 'Write') {
    const filePath = (toolInput.file_path as string) || '';
    const normalizedPath = path.basename(filePath);

    if (newState.state === 'IDLE') {
      // Start tracking
      newState.state = 'ATTEMPTING';
      newState.tracked_file = filePath;
      newState.attempts = 1;
      newState.failures = [];
      newState.context = `Editing ${normalizedPath}`;
    } else if (newState.state === 'CANDIDATE' && filePath === newState.tracked_file) {
      // Editing same file again - not final!
      newState.state = 'ATTEMPTING';
      newState.attempts += 1;
      newState.candidate_turn = null;
    } else if (newState.state === 'ATTEMPTING' && filePath === newState.tracked_file) {
      // Continue tracking same file
      newState.attempts += 1;
    } else if (filePath !== newState.tracked_file) {
      // Different file - might be switching problems
      // Check if CANDIDATE should become VICTORY
      if (newState.state === 'CANDIDATE' && newState.candidate_turn) {
        const turnsSince = newState.current_turn - newState.candidate_turn;
        if (turnsSince >= VICTORY_TURN_THRESHOLD) {
          // VICTORY! Store and reset
          storeVictoryLearning(newState, projectDir);
          message = `[SmarterEveryDay] Victory captured: ${normalizedPath} fixed after ${newState.attempts} attempts`;
          newState.state = 'IDLE';
          newState.tracked_file = null;
          newState.attempts = 0;
          newState.failures = [];
          newState.candidate_turn = null;
        }
      }
    }

    // Capture edit content for learning
    if (toolInput.new_string) {
      newState.last_edit_content = String(toolInput.new_string).slice(0, 500);
    } else if (toolInput.content) {
      newState.last_edit_content = String(toolInput.content).slice(0, 500);
    }
  }

  // Handle Bash - test execution
  if (toolName === 'Bash') {
    const command = (toolInput.command as string) || '';

    if (isTestCommand(command)) {
      newState.test_command = command;
      const output = String((toolResponse as { output?: string })?.output || '');

      if (newState.state === 'ATTEMPTING') {
        newState.state = 'TESTING';

        if (isTestSuccess(output)) {
          // Test passed - become candidate
          newState.state = 'CANDIDATE';
          newState.candidate_turn = newState.current_turn;
        } else if (isTestFailure(output)) {
          // Test failed - record and stay in ATTEMPTING
          newState.state = 'ATTEMPTING';
          newState.failures.push({
            turn: newState.current_turn,
            error: extractErrorMessage(output)
          });
          // Keep only last 5 failures
          if (newState.failures.length > 5) {
            newState.failures = newState.failures.slice(-5);
          }
        }
      } else if (newState.state === 'CANDIDATE') {
        // Another test run while candidate
        if (isTestSuccess(output)) {
          // Still passing - stay candidate
        } else if (isTestFailure(output)) {
          // Failed again - back to attempting
          newState.state = 'ATTEMPTING';
          newState.candidate_turn = null;
          newState.failures.push({
            turn: newState.current_turn,
            error: extractErrorMessage(output)
          });
        }
      }
    }
  }

  // Handle TaskUpdate - task completion
  if (toolName === 'TaskUpdate') {
    const status = (toolInput.status as string) || '';

    if (status === 'completed' && newState.state === 'CANDIDATE') {
      // Task marked complete while candidate - VICTORY!
      storeVictoryLearning(newState, projectDir);
      message = `[SmarterEveryDay] Victory confirmed (task complete): ${newState.tracked_file} fixed after ${newState.attempts} attempts`;
      newState.state = 'IDLE';
      newState.tracked_file = null;
      newState.attempts = 0;
      newState.failures = [];
      newState.candidate_turn = null;
    }
  }

  // Time-based victory check
  if (newState.state === 'CANDIDATE' && newState.candidate_turn) {
    const turnsSince = newState.current_turn - newState.candidate_turn;
    if (turnsSince >= VICTORY_TURN_THRESHOLD && newState.attempts >= 2) {
      // Only count as victory if we had multiple attempts
      storeVictoryLearning(newState, projectDir);
      message = `[SmarterEveryDay] Victory (${turnsSince} turns stable): ${newState.tracked_file} fixed after ${newState.attempts} attempts`;
      newState.state = 'IDLE';
      newState.tracked_file = null;
      newState.attempts = 0;
      newState.failures = [];
      newState.candidate_turn = null;
    }
  }

  return { newState, message };
}

async function main() {
  const input = await readStdin();
  if (!input.trim()) {
    console.log(JSON.stringify({ continue: true }));
    return;
  }

  let data: PostToolUseInput;
  try {
    data = JSON.parse(input);
  } catch {
    console.log(JSON.stringify({ continue: true }));
    return;
  }

  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const stateFile = getStateFilePath(projectDir);
  const state = loadState(stateFile, data.session_id);

  const { newState, message } = processTransition(
    state,
    data.tool_name,
    data.tool_input,
    data.tool_response,
    projectDir
  );

  saveState(stateFile, newState);

  const output: HookOutput = {
    continue: true,
    systemMessage: message || undefined
  };

  console.log(JSON.stringify(output));
}

async function readStdin(): Promise<string> {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.setEncoding('utf-8');
    process.stdin.on('data', chunk => data += chunk);
    process.stdin.on('end', () => resolve(data));
  });
}

main().catch(err => {
  console.error('smarter-everyday error:', err);
  console.log(JSON.stringify({ continue: true }));
});
