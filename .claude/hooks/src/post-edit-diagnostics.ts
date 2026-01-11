/**
 * Post-Edit Diagnostics Hook
 *
 * Runs shift-left diagnostics after file edits.
 * Queries TLDR daemon for type errors and lint issues immediately after Edit/Write.
 * Provides early feedback before tests run.
 */

import { readFileSync } from 'fs';
import { queryDaemonSync, trackHookActivitySync } from './daemon-client.js';

interface HookInput {
  tool_name: string;
  tool_input: {
    file_path?: string;
  };
  tool_result?: {
    success?: boolean;
  };
}

interface HookOutput {
  hookSpecificOutput?: {
    hookEventName: string;
    additionalContext?: string;
  };
}

async function main() {
  const input: HookInput = JSON.parse(readFileSync(0, 'utf-8'));

  // Only run on Edit and Write operations
  if (input.tool_name !== 'Edit' && input.tool_name !== 'Write') {
    console.log('{}');
    return;
  }

  const filePath = input.tool_input?.file_path;
  if (!filePath) {
    console.log('{}');
    return;
  }

  // Code file extensions we care about
  const codeExtensions = [
    // Python (has linters: pyright + ruff)
    '.py', '.pyx', '.pyi',
    // TypeScript/JavaScript (TODO: add eslint/tsc)
    '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs',
    // Go (TODO: add go vet)
    '.go',
    // Rust (TODO: add clippy)
    '.rs',
    // Java
    '.java',
    // C/C++
    '.c', '.h', '.cpp', '.hpp', '.cc', '.cxx', '.hh',
    // Ruby
    '.rb',
    // C#
    '.cs',
  ];

  const ext = filePath.substring(filePath.lastIndexOf('.'));

  // Skip non-code files entirely
  if (!codeExtensions.includes(ext)) {
    console.log('{}');
    return;
  }

  // Currently only Python has linters configured in tldr diagnostics
  // Skip other languages until we add their linters
  const pythonExtensions = ['.py', '.pyx', '.pyi'];
  if (!pythonExtensions.includes(ext)) {
    console.log('{}');
    return;
  }

  // Query daemon for diagnostics
  try {
    const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
    const response = queryDaemonSync(
      { cmd: 'diagnostics', file: filePath },
      projectDir
    );

    // If daemon is unavailable or no errors, silently succeed
    if (response.status === 'unavailable' || response.error) {
      console.log('{}');
      return;
    }

    // Handle both direct response and summary-wrapped response formats
    const summary = (response as any).summary || response;
    const typeErrors = summary.type_errors || 0;
    const lintIssues = summary.lint_errors || summary.lint_issues || 0;
    const errors = response.errors || [];

    // Track hook activity (P8) - reuse projectDir from above
    trackHookActivitySync('post-edit-diagnostics', projectDir, true, {
      edits_analyzed: 1,
      type_errors: typeErrors,
      lint_issues: lintIssues,
    });

    // No errors - silent success
    if (typeErrors === 0 && lintIssues === 0) {
      console.log('{}');
      return;
    }

    // Build error summary
    const lines: string[] = [];
    lines.push(`⚠️ Diagnostics: ${typeErrors} type errors, ${lintIssues} lint issues`);

    // Show up to 5 error previews
    const maxPreviews = 5;
    const previews = errors.slice(0, maxPreviews);

    for (const err of previews) {
      const location = err.column
        ? `${err.file}:${err.line}:${err.column}`
        : `${err.file}:${err.line}`;
      lines.push(`   - ${location}: ${err.message}`);
    }

    // Show "... and N more" if there are more errors
    if (errors.length > maxPreviews) {
      const remaining = errors.length - maxPreviews;
      lines.push(`   ... and ${remaining} more`);
    }

    const output: HookOutput = {
      hookSpecificOutput: {
        hookEventName: 'PostToolUse',
        additionalContext: lines.join('\n')
      }
    };
    console.log(JSON.stringify(output));
  } catch {
    // Daemon error - silently ignore (graceful degradation)
    console.log('{}');
  }
}

main().catch(() => console.log('{}'));
