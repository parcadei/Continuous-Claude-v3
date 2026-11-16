/**
 * Transcript Parser Module
 *
 * Parses JSONL transcript files from Claude Code sessions and extracts
 * high-signal data for use by PreCompact hooks and auto-handoff generation.
 */

import * as fs from 'fs';

// ============================================================================
// Type Definitions
// ============================================================================

export interface TodoItem {
  id: string;
  content: string;
  status: 'pending' | 'in_progress' | 'completed';
}

export interface ToolCall {
  name: string;
  timestamp?: string;
  input?: Record<string, unknown>;
  success?: boolean;
}

export interface TranscriptSummary {
  lastTodos: TodoItem[];
  recentToolCalls: ToolCall[];
  lastAssistantMessage: string;
  filesModified: string[];
  errorsEncountered: string[];
}

// Internal types for parsing
interface TranscriptEntry {
  type?: string;
  role?: string;
  content?: unknown;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_result?: unknown;
  timestamp?: string;
  error?: string;
}

interface TodoWriteInput {
  todos?: Array<{
    id?: string;
    content?: string;
    status?: string;
  }>;
}

interface EditWriteInput {
  file_path?: string;
  path?: string;
}

interface BashInput {
  command?: string;
}

interface BashResult {
  exit_code?: number;
  exitCode?: number;
  stderr?: string;
  error?: string;
}

// ============================================================================
// Parse Functions
// ============================================================================

/**
 * Parse a JSONL transcript file and extract high-signal data.
 *
 * @param transcriptPath - Absolute path to the JSONL transcript file
 * @returns TranscriptSummary with extracted data
 */
export function parseTranscript(transcriptPath: string): TranscriptSummary {
  const summary: TranscriptSummary = {
    lastTodos: [],
    recentToolCalls: [],
    lastAssistantMessage: '',
    filesModified: [],
    errorsEncountered: []
  };

  if (!fs.existsSync(transcriptPath)) {
    return summary;
  }

  const content = fs.readFileSync(transcriptPath, 'utf-8');
  const lines = content.split('\n').filter(line => line.trim());

  const allToolCalls: ToolCall[] = [];
  const modifiedFiles = new Set<string>();
  const errors: string[] = [];
  let lastTodoState: TodoItem[] = [];
  let lastAssistant = '';

  for (const line of lines) {
    try {
      const entry: TranscriptEntry = JSON.parse(line);

      // Extract last assistant message
      if (entry.role === 'assistant' && typeof entry.content === 'string') {
        lastAssistant = entry.content;
      } else if (entry.type === 'assistant' && typeof entry.content === 'string') {
        lastAssistant = entry.content;
      }

      // Extract tool calls
      if (entry.tool_name || entry.type === 'tool_use') {
        const toolName = entry.tool_name || (entry as Record<string, unknown>).name as string;
        if (toolName) {
          const toolCall: ToolCall = {
            name: toolName,
            timestamp: entry.timestamp,
            input: entry.tool_input,
            success: true // Will be updated by result
          };

          // Check for TodoWrite to capture state
          if (toolName === 'TodoWrite' || toolName.toLowerCase().includes('todowrite')) {
            const input = entry.tool_input as TodoWriteInput | undefined;
            if (input?.todos) {
              lastTodoState = input.todos.map((t, idx) => ({
                id: t.id || `todo-${idx}`,
                content: t.content || '',
                status: (t.status as TodoItem['status']) || 'pending'
              }));
            }
          }

          // Track file modifications from Edit/Write tools
          if (toolName === 'Edit' || toolName === 'Write' ||
              toolName.toLowerCase().includes('edit') ||
              toolName.toLowerCase().includes('write')) {
            const input = entry.tool_input as EditWriteInput | undefined;
            const filePath = input?.file_path || input?.path;
            if (filePath && typeof filePath === 'string') {
              modifiedFiles.add(filePath);
            }
          }

          // Track Bash commands for potential errors
          if (toolName === 'Bash' || toolName.toLowerCase().includes('bash')) {
            const input = entry.tool_input as BashInput | undefined;
            if (input?.command) {
              toolCall.input = { command: input.command };
            }
          }

          allToolCalls.push(toolCall);
        }
      }

      // Extract tool results and check for failures
      if (entry.type === 'tool_result' || entry.tool_result !== undefined) {
        const result = entry.tool_result as BashResult | undefined;

        // Check for Bash failures
        if (result) {
          const exitCode = result.exit_code ?? result.exitCode;
          if (exitCode !== undefined && exitCode !== 0) {
            // Mark last tool call as failed
            if (allToolCalls.length > 0) {
              allToolCalls[allToolCalls.length - 1].success = false;
            }

            // Extract error message
            const errorMsg = result.stderr || result.error || 'Command failed';
            const lastTool = allToolCalls[allToolCalls.length - 1];
            const command = (lastTool?.input as BashInput)?.command || 'unknown command';
            errors.push(`${command}: ${errorMsg.substring(0, 200)}`);
          }
        }

        // Check for explicit errors
        if (entry.error) {
          errors.push(entry.error.substring(0, 200));
          if (allToolCalls.length > 0) {
            allToolCalls[allToolCalls.length - 1].success = false;
          }
        }
      }

    } catch {
      // Skip malformed JSON lines
      continue;
    }
  }

  // Populate summary
  summary.lastTodos = lastTodoState;
  summary.recentToolCalls = allToolCalls.slice(-5); // Last 5 tool calls
  summary.lastAssistantMessage = lastAssistant.substring(0, 500);
  summary.filesModified = Array.from(modifiedFiles);
  summary.errorsEncountered = errors.slice(-5); // Last 5 errors

  return summary;
}

// ============================================================================
// Auto-Handoff Generation
// ============================================================================

/**
 * Generate a markdown auto-handoff document from a transcript summary.
 *
 * @param summary - TranscriptSummary from parseTranscript
 * @param sessionName - Name of the session for metadata
 * @returns Markdown string suitable for writing to a handoff file
 */
export function generateAutoHandoff(summary: TranscriptSummary, sessionName: string): string {
  const timestamp = new Date().toISOString();
  const lines: string[] = [];

  // YAML frontmatter
  lines.push('---');
  lines.push(`date: ${timestamp}`);
  lines.push('type: auto-handoff');
  lines.push('trigger: pre-compact-auto');
  lines.push(`session: ${sessionName}`);
  lines.push('---');
  lines.push('');

  // Header
  lines.push('# Auto-Handoff (PreCompact)');
  lines.push('');
  lines.push('This handoff was automatically generated before context compaction.');
  lines.push('');

  // In Progress section (TodoWrite state)
  lines.push('## In Progress');
  lines.push('');
  if (summary.lastTodos.length > 0) {
    const inProgress = summary.lastTodos.filter(t => t.status === 'in_progress');
    const pending = summary.lastTodos.filter(t => t.status === 'pending');
    const completed = summary.lastTodos.filter(t => t.status === 'completed');

    if (inProgress.length > 0) {
      lines.push('**Active:**');
      inProgress.forEach(t => lines.push(`- [>] ${t.content}`));
      lines.push('');
    }

    if (pending.length > 0) {
      lines.push('**Pending:**');
      pending.forEach(t => lines.push(`- [ ] ${t.content}`));
      lines.push('');
    }

    if (completed.length > 0) {
      lines.push('**Completed this session:**');
      completed.forEach(t => lines.push(`- [x] ${t.content}`));
      lines.push('');
    }
  } else {
    lines.push('No TodoWrite state captured.');
    lines.push('');
  }

  // Recent Actions section
  lines.push('## Recent Actions');
  lines.push('');
  if (summary.recentToolCalls.length > 0) {
    summary.recentToolCalls.forEach(tc => {
      const status = tc.success ? 'OK' : 'FAILED';
      const inputSummary = tc.input
        ? ` - ${JSON.stringify(tc.input).substring(0, 80)}...`
        : '';
      lines.push(`- ${tc.name} [${status}]${inputSummary}`);
    });
  } else {
    lines.push('No tool calls recorded.');
  }
  lines.push('');

  // Files Modified section
  lines.push('## Files Modified');
  lines.push('');
  if (summary.filesModified.length > 0) {
    summary.filesModified.forEach(f => lines.push(`- ${f}`));
  } else {
    lines.push('No files modified.');
  }
  lines.push('');

  // Errors section
  if (summary.errorsEncountered.length > 0) {
    lines.push('## Errors Encountered');
    lines.push('');
    summary.errorsEncountered.forEach(e => {
      lines.push('```');
      lines.push(e);
      lines.push('```');
    });
    lines.push('');
  }

  // Last Context section
  lines.push('## Last Context');
  lines.push('');
  if (summary.lastAssistantMessage) {
    lines.push('```');
    lines.push(summary.lastAssistantMessage);
    if (summary.lastAssistantMessage.length >= 500) {
      lines.push('[... truncated]');
    }
    lines.push('```');
  } else {
    lines.push('No assistant message captured.');
  }
  lines.push('');

  // Suggested Next Steps
  lines.push('## Suggested Next Steps');
  lines.push('');
  lines.push('1. Review the "In Progress" section for current task state');
  lines.push('2. Check "Errors Encountered" if debugging issues');
  lines.push('3. Read modified files to understand recent changes');
  lines.push('4. Continue from where session left off');
  lines.push('');

  return lines.join('\n');
}

// ============================================================================
// CLI Entry Point (for testing)
// ============================================================================

// Allow running as CLI for testing: npx tsx transcript-parser.ts /path/to/transcript.jsonl
// ES module compatible entry point check
const isMainModule = import.meta.url === `file://${process.argv[1]}`;

if (isMainModule) {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.log('Usage: npx tsx transcript-parser.ts <transcript-path> [session-name]');
    process.exit(1);
  }

  const transcriptPath = args[0];
  const sessionName = args[1] || 'test-session';

  console.log(`Parsing transcript: ${transcriptPath}`);
  const summary = parseTranscript(transcriptPath);

  console.log('\n--- Summary ---');
  console.log(JSON.stringify(summary, null, 2));

  console.log('\n--- Auto-Handoff ---');
  console.log(generateAutoHandoff(summary, sessionName));
}
