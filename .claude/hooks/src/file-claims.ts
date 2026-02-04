/**
 * PreToolUse:Edit|Write Hook - Enforce file locking for conflict prevention.
 *
 * This hook:
 * 1. Checks if another ACTIVE session has claimed the file
 * 2. BLOCKS edits if there's an active conflict (session heartbeat < 5 min old)
 * 3. Allows and claims if no conflict or other session is stale
 *
 * Part of the coordination layer architecture (Phase 3).
 */

import { readFileSync } from 'fs';
import { checkFileClaim, claimFile, isSessionActive } from './shared/db-utils-pg.js';
import { getSessionId, getProject } from './shared/session-id.js';
import type { PreToolUseInput, HookOutput } from './shared/types.js';

// Stale session threshold (5 minutes)
const STALE_THRESHOLD_MS = 5 * 60 * 1000;

/**
 * Main entry point for the PreToolUse:Edit|Write hook.
 * Enforces file locking - blocks edits when another active session has the file.
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

  // Only process Edit and Write tools
  if (input.tool_name !== 'Edit' && input.tool_name !== 'Write') {
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

  let output: any;

  if (claimCheck.claimed && claimCheck.claimedBy) {
    // Check if the claiming session is still active
    const otherSessionActive = isSessionActive(claimCheck.claimedBy, STALE_THRESHOLD_MS);

    if (otherSessionActive) {
      // Active session has the file - BLOCK the edit with proper PreToolUse format
      const fileName = filePath.split(/[/\\]/).pop() || filePath;
      const blockMessage = `⚠️ FILE CONFLICT BLOCKED

"${fileName}" is locked by Session ${claimCheck.claimedBy}

This file is being edited by another active Claude session.
Wait for the other session to finish or coordinate directly.

The lock auto-releases when that session's heartbeat goes stale (5 min).`;

      output = {
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          permissionDecision: 'deny',
          permissionDecisionReason: blockMessage
        }
      };
    } else {
      // Other session is stale - take over the claim
      claimFile(filePath, project, sessionId);
      const fileName = filePath.split(/[/\\]/).pop() || filePath;
      output = {
        result: 'continue',
        message: `[INFO] Took over stale file lock for "${fileName}" from inactive session`,
      };
    }
  } else {
    // No conflict - claim the file for this session
    claimFile(filePath, project, sessionId);
    output = { result: 'continue' };
  }

  console.log(JSON.stringify(output));
}

// Run if executed directly
main();
