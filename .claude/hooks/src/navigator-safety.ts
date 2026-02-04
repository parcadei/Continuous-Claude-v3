/**
 * Navigator Safety - Destructive Operation Warning (PreToolUse:Bash)
 *
 * Surfaces relevant safety rules before destructive operations:
 * - git reset --hard, git checkout .
 * - rm -rf, rmdir
 * - Database operations (DROP, TRUNCATE, DELETE)
 *
 * Does NOT block - existing hooks (git-memory-check, etc.) handle blocking.
 * This hook surfaces the relevant rule text for Claude's consideration.
 */

import { readFileSync } from 'fs';
import { queryPageIndex } from './shared/pageindex-client.js';
import { outputContinue } from './shared/output.js';

interface PreToolUseInput {
  session_id: string;
  tool_name: string;
  tool_input: {
    command?: string;
    description?: string;
  };
}

interface PreToolUseOutput {
  hookSpecificOutput: {
    hookEventName: 'PreToolUse';
    permissionDecision: 'allow' | 'deny' | 'ask';
    permissionDecisionReason?: string;
  };
}

// Destructive patterns and their associated rule queries
const DESTRUCTIVE_PATTERNS: Array<{
  pattern: RegExp;
  category: string;
  ruleQuery: string;
  ruleText: string;
}> = [
  {
    pattern: /^git\s+(reset\s+--hard|checkout\s+\.|clean\s+-f)/i,
    category: 'Git (destructive)',
    ruleQuery: 'git destructive commands confirmation',
    ruleText: 'Per destructive-commands.md: Ask user before git reset/checkout/clean',
  },
  {
    pattern: /^git\s+push\s+(-f|--force)/i,
    category: 'Git (force push)',
    ruleQuery: 'git force push dangerous',
    ruleText: 'Per destructive-commands.md: NEVER force push to shared branches without explicit confirmation',
  },
  {
    pattern: /^git\s+(checkout|stash|rebase|merge|push|commit)(?:\s|$)/i,
    category: 'Git (state-modifying)',
    ruleQuery: 'git confirmation state modify',
    ruleText: 'Per destructive-commands.md: State-modifying git commands require confirmation',
  },
  {
    pattern: /\brm\s+/i,
    category: 'File deletion',
    ruleQuery: 'file deletion rm confirmation',
    ruleText: 'Per destructive-commands.md: Ask before running rm (any form)',
  },
  {
    pattern: /\brmdir\b/i,
    category: 'Directory deletion',
    ruleQuery: 'directory deletion confirmation',
    ruleText: 'Per destructive-commands.md: Ask before removing directories',
  },
  {
    pattern: /\b(DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE|DELETE\s+FROM)\b/i,
    category: 'Database (destructive)',
    ruleQuery: 'database destructive operations',
    ruleText: 'Database destructive operations require explicit confirmation',
  },
];

function readStdin(): string {
  return readFileSync(0, 'utf-8');
}

/**
 * Check command against destructive patterns.
 */
function checkDestructivePatterns(command: string): {
  isDestructive: boolean;
  categories: string[];
  ruleTexts: string[];
} {
  const matches: { category: string; ruleText: string }[] = [];

  for (const { pattern, category, ruleText } of DESTRUCTIVE_PATTERNS) {
    if (pattern.test(command)) {
      matches.push({ category, ruleText });
    }
  }

  return {
    isDestructive: matches.length > 0,
    categories: matches.map(m => m.category),
    ruleTexts: matches.map(m => m.ruleText),
  };
}

/**
 * Try to get additional context from PageIndex.
 */
function queryRuleContext(ruleQuery: string): string | null {
  const results = queryPageIndex(ruleQuery, null, {
    maxResults: 1,
    timeoutMs: 1500,
  });

  if (results.length > 0) {
    return results[0].text?.slice(0, 200) || results[0].relevanceReason;
  }

  return null;
}

/**
 * Build safety warning message.
 */
function buildSafetyWarning(
  command: string,
  categories: string[],
  ruleTexts: string[]
): string {
  const lines: string[] = [];

  lines.push('NAVIGATOR SAFETY ALERT');
  lines.push('');
  lines.push(`Command: ${command.slice(0, 100)}${command.length > 100 ? '...' : ''}`);
  lines.push(`Pattern: ${categories.join(', ')}`);
  lines.push('');
  lines.push('Relevant Rules:');

  for (const ruleText of ruleTexts) {
    lines.push(`  - ${ruleText}`);
  }

  lines.push('');
  lines.push('Ensure user has confirmed this operation.');

  return lines.join('\n');
}

async function main() {
  const input: PreToolUseInput = JSON.parse(readStdin());

  // Only process Bash tool calls
  if (input.tool_name !== 'Bash') {
    outputContinue();
    return;
  }

  const command = input.tool_input.command;
  if (!command) {
    outputContinue();
    return;
  }

  // Check for destructive patterns
  const { isDestructive, categories, ruleTexts } = checkDestructivePatterns(command);

  if (!isDestructive) {
    outputContinue();
    return;
  }

  // Build warning message (allow but warn)
  const warning = buildSafetyWarning(command, categories, ruleTexts);

  const output: PreToolUseOutput = {
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'allow',
      permissionDecisionReason: warning,
    },
  };

  console.log(JSON.stringify(output));
}

main().catch(() => {
  outputContinue();
});
