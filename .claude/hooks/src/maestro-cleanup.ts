#!/usr/bin/env node
/**
 * Maestro Cleanup Hook (SessionEnd)
 *
 * Cleans up Maestro and Ralph state files when a session ends.
 * Prevents stale state from blocking new sessions.
 */

import { readFileSync, existsSync, unlinkSync } from 'fs';
import { getStatePathWithMigration, cleanupOldStateFiles } from './shared/session-isolation.js';

interface SessionEndInput {
  session_id?: string;
}

const STATE_FILES = ['maestro-state', 'ralph-state'];

function readStdin(): string {
  try {
    return readFileSync(0, 'utf-8');
  } catch {
    return '{}';
  }
}

function cleanupStateFile(baseName: string, sessionId?: string): boolean {
  try {
    const stateFile = getStatePathWithMigration(baseName, sessionId);
    if (existsSync(stateFile)) {
      unlinkSync(stateFile);
      return true;
    }
  } catch {
    // Ignore cleanup errors
  }
  return false;
}

async function main() {
  let input: SessionEndInput = {};
  try {
    input = JSON.parse(readStdin());
  } catch {
    // Continue with empty input
  }

  const sessionId = input.session_id;
  const cleaned: string[] = [];

  // Clean up state files for this session
  for (const baseName of STATE_FILES) {
    if (cleanupStateFile(baseName, sessionId)) {
      cleaned.push(baseName);
    }
  }

  // Also clean up any stale state files older than 24 hours
  for (const baseName of STATE_FILES) {
    cleanupOldStateFiles(baseName, 24 * 60 * 60 * 1000);
  }

  // Output result
  if (cleaned.length > 0) {
    console.log(JSON.stringify({
      result: 'continue',
      message: `Cleaned up state: ${cleaned.join(', ')}`
    }));
  } else {
    console.log(JSON.stringify({ result: 'continue' }));
  }
}

main().catch(() => {
  console.log(JSON.stringify({ result: 'continue' }));
});
