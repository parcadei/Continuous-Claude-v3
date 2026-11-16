#!/usr/bin/env node
/**
 * Failure Detection Hook - PostToolUse hook that detects Bash/Task failures
 * and suggests Nia documentation search to help resolve errors.
 *
 * Phases 12-14, 17-18, 20 of the implementation plan.
 *
 * Detects:
 * - Bash failures: non-zero exit_code
 * - Task failures: error keywords in output
 *
 * On failure, outputs a system reminder with Nia docs search command
 * that includes the error message for context.
 */
import { readFileSync } from 'fs';

// ============================================================================
// Types
// ============================================================================

interface BashToolResponse {
  stdout?: string;
  stderr?: string;
  exit_code?: number;
}

interface PostToolUseInput {
  session_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_response: BashToolResponse | string | unknown;
}

interface HookOutput {
  result: 'continue' | 'block';
  message?: string;
}

// ============================================================================
// Error Detection Patterns
// ============================================================================

/**
 * Patterns that indicate an error in Task tool output.
 * These are checked case-insensitively.
 */
const TASK_ERROR_PATTERNS = [
  /\berror\b/i,
  /\bfailed\b/i,
  /\bexception\b/i,
  /\bcrash(ed)?\b/i,
  /\btimeout\b/i,
  /\babort(ed)?\b/i,
  /\bpanic\b/i,
  /\bfatal\b/i,
];

/**
 * Patterns to extract meaningful error context for search query.
 * First capture group is the error type/name, second is details.
 */
const ERROR_CONTEXT_PATTERNS = [
  /ModuleNotFoundError:\s*No module named\s*['"]?(\w+)['"]?/i,
  /ImportError:\s*(.+)/i,
  /TypeError:\s*(.+)/i,
  /ValueError:\s*(.+)/i,
  /AttributeError:\s*(.+)/i,
  /NameError:\s*(.+)/i,
  /SyntaxError:\s*(.+)/i,
  /RuntimeError:\s*(.+)/i,
  /KeyError:\s*(.+)/i,
  /FileNotFoundError:\s*(.+)/i,
  /PermissionError:\s*(.+)/i,
  /ConnectionError:\s*(.+)/i,
  /OSError:\s*(.+)/i,
  /Error:\s*(.+)/i,
  /error:\s*(.+)/i,
  /failed:\s*(.+)/i,
  /FAILED:\s*(.+)/i,
];

// ============================================================================
// Detection Functions
// ============================================================================

/**
 * Check if Bash tool output indicates a failure.
 */
function isBashFailure(response: unknown): { failed: boolean; errorText: string } {
  if (typeof response === 'object' && response !== null) {
    const bashResponse = response as BashToolResponse;

    // Non-zero exit code is a clear failure
    if (typeof bashResponse.exit_code === 'number' && bashResponse.exit_code !== 0) {
      const stderr = bashResponse.stderr || '';
      const stdout = bashResponse.stdout || '';
      return {
        failed: true,
        errorText: stderr || stdout,
      };
    }
  }

  return { failed: false, errorText: '' };
}

/**
 * Check if Task tool output indicates a failure.
 */
function isTaskFailure(response: unknown): { failed: boolean; errorText: string } {
  let text = '';

  if (typeof response === 'string') {
    text = response;
  } else if (typeof response === 'object' && response !== null) {
    text = JSON.stringify(response);
  }

  for (const pattern of TASK_ERROR_PATTERNS) {
    if (pattern.test(text)) {
      return { failed: true, errorText: text };
    }
  }

  return { failed: false, errorText: '' };
}

/**
 * Extract meaningful error context for the search query.
 * Returns a concise string suitable for Nia search.
 */
function extractErrorContext(errorText: string, toolInput: Record<string, unknown>): string {
  // Try to extract specific error type and details
  for (const pattern of ERROR_CONTEXT_PATTERNS) {
    const match = pattern.exec(errorText);
    if (match) {
      // Return the matched error context (first group or full match)
      const context = match[1] || match[0];
      // Truncate to reasonable length for search
      return context.substring(0, 100).trim();
    }
  }

  // Fall back to first line of error, truncated
  const firstLine = errorText.split('\n')[0] || '';
  if (firstLine.length > 100) {
    return firstLine.substring(0, 100).trim();
  }

  // If still nothing, try to use the command/input as context
  if (toolInput.command && typeof toolInput.command === 'string') {
    return `command failed: ${toolInput.command.substring(0, 50)}`;
  }

  return 'execution failed';
}

/**
 * Build the Nia docs search command suggestion.
 */
function buildNiaSearchCommand(errorContext: string): string {
  // Escape special characters for shell
  const escapedContext = errorContext
    .replace(/'/g, "'\\''")
    .replace(/"/g, '\\"');

  return `uv run python -m runtime.harness scripts/nia_docs.py search universal "${escapedContext}" --limit 5`;
}

// ============================================================================
// Main Hook Logic
// ============================================================================

async function main() {
  let input: PostToolUseInput;

  try {
    const rawInput = readFileSync(0, 'utf-8');
    input = JSON.parse(rawInput) as PostToolUseInput;
  } catch {
    // Malformed input - continue silently
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Only process Bash and Task tools
  if (input.tool_name !== 'Bash' && input.tool_name !== 'Task') {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  let failed = false;
  let errorText = '';

  if (input.tool_name === 'Bash') {
    const result = isBashFailure(input.tool_response);
    failed = result.failed;
    errorText = result.errorText;
  } else if (input.tool_name === 'Task') {
    const result = isTaskFailure(input.tool_response);
    failed = result.failed;
    errorText = result.errorText;
  }

  if (!failed) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Extract error context and build suggestion
  const errorContext = extractErrorContext(errorText, input.tool_input);
  const niaCommand = buildNiaSearchCommand(errorContext);

  const output: HookOutput = {
    result: 'continue',
    message: `
---
**Build/Execution Failure Detected**

Consider searching documentation for help:
\`\`\`bash
${niaCommand}
\`\`\`

Error context: ${errorContext.substring(0, 200)}
---`,
  };

  console.log(JSON.stringify(output));
}

main().catch(() => {
  console.log(JSON.stringify({ result: 'continue' }));
});
