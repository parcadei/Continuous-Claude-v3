/**
 * PostToolUse:Edit|Write Hook - Detect code markers and queue for learning capture.
 *
 * Ported from 8t0 system's detect-patterns.sh
 *
 * This hook:
 * 1. Scans tool output and file content for learning signals (HACK, TODO, FIXME, etc.)
 * 2. Detects ADR-worthy discussions (tradeoffs, alternatives)
 * 3. Stores detections as OPEN_THREAD in memory for later capture via /8t0-learn or /8t0-adr
 *
 * Uses PostgreSQL memory system instead of file-based queue.
 */

import { readFileSync, existsSync } from 'fs';
import { execSync } from 'child_process';
import type { PostToolUseInput, LegacyHookOutput } from './shared/types.js';

// Learning signal patterns - things worth capturing as knowledge
const LEARNING_SIGNALS = /\b(HACK|TODO|FIXME|NOTE|WORKAROUND|GOTCHA|tricky|edge[\s._-]?case|be[\s._-]?careful|non[\s._-]?obvious|unexpected|quirk|must[\s._-]?await)\s*:?/gi;

// ADR signal patterns - architectural discussions worth documenting
const ADR_SIGNALS = /\b(should\s+we\s+use|deciding\s+between|trade[\s._-]?off|versus|vs\.?|pros\s+and\s+cons|which\s+approach|recommend|alternative)/gi;

function getSessionId(): string {
  return process.env.COORDINATION_SESSION_ID ||
         process.env.BRAINTRUST_SPAN_ID?.slice(0, 8) ||
         `s-${Date.now().toString(36)}`;
}

function getProjectDir(): string {
  return process.env.CLAUDE_PROJECT_DIR || process.cwd();
}

/**
 * Store detection in PostgreSQL memory as OPEN_THREAD
 */
function storeInMemory(
  type: 'learning' | 'adr',
  signal: string,
  filePath: string,
  context: string
): boolean {
  const sessionId = getSessionId();
  const projectDir = getProjectDir();
  const opcDir = `${projectDir}/opc`;

  // Check if opc directory exists (memory system available)
  if (!existsSync(opcDir)) {
    return false;
  }

  const tags = type === 'learning'
    ? `code-marker,${signal.toLowerCase()},8t0-learn`
    : `adr-opportunity,architecture,8t0-adr`;

  const content = type === 'learning'
    ? `Detected ${signal} in ${filePath}: ${context.slice(0, 200)}`
    : `ADR opportunity in ${filePath}: ${context.slice(0, 200)}`;

  try {
    // Use the store_learning.py script to add to memory
    execSync(`cd "${opcDir}" && PYTHONPATH=. uv run python scripts/core/store_learning.py \
      --session-id "${sessionId}" \
      --type OPEN_THREAD \
      --content "${content.replace(/"/g, '\\"').replace(/\n/g, ' ')}" \
      --context "Detected by code-markers-detector hook" \
      --tags "${tags}" \
      --confidence medium`, {
      stdio: 'pipe',
      timeout: 5000
    });
    return true;
  } catch {
    // Silently fail - don't interrupt the user's work
    return false;
  }
}

/**
 * Extract matching patterns from text
 */
function extractMatches(text: string, pattern: RegExp): string[] {
  const matches: string[] = [];
  let match;
  while ((match = pattern.exec(text)) !== null) {
    matches.push(match[0].trim());
  }
  return matches;
}

export function main(): void {
  // Read hook input from stdin
  let input: PostToolUseInput;
  try {
    const stdinContent = readFileSync(0, 'utf-8');
    input = JSON.parse(stdinContent) as PostToolUseInput;
  } catch {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Only process Edit and Write tools
  if (!['Edit', 'Write'].includes(input.tool_name)) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  const filePath = (input.tool_input?.file_path as string) || '';
  const toolOutput = typeof input.tool_response === 'string'
    ? input.tool_response
    : JSON.stringify(input.tool_response || '');

  // Also check the content being written/edited
  const newContent = (input.tool_input?.new_string as string) ||
                     (input.tool_input?.content as string) || '';

  const combinedText = `${toolOutput}\n${newContent}`;

  // Detect learning signals
  const learningMatches = extractMatches(combinedText, LEARNING_SIGNALS);
  const adrMatches = extractMatches(combinedText, ADR_SIGNALS);

  let detectionsCount = 0;

  // Store learning signals
  if (learningMatches.length > 0) {
    const signal = learningMatches[0];
    if (storeInMemory('learning', signal, filePath, combinedText.slice(0, 500))) {
      detectionsCount++;
    }
  }

  // Store ADR signals
  if (adrMatches.length > 0) {
    if (storeInMemory('adr', 'architecture', filePath, combinedText.slice(0, 500))) {
      detectionsCount++;
    }
  }

  // Prepare output
  let output: LegacyHookOutput = { result: 'continue' };

  if (detectionsCount > 0) {
    const suggestions: string[] = [];
    if (learningMatches.length > 0) {
      suggestions.push(`\`${learningMatches[0]}\` detected - consider /8t0-learn`);
    }
    if (adrMatches.length > 0) {
      suggestions.push('ADR-worthy discussion detected - consider /8t0-adr');
    }

    output.message = `Code markers stored: ${suggestions.join(', ')}`;
  }

  console.log(JSON.stringify(output));
}

// Run if executed directly
main();
