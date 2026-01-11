/**
 * UserPromptSubmit Hook: Impact Analysis for Refactoring (DAEMON)
 *
 * When user mentions refactor/change/rename + function name, automatically
 * runs impact analysis via daemon and injects the results as context.
 *
 * Uses TLDR daemon for fast cached responses (50ms vs 500ms CLI).
 */

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { queryDaemonSync, DaemonResponse, trackHookActivitySync } from './daemon-client';

interface UserPromptInput {
  session_id: string;
  hook_event_name: string;
  prompt: string;
  cwd: string;
}

// Keywords that trigger impact analysis
const REFACTOR_KEYWORDS = [
  /\brefactor\b/i,
  /\brename\b/i,
  /\bchange\b.*\bfunction\b/i,
  /\bmodify\b.*\b(?:function|method|class)\b/i,
  /\bupdate\b.*\bsignature\b/i,
  /\bmove\b.*\bfunction\b/i,
  /\bdelete\b.*\b(?:function|method)\b/i,
  /\bremove\b.*\b(?:function|method)\b/i,
  /\bextract\b.*\b(?:function|method)\b/i,
  /\binline\b.*\b(?:function|method)\b/i,
];

// Extract function/method names from prompt
const FUNCTION_PATTERNS = [
  /(?:refactor|rename|change|modify|update|move|delete|remove)\s+(?:the\s+)?(?:function\s+)?[`"']?(\w+)[`"']?/gi,
  /[`"'](\w+)[`"']\s+(?:function|method)/gi,
  /(?:function|method|def|fn)\s+[`"']?(\w+)[`"']?/gi,
];

const EXCLUDE_WORDS = new Set([
  'the', 'this', 'that', 'function', 'method', 'class', 'file',
  'to', 'from', 'into', 'a', 'an', 'and', 'or', 'for', 'with',
]);

function readStdin(): string {
  return readFileSync(0, 'utf-8');
}

function shouldTrigger(prompt: string): boolean {
  return REFACTOR_KEYWORDS.some(pattern => pattern.test(prompt));
}

function extractFunctionNames(prompt: string): string[] {
  const candidates: Set<string> = new Set();

  for (const pattern of FUNCTION_PATTERNS) {
    let match;
    // Reset lastIndex for global patterns
    pattern.lastIndex = 0;
    while ((match = pattern.exec(prompt)) !== null) {
      const name = match[1];
      if (name && name.length > 2 && !EXCLUDE_WORDS.has(name.toLowerCase())) {
        candidates.add(name);
      }
    }
  }

  // Also look for snake_case and camelCase identifiers
  const identifierPattern = /\b([a-z][a-z0-9_]*[a-z0-9])\b/gi;
  let match;
  while ((match = identifierPattern.exec(prompt)) !== null) {
    const name = match[1];
    if (name.length > 4 && !EXCLUDE_WORDS.has(name.toLowerCase())) {
      // Only add if it looks like a function name (has underscore or is camelCase)
      if (name.includes('_') || /[a-z][A-Z]/.test(name)) {
        candidates.add(name);
      }
    }
  }

  return Array.from(candidates);
}

interface Caller {
  file: string;
  function: string;
  line: number;
}

interface Importer {
  file: string;
  line?: number;
}

/**
 * Get module-level importers using TLDR daemon.
 * Shows which files import a module (broader than function-level callers).
 */
function getImportersFromDaemon(moduleName: string, projectDir: string): Importer[] | null {
  try {
    const response = queryDaemonSync({ cmd: 'importers', module: moduleName }, projectDir);

    if (response.indexing) {
      return null;
    }

    if (response.status === 'unavailable' || response.status === 'error') {
      return null;
    }

    if (response.importers && Array.isArray(response.importers)) {
      return response.importers;
    }

    return [];
  } catch {
    return null;
  }
}

function getImpactFromDaemon(functionName: string, projectDir: string): Caller[] | null {
  try {
    const response = queryDaemonSync({ cmd: 'impact', func: functionName }, projectDir);

    if (response.indexing) {
      return null;  // Daemon still indexing
    }

    if (response.status === 'unavailable' || response.status === 'error') {
      return null;
    }

    if (response.callers && Array.isArray(response.callers)) {
      return response.callers;
    }

    return [];
  } catch {
    return null;
  }
}

function formatCallers(callers: Caller[]): string {
  if (callers.length === 0) {
    return 'No callers found (function may be an entry point or unused)';
  }

  return callers.slice(0, 15).map(c => {
    const loc = c.line ? `${c.file}:${c.line}` : c.file;
    return `  - ${c.function || 'unknown'} in ${loc}`;
  }).join('\n') + (callers.length > 15 ? `\n  ... and ${callers.length - 15} more` : '');
}

function formatImporters(importers: Importer[]): string {
  if (importers.length === 0) {
    return 'No importers found';
  }

  return importers.slice(0, 10).map(i => {
    const loc = i.line ? `${i.file}:${i.line}` : i.file;
    return `  - ${loc}`;
  }).join('\n') + (importers.length > 10 ? `\n  ... and ${importers.length - 10} more` : '');
}

async function main() {
  const input: UserPromptInput = JSON.parse(readStdin());
  const prompt = input.prompt;

  // Check if this looks like a refactoring request
  if (!shouldTrigger(prompt)) {
    console.log('');
    return;
  }

  // Extract function names
  const functions = extractFunctionNames(prompt);
  if (functions.length === 0) {
    console.log('');
    return;
  }

  const projectDir = process.env.CLAUDE_PROJECT_DIR || input.cwd;

  const results: string[] = [];

  for (const funcName of functions.slice(0, 3)) {  // Max 3 functions
    const callers = getImpactFromDaemon(funcName, projectDir);

    if (callers === null) {
      // Daemon unavailable, skip
      continue;
    }

    // Also get module-level importers (broader impact)
    // Try to infer module name from function name (e.g., "api" from "api.py")
    const importers = getImportersFromDaemon(funcName, projectDir);

    let impact = `📊 **Impact: ${funcName}**\nCallers:\n${formatCallers(callers)}`;

    if (importers && importers.length > 0) {
      impact += `\n\nModule importers:\n${formatImporters(importers)}`;
    }

    results.push(impact);
  }

  // Track hook activity (P8)
  const totalCallers = results.length > 0 ? results.join(' ').match(/Callers:/g)?.length || 0 : 0;
  trackHookActivitySync('impact-refactor', projectDir, true, {
    analyses_run: functions.length,
    results_found: results.length,
  });

  if (results.length > 0) {
    console.log(`\n⚠️ **REFACTORING IMPACT ANALYSIS**\n\n${results.join('\n\n')}\n\nConsider callers AND importers before making changes.\n`);
  } else {
    console.log('');
  }
}

main().catch(() => {
  // Silent fail
  console.log('');
});
