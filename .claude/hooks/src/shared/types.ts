/**
 * Shared type definitions for Claude Code hooks.
 *
 * Centralizes interface definitions to avoid duplication across:
 * - pattern-router.ts
 * - db-utils.ts
 * - patterns/swarm.ts
 * - subagent-start.ts
 * - pre-tool-use.ts
 *
 * Part of the pattern-aware hooks infrastructure.
 * See: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md
 */

// =============================================================================
// Hook Input Types
// =============================================================================

export interface SubagentStartInput {
  session_id: string;
  agent_id?: string | null;
  agent_type?: string;
}

export interface SubagentStopInput {
  session_id: string;
  agent_id?: string | null;
  agent_type?: string;
}

export interface PreToolUseInput {
  session_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
}

export interface PostToolUseInput {
  session_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_response: unknown;
}

export interface StopInput {
  session_id: string;
  stop_hook_active?: boolean;
}

// =============================================================================
// Hook Output Types
// =============================================================================

export interface HookOutput {
  result: 'continue' | 'block';
  message?: string;
  reason?: string;
}

// =============================================================================
// Database Query Result Types
// =============================================================================

export interface QueryResult {
  success: boolean;
  stdout: string;
  stderr: string;
}
