#!/usr/bin/env node
/**
 * Heartbeat Hook - Updates session last_heartbeat on each user prompt
 *
 * Runs on UserPromptSubmit to keep the session marked as active
 * in the cross-terminal coordination database.
 */

import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';
import { registerSession } from './shared/db-utils-pg.js';
import { getSessionId } from './shared/session-id.js';

// Cache heartbeat to avoid DB update on every prompt
const CACHE_TTL_MS = 30000;  // 30 seconds
const CACHE_DIR = join(process.env.HOME || process.env.USERPROFILE || '', '.claude', 'cache');
const CACHE_FILE = join(CACHE_DIR, 'heartbeat-last.json');

function shouldUpdateHeartbeat(sessionId: string): boolean {
  try {
    if (!existsSync(CACHE_FILE)) return true;
    const cache = JSON.parse(readFileSync(CACHE_FILE, 'utf-8'));
    if (cache.sessionId !== sessionId) return true;
    const elapsed = Date.now() - cache.timestamp;
    return elapsed >= CACHE_TTL_MS;
  } catch {
    return true;
  }
}

function updateCache(sessionId: string): void {
  try {
    mkdirSync(CACHE_DIR, { recursive: true });
    writeFileSync(CACHE_FILE, JSON.stringify({ sessionId, timestamp: Date.now() }));
  } catch {
    // Ignore cache write failures
  }
}

interface HookInput {
  session_id?: string;
  cwd?: string;
  prompt?: string;
}

function readStdin(): string {
  return readFileSync(0, 'utf-8');
}

function main(): void {
  let input: HookInput = {};

  try {
    const rawInput = readStdin().trim();
    if (rawInput) {
      input = JSON.parse(rawInput);
    }
  } catch {
    // Ignore parse errors
  }

  const sessionId = input.session_id || getSessionId();
  const project = input.cwd || process.cwd();

  // Guard: Skip in ~/.claude (infrastructure directory)
  const homeDir = process.env.HOME || process.env.USERPROFILE || '';
  if (homeDir) {
    const claudeDir = homeDir.replace(/\\/g, '/') + '/.claude';
    const normalizedProject = project.replace(/\\/g, '/');
    if (normalizedProject === claudeDir || normalizedProject.endsWith('/.claude')) {
      console.log(JSON.stringify({ result: 'continue' }));
      return;
    }
  }

  // Extract first line of prompt as "working on" context (max 100 chars)
  const workingOn = input.prompt
    ? input.prompt.split('\n')[0].substring(0, 100)
    : undefined;

  // Skip DB update if within cache TTL (30s) for same session
  if (!shouldUpdateHeartbeat(sessionId)) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Update session heartbeat via registerSession (upserts)
  const result = registerSession(sessionId, project, workingOn);

  if (!result.success) {
    console.error(`Heartbeat update failed: ${result.error}`);
  } else {
    updateCache(sessionId);
  }

  console.log(JSON.stringify({ result: 'continue' }));
}

try {
  main();
} catch (err) {
  console.error('Heartbeat error:', err);
  console.log(JSON.stringify({ result: 'continue' }));
}
