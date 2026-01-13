/**
 * SessionStart Hook - Registers session in coordination layer.
 *
 * This hook:
 * 1. Registers the session in PostgreSQL for cross-session awareness
 * 2. Injects a system reminder about coordination layer features
 * 3. Shows other active sessions working on the same project
 *
 * Part of the coordination layer architecture (Phase 1).
 */

import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';
import { registerSession, getActiveSessions } from './shared/db-utils-pg.js';
import type { SessionStartInput, HookOutput } from './shared/types.js';

/**
 * Returns the path to the session ID persistence file.
 * Creates the ~/.claude directory if it doesn't exist.
 *
 * @returns Path to ~/.claude/.coordination-session-id
 */
function getSessionIdFile(): string {
  const claudeDir = join(process.env.HOME || '/tmp', '.claude');
  try {
    mkdirSync(claudeDir, { recursive: true });
  } catch { /* ignore */ }
  return join(claudeDir, '.coordination-session-id');
}

/**
 * Generates or retrieves a short session ID for coordination.
 * Priority: BRAINTRUST_SPAN_ID (first 8 chars) > timestamp-based ID.
 *
 * @returns 8-character session identifier (e.g., "s-m1abc23")
 */
function getSessionId(): string {
  const spanId = process.env.BRAINTRUST_SPAN_ID;
  if (spanId) {
    return spanId.slice(0, 8);
  }
  return `s-${Date.now().toString(36)}`;
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
 * Main entry point for the SessionStart hook.
 * Registers the session, persists the ID to file, and injects awareness message.
 */
export function main(): void {
  // Read hook input from stdin
  let input: SessionStartInput;
  try {
    const stdinContent = readFileSync(0, 'utf-8');
    input = JSON.parse(stdinContent) as SessionStartInput;
  } catch {
    // If we can't read input, just continue silently
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  const sessionId = getSessionId();
  const project = getProject();
  const projectName = project.split('/').pop() || 'unknown';

  // Store session ID in environment and file for other hooks
  process.env.COORDINATION_SESSION_ID = sessionId;
  try {
    writeFileSync(getSessionIdFile(), sessionId, 'utf-8');
  } catch { /* ignore write errors */ }

  // Register session in PostgreSQL
  const registerResult = registerSession(sessionId, project, '');

  // Get other active sessions
  const sessionsResult = getActiveSessions(project);
  const otherSessions = sessionsResult.sessions.filter(s => s.id !== sessionId);

  // Build awareness message
  let awarenessMessage = `
<system-reminder>
MULTI-SESSION COORDINATION ACTIVE

Session: ${sessionId}
Project: ${projectName}
`;

  if (otherSessions.length > 0) {
    awarenessMessage += `
Active peer sessions (${otherSessions.length}):
${otherSessions.map(s => `  - ${s.id}: ${s.working_on || 'working...'}`).join('\n')}

Coordination features:
- File edits are tracked to prevent conflicts
- Research findings are shared automatically
- Use Task tool normally - coordination happens via hooks
`;
  } else {
    awarenessMessage += `
No other sessions active on this project.
You are the only session currently working here.
`;
  }

  awarenessMessage += `</system-reminder>`;

  // Output hook result with awareness injection
  const output: HookOutput = {
    result: 'continue',
    message: awarenessMessage,
  };

  console.log(JSON.stringify(output));
}

// Run if executed directly
main();
