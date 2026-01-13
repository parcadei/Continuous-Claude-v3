/**
 * Session ID utilities for cross-process coordination.
 *
 * Provides consistent session ID generation and persistence across hooks.
 * Session IDs are persisted to ~/.claude/.coordination-session-id to enable
 * cross-process sharing (each hook runs as a separate Node.js process).
 *
 * Used by:
 * - session-register.ts (writes ID on session start)
 * - file-claims.ts (reads ID for file conflict detection)
 */

import { mkdirSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';

/** Default filename for session ID persistence */
const SESSION_ID_FILENAME = '.coordination-session-id';

/**
 * Returns the path to the session ID persistence file.
 * Optionally creates the parent directory if it doesn't exist.
 *
 * @param options.createDir - If true, creates ~/.claude/ directory (default: false)
 * @returns Path to ~/.claude/.coordination-session-id
 */
export function getSessionIdFile(options: { createDir?: boolean } = {}): string {
  const claudeDir = join(process.env.HOME || '/tmp', '.claude');

  if (options.createDir) {
    try {
      mkdirSync(claudeDir, { recursive: true, mode: 0o700 });
    } catch { /* ignore mkdir errors */ }
  }

  return join(claudeDir, SESSION_ID_FILENAME);
}

/**
 * Generates a new short session ID.
 * Priority: BRAINTRUST_SPAN_ID (first 8 chars) > timestamp-based ID.
 *
 * @returns 8-character session identifier (e.g., "s-m1abc23")
 */
export function generateSessionId(): string {
  const spanId = process.env.BRAINTRUST_SPAN_ID;
  if (spanId) {
    return spanId.slice(0, 8);
  }
  return `s-${Date.now().toString(36)}`;
}

/**
 * Writes the session ID to the persistence file.
 * Creates the ~/.claude/ directory if needed.
 *
 * @param sessionId - The session ID to persist
 * @returns true if write succeeded, false otherwise
 */
export function writeSessionId(sessionId: string): boolean {
  try {
    const filePath = getSessionIdFile({ createDir: true });
    writeFileSync(filePath, sessionId, { encoding: 'utf-8', mode: 0o600 });
    return true;
  } catch {
    return false;
  }
}

/**
 * Reads the session ID from the persistence file.
 *
 * @returns The session ID if found, null otherwise
 */
export function readSessionId(): string | null {
  try {
    const sessionFile = getSessionIdFile();
    const id = readFileSync(sessionFile, 'utf-8').trim();
    return id || null;
  } catch {
    // File doesn't exist or read error - return null
    return null;
  }
}

/**
 * Retrieves the session ID for coordination, checking multiple sources.
 * Priority: env var > file > BRAINTRUST_SPAN_ID > generated.
 *
 * @param options.debug - If true, logs when falling back to generation
 * @returns Session identifier string (e.g., "s-m1abc23")
 */
export function getSessionId(options: { debug?: boolean } = {}): string {
  // First try environment (same process)
  if (process.env.COORDINATION_SESSION_ID) {
    return process.env.COORDINATION_SESSION_ID;
  }

  // Try reading from file (cross-process persistence)
  const fileId = readSessionId();
  if (fileId) {
    return fileId;
  }

  // Fallback - log if debug enabled
  if (options.debug) {
    console.error('[session-id] WARNING: No persisted session ID found, generating new one');
  }

  // Fallback to Braintrust span ID or generate new
  return generateSessionId();
}

/**
 * Returns the current project directory path.
 *
 * @returns CLAUDE_PROJECT_DIR env var or current working directory
 */
export function getProject(): string {
  return process.env.CLAUDE_PROJECT_DIR || process.cwd();
}
