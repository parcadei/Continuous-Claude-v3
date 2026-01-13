/**
 * PreToolUse:Edit Hook - Check and claim files for conflict prevention.
 *
 * This hook:
 * 1. Checks if another session has claimed the file
 * 2. Warns if file is being edited by another session
 * 3. Claims the file for the current session
 *
 * Part of the coordination layer architecture (Phase 1).
 */

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { checkFileClaim, claimFile } from './shared/db-utils-pg.js';
import type { PreToolUseInput, HookOutput } from './shared/types.js';

/**
 * Returns the path to the session ID persistence file.
 * Does not create the directory (session-register.ts handles creation).
 *
 * @returns Path to ~/.claude/.coordination-session-id
 */
function getSessionIdFile(): string {
  return join(process.env.HOME || '/tmp', '.claude', '.coordination-session-id');
}

/**
 * Retrieves the session ID for coordination, checking multiple sources.
 * Priority: env var > file > BRAINTRUST_SPAN_ID > generated.
 *
 * @returns Session identifier string (e.g., "s-m1abc23")
 */
function getSessionId(): string {
  // First try environment (same process)
  if (process.env.COORDINATION_SESSION_ID) {
    return process.env.COORDINATION_SESSION_ID;
  }

  // Try reading from file (cross-process persistence)
  const sessionFile = getSessionIdFile();
  if (existsSync(sessionFile)) {
    try {
      const id = readFileSync(sessionFile, 'utf-8').trim();
      if (id) return id;
    } catch { /* ignore read errors */ }
  }

  // Fallback to Braintrust span ID or generate new
  return process.env.BRAINTRUST_SPAN_ID?.slice(0, 8) ||
         `s-${Date.now().toString(36)}`;
}

/**
 * Returns the current project directory path.
 *
 * @returns CLAUDE_PROJECT_DIR env var or current working directory
 */
function getProject(): string {
  return process.env.CLAUDE_PROJECT_DIR || process.cwd();
}

/**
 * Main entry point for the PreToolUse:Edit hook.
 * Checks for file conflicts and claims files for the current session.
 */
export function main(): void {
  // Read hook input from stdin
  let input: PreToolUseInput;
  try {
    const stdinContent = readFileSync(0, 'utf-8');
    input = JSON.parse(stdinContent) as PreToolUseInput;
  } catch {
    // If we can't read input, continue silently
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Only process Edit tool
  if (input.tool_name !== 'Edit') {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Extract file path from input
  const filePath = input.tool_input?.file_path as string;
  if (!filePath) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  const sessionId = getSessionId();
  const project = getProject();

  // Check if file is claimed by another session
  const claimCheck = checkFileClaim(filePath, project, sessionId);

  let output: HookOutput;

  if (claimCheck.claimed) {
    // File is being edited by another session - warn but allow
    const fileName = filePath.split('/').pop() || filePath;
    output = {
      result: 'continue',  // Allow edit, just warn
      message: `\u26A0\uFE0F **File Conflict Warning**
\`${fileName}\` is being edited by Session ${claimCheck.claimedBy}
Consider coordinating with the other session to avoid conflicts.`,
    };
  } else {
    // Claim the file for this session
    claimFile(filePath, project, sessionId);
    output = { result: 'continue' };
  }

  console.log(JSON.stringify(output));
}

// Run if executed directly
main();
