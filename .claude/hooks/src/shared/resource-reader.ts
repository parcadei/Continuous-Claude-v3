/**
 * Resource State Reader Utility
 *
 * Reads resource state JSON from /tmp/claude-resources-{sessionId}.json.
 * This file is written by status.sh (Phase 3) and contains:
 * - freeMemMB: Available RAM in MB
 * - activeAgents: Number of currently running agents
 * - maxAgents: Maximum agents allowed based on RAM
 * - contextPct: Current context usage percentage
 *
 * Part of Phase 4: TypeScript Resource Reader
 * See: docs/handoffs/resource-limits-plan.md
 */

import { readFileSync, existsSync } from 'fs';

// =============================================================================
// Types
// =============================================================================

/**
 * Resource state from the JSON file written by status.sh.
 */
export interface ResourceState {
  /** Free RAM in MB */
  freeMemMB: number;
  /** Number of currently running agents */
  activeAgents: number;
  /** Maximum agents allowed based on available RAM */
  maxAgents: number;
  /** Current context usage percentage (0-100) */
  contextPct: number;
}

// =============================================================================
// Constants
// =============================================================================

/**
 * Default resource state used when file is missing or corrupt.
 *
 * Values chosen to be conservative:
 * - freeMemMB: 4096 (4GB, reasonable minimum)
 * - activeAgents: 0 (assume none running)
 * - maxAgents: 10 (reasonable default limit)
 * - contextPct: 0 (assume fresh context)
 */
export const DEFAULT_RESOURCE_STATE: ResourceState = {
  freeMemMB: 4096,
  activeAgents: 0,
  maxAgents: 10,
  contextPct: 0,
};

// =============================================================================
// Functions
// =============================================================================

/**
 * Get the session ID from environment variables.
 *
 * Priority:
 * 1. CLAUDE_SESSION_ID (if set by Claude Code)
 * 2. PPID (parent process ID as fallback)
 *
 * @returns Session ID string
 */
export function getSessionId(): string {
  return process.env.CLAUDE_SESSION_ID || String(process.ppid || process.pid);
}

/**
 * Get the path to the resource state JSON file.
 *
 * @param sessionId - Session ID to use in the filename
 * @returns Path to /tmp/claude-resources-{sessionId}.json
 */
export function getResourceFilePath(sessionId: string): string {
  return `/tmp/claude-resources-${sessionId}.json`;
}

/**
 * Read resource state from the JSON file.
 *
 * Reads /tmp/claude-resources-{sessionId}.json and parses it into a
 * ResourceState object. Returns null if:
 * - File doesn't exist
 * - File contains invalid JSON
 *
 * Missing fields are filled with defaults from DEFAULT_RESOURCE_STATE.
 *
 * @returns ResourceState object or null if file is missing/corrupt
 *
 * @example
 * ```typescript
 * import { readResourceState } from './shared/resource-reader.js';
 *
 * const state = readResourceState();
 * if (state && state.activeAgents >= state.maxAgents) {
 *   console.log('Agent limit reached!');
 * }
 * ```
 */
export function readResourceState(): ResourceState | null {
  const sessionId = getSessionId();
  const resourceFile = getResourceFilePath(sessionId);

  // Return null if file doesn't exist
  if (!existsSync(resourceFile)) {
    return null;
  }

  try {
    const content = readFileSync(resourceFile, 'utf-8');
    const data = JSON.parse(content);

    // Merge with defaults to handle missing fields
    return {
      freeMemMB: typeof data.freeMemMB === 'number' ? data.freeMemMB : DEFAULT_RESOURCE_STATE.freeMemMB,
      activeAgents: typeof data.activeAgents === 'number' ? data.activeAgents : DEFAULT_RESOURCE_STATE.activeAgents,
      maxAgents: typeof data.maxAgents === 'number' ? data.maxAgents : DEFAULT_RESOURCE_STATE.maxAgents,
      contextPct: typeof data.contextPct === 'number' ? data.contextPct : DEFAULT_RESOURCE_STATE.contextPct,
    };
  } catch {
    // Return null on JSON parse error or file read error
    return null;
  }
}
