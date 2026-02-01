/**
 * Memory Awareness Hook (UserPromptSubmit)
 *
 * Checks if user prompt is similar to stored learnings.
 * Shows hint to BOTH user (visible) AND Claude (system context).
 *
 * Flow:
 * 1. Extract INTENT from user prompt (not just keywords)
 * 2. Semantic search using hybrid RRF (text + vector)
 * 3. If score > threshold, show visible hint with top learning preview
 * 4. Claude proactively discloses and acts on relevant memories
 */

import { readFileSync, existsSync } from 'fs';
import * as path from 'path';
import { spawnSync } from 'child_process';
import { getOpcDir } from './shared/opc-path.js';
import { outputContinue } from './shared/output.js';

interface UserPromptSubmitInput {
  session_id: string;
  hook_event_name: string;
  prompt: string;
  cwd: string;
}

interface LearningResult {
  id: string;
  type: string;
  content: string;
  score: number;
}

interface MemoryMatch {
  count: number;
  results: LearningResult[];
}

function readStdin(): string {
  return readFileSync(0, 'utf-8');
}

/**
 * Check if we're running in ~/.claude (infrastructure directory).
 * Skip all DB operations in this directory to prevent hangs.
 */
function isInfrastructureDir(projectDir: string): boolean {
  const homeDir = process.env.HOME || process.env.USERPROFILE || '';
  if (!homeDir) return false;
  const claudeDir = homeDir.replace(/\\/g, '/') + '/.claude';
  const normalizedProject = (projectDir || '').replace(/\\/g, '/');
  return normalizedProject === claudeDir || normalizedProject.endsWith('/.claude');
}

/**
 * Extract the INTENT from user prompt - what they're actually asking about.
 * Removes meta-language ("can you", "help me", "recall") to get core topic.
 */
function extractIntent(prompt: string): string {
  // Meta-phrases to remove (these describe HOW, not WHAT)
  const metaPhrases = [
    /^(can you|could you|would you|please|help me|i want to|i need to|let's|lets)\s+/gi,
    /^(show me|tell me|find|search for|look for|recall|remember)\s+/gi,
    /^(how do i|how can i|how to|what is|what are|where is|where are)\s+/gi,
    /\s+(for me|please|thanks|thank you)$/gi,
    /\?$/g,
  ];

  let intent = prompt.trim();

  // Strip meta-phrases iteratively
  for (const pattern of metaPhrases) {
    intent = intent.replace(pattern, '');
  }

  intent = intent.trim();

  // If we stripped too much, fall back to keyword extraction
  if (intent.length < 5) {
    return extractKeywords(prompt);
  }

  return intent;
}

/**
 * Extract meaningful keywords from prompt (fallback for very short intents).
 */
function extractKeywords(prompt: string): string {
  const stopWords = new Set([
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'can', 'to', 'of', 'in', 'for',
    'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
    'before', 'after', 'above', 'below', 'between', 'under', 'again',
    'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why',
    'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some', 'such',
    'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
    's', 't', 'just', 'don', 'now', 'i', 'me', 'my', 'you', 'your', 'we', 'help', 'with',
    'our', 'they', 'them', 'their', 'it', 'its', 'this', 'that', 'these',
    'what', 'which', 'who', 'whom', 'and', 'but', 'if', 'or', 'because',
    'until', 'while', 'about', 'against', 'also', 'get', 'got', 'make',
    'want', 'need', 'look', 'see', 'use', 'like', 'know', 'think', 'take',
    'come', 'go', 'say', 'said', 'tell', 'please', 'help', 'let', 'sure',
    'recall', 'remember', 'similar', 'problems', 'issues'
  ]);

  const words = prompt
    .toLowerCase()
    .replace(/[^\w\s-]/g, ' ')
    .split(/\s+/)
    .filter(w => w.length > 2 && !stopWords.has(w));

  return [...new Set(words)].slice(0, 5).join(' ');
}

/**
 * Check local project memory index first (topic keyword match).
 * Returns results from .claude/memory/index.json if available.
 */
function checkLocalMemory(intent: string, projectDir: string): MemoryMatch | null {
  const homeDir = process.env.HOME || process.env.USERPROFILE || '';
  const projectMemoryScript = path.join(homeDir, '.claude', 'scripts', 'core', 'core', 'project_memory.py');

  if (!existsSync(projectMemoryScript)) return null;

  try {
    const result = spawnSync('uv', [
      'run', 'python', projectMemoryScript,
      'query', intent,
      '--project-dir', projectDir,
      '-k', '3',
      '--json'
    ], {
      encoding: 'utf-8',
      cwd: path.join(homeDir, '.claude', 'scripts', 'core', 'core'),
      timeout: 2000,
      killSignal: 'SIGKILL',
    });

    if (result.status !== 0 || !result.stdout) return null;

    const data = JSON.parse(result.stdout);
    if (!data.results || data.results.length === 0) return null;

    const results: LearningResult[] = data.results.slice(0, 3).map((r: any) => ({
      id: r.task_id || r.id || 'local',
      type: 'LOCAL_HANDOFF',
      content: r.summary || r.content || '',
      score: r.similarity || 0.5
    }));

    return { count: data.count || results.length, results };
  } catch {
    return null;
  }
}

/**
 * Fast memory relevance check using text search.
 * Local-first: checks project memory, then falls back to global DB.
 */
function checkMemoryRelevance(intent: string, projectDir: string): MemoryMatch | null {
  if (!intent || intent.length < 3) return null;

  // 1. Try local project memory first (fast topic index)
  const localMatch = checkLocalMemory(intent, projectDir);
  if (localMatch) {
    return localMatch;
  }

  // 2. Fall back to global DB search
  const opcDir = getOpcDir();
  if (!opcDir) return null;

  const searchTerm = intent
    .replace(/[_\/]/g, ' ')
    .replace(/\b\w{1,2}\b/g, '')
    .replace(/\s+/g, ' ')
    .trim();

  const result = spawnSync('uv', [
    'run', 'python', 'scripts/core/recall_learnings.py',
    '--query', searchTerm,
    '--k', '3',
    '--json',
    '--text-only'
  ], {
    encoding: 'utf-8',
    cwd: opcDir,
    env: {
      ...process.env,
      PYTHONPATH: opcDir
    },
    timeout: 2000,
    killSignal: 'SIGKILL',
  });

  if (result.status !== 0 || !result.stdout) {
    return null;
  }

  try {
    const data = JSON.parse(result.stdout);

    if (!data.results || data.results.length === 0) {
      return null;
    }

    // ts_rank returns small values (0.0001-0.1), ILIKE fallback returns 0.1
    // Any match from FTS is relevant enough to show

    // Extract structured results with better previews
    const results: LearningResult[] = data.results.slice(0, 3).map((r: any) => {
      const content = r.content || '';
      // Get first meaningful line up to 120 chars
      const preview = content
        .split('\n')
        .filter((l: string) => l.trim().length > 0)
        .map((l: string) => l.trim())
        .join(' ')
        .slice(0, 120);

      return {
        id: (r.id || 'unknown').slice(0, 8),
        type: r.learning_type || r.type || 'UNKNOWN',
        content: preview + (content.length > 120 ? '...' : ''),
        score: r.score || 0
      };
    });

    return {
      count: data.results.length,
      results
    };
  } catch {
    return null;
  }
}

async function main() {
  const input: UserPromptSubmitInput = JSON.parse(readStdin());
  const projectDir = process.env.CLAUDE_PROJECT_DIR || input.cwd;

  // Guard: Skip in ~/.claude (infrastructure directory) to prevent DB hangs
  if (isInfrastructureDir(projectDir)) {
    outputContinue();
    return;
  }

  // Skip for subagents - they don't need memory recall (saves tokens)
  if (process.env.CLAUDE_AGENT_ID) {
    outputContinue();
    return;
  }

  // Skip very short prompts (greetings, commands)
  if (input.prompt.length < 15) {
    outputContinue();
    return;
  }

  // Skip if prompt is just a slash command
  if (input.prompt.trim().startsWith('/')) {
    outputContinue();
    return;
  }

  // Extract intent (semantic query, not just keywords)
  const intent = extractIntent(input.prompt);

  // Skip if no meaningful intent
  if (intent.length < 3) {
    outputContinue();
    return;
  }

  // Check memory relevance using semantic search
  const match = checkMemoryRelevance(intent, projectDir);

  if (match) {
    // Build structured context for Claude
    const resultLines = match.results.map((r, i) =>
      `${i + 1}. [${r.type}] ${r.content} (id: ${r.id})`
    ).join('\n');

    const claudeContext = `MEMORY MATCH (${match.count} results) for "${intent}":\n${resultLines}\nUse /recall "${intent}" for full content. Disclose if helpful.`;

    console.log(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'UserPromptSubmit',
        additionalContext: claudeContext
      }
    }));
  } else {
    outputContinue();
  }
}

main().catch(() => {
  // Silent fail - don't block user prompts
  outputContinue();
});
