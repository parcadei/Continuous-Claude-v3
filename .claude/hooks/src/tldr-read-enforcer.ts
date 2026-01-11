/**
 * TLDR Read Enforcer Hook - BLOCKING VERSION (DAEMON)
 *
 * Intercepts Read tool calls for code files and BLOCKS with TLDR context.
 * Instead of reading 1000+ line files, returns structured L1 AST context.
 *
 * Uses TLDR daemon for fast cached responses (50ms vs 500ms CLI).
 *
 * Result: 95% token savings (50-500 tokens vs 3000-20000 raw)
 */

import { readFileSync, existsSync, statSync } from 'fs';
import { basename, extname } from 'path';
import { queryDaemonSync, DaemonResponse, trackHookActivitySync } from './daemon-client';

// Search context from smart-search-router
interface SearchContext {
  timestamp: number;
  queryType: 'structural' | 'semantic' | 'literal';
  pattern: string;
  target: string | null;
  targetType: 'function' | 'class' | 'variable' | 'import' | 'decorator' | 'unknown';
  suggestedLayers: string[];
  definitionLocation?: string;  // Where the symbol is defined
  callers?: string[];           // Cross-file: where the symbol is called/used
}

const CONTEXT_DIR = '/tmp/claude-search-context';
const CONTEXT_MAX_AGE_MS = 30000; // 30 seconds - context expires after this

/**
 * Read search context from smart-search-router (if recent)
 */
function getSearchContext(sessionId: string): SearchContext | null {
  try {
    const contextPath = `${CONTEXT_DIR}/${sessionId}.json`;
    if (!existsSync(contextPath)) return null;

    const context: SearchContext = JSON.parse(readFileSync(contextPath, 'utf-8'));

    // Check if context is stale
    if (Date.now() - context.timestamp > CONTEXT_MAX_AGE_MS) {
      return null;
    }

    return context;
  } catch {
    return null;
  }
}

interface HookInput {
  session_id: string;
  hook_event_name: string;
  tool_name: string;
  tool_input: {
    file_path?: string;
    limit?: number;
    offset?: number;
  };
  cwd: string;
  transcript_path?: string;  // Path to conversation JSONL
}

interface TranscriptIntent {
  layers: string[];
  target: string | null;
  source: string;
}

/**
 * Analyze recent transcript messages to infer intent
 */
function analyzeTranscript(transcriptPath: string): TranscriptIntent | null {
  try {
    if (!existsSync(transcriptPath)) return null;

    const content = readFileSync(transcriptPath, 'utf-8');
    const lines = content.trim().split('\n').slice(-20);  // Last 20 messages

    // Combine recent text for analysis
    let recentText = '';
    for (const line of lines) {
      try {
        const msg = JSON.parse(line);
        if (msg.type === 'human' || msg.type === 'assistant') {
          const text = typeof msg.message === 'string'
            ? msg.message
            : JSON.stringify(msg.message);
          recentText += ' ' + text;
        }
      } catch { /* ignore parse errors */ }
    }

    recentText = recentText.toLowerCase();

    // Intent detection patterns
    const intentPatterns: Array<{ patterns: RegExp[]; layers: string[]; name: string }> = [
      {
        patterns: [/debug/, /bug/, /fix\s+(the|this|a)?\s*(error|issue|problem)/, /investigate/, /broken/],
        layers: ['ast', 'call_graph', 'cfg'],
        name: 'debugging'
      },
      {
        patterns: [/where\s+does/, /data\s*flow/, /variable/, /track\s+\w+/, /what\s+sets/],
        layers: ['ast', 'dfg'],
        name: 'data-flow'
      },
      {
        patterns: [/complexity/, /how\s+complex/, /refactor/, /simplify/, /control\s+flow/],
        layers: ['ast', 'call_graph', 'cfg'],
        name: 'complexity'
      },
      {
        patterns: [/what\s+depends/, /impact/, /affects/, /slice/],
        layers: ['ast', 'call_graph', 'pdg'],
        name: 'dependencies'
      },
      {
        patterns: [/understand/, /how\s+does.*work/, /explain/],
        layers: ['ast', 'call_graph', 'cfg'],
        name: 'understanding'
      }
    ];

    for (const intent of intentPatterns) {
      if (intent.patterns.some(p => p.test(recentText))) {
        // Try to extract a function/class name from recent text
        const funcMatch = recentText.match(/(?:function|method|def|class)\s+(\w+)/);
        const target = funcMatch ? funcMatch[1] : null;

        return {
          layers: intent.layers,
          target,
          source: `transcript:${intent.name}`
        };
      }
    }

    return null;
  } catch {
    return null;
  }
}

interface HookOutput {
  hookSpecificOutput?: {
    hookEventName: string;
    permissionDecision: 'allow' | 'deny' | 'ask';
    permissionDecisionReason?: string;
  };
}

// Code file extensions that should use TLDR
const CODE_EXTENSIONS = new Set([
  '.py', '.ts', '.tsx', '.js', '.jsx',
  '.go', '.rs',
]);

// Files that should always be allowed (bypass TLDR)
const ALLOWED_PATTERNS = [
  /\.json$/, /\.yaml$/, /\.yml$/, /\.toml$/, /\.md$/, /\.txt$/,
  /\.env/, /\.gitignore$/, /Makefile$/, /Dockerfile$/,
  /requirements\.txt$/, /package\.json$/, /tsconfig\.json$/, /pyproject\.toml$/,
  // Allow test files (need full context for implementation)
  /test_.*\.py$/, /.*_test\.py$/, /.*\.test\.(ts|js)$/, /.*\.spec\.(ts|js)$/,
  // Allow hooks/skills (we edit these)
  /\.claude\/hooks\//, /\.claude\/skills\//,
  /init-db\.sql$/, /migrations\//,
];

const ALLOWED_DIRS = ['/tmp/', 'node_modules/', '.venv/', '__pycache__/'];

function isCodeFile(filePath: string): boolean {
  return CODE_EXTENSIONS.has(extname(filePath));
}

function isAllowedFile(filePath: string): boolean {
  for (const pattern of ALLOWED_PATTERNS) {
    if (pattern.test(filePath)) return true;
  }
  for (const dir of ALLOWED_DIRS) {
    if (filePath.includes(dir)) return true;
  }
  return false;
}

function detectLanguage(filePath: string): string {
  const ext = extname(filePath);
  const langMap: Record<string, string> = {
    '.py': 'python', '.ts': 'typescript', '.tsx': 'typescript',
    '.js': 'javascript', '.jsx': 'javascript',
    '.go': 'go', '.rs': 'rust',
  };
  return langMap[ext] || 'python';
}

function getTldrContext(
  filePath: string,
  language: string,
  layers: string[] = ['ast', 'call_graph'],
  target: string | null = null,
  sessionId: string | null = null
): string | null {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const fileName = basename(filePath);
  const results: string[] = [];

  try {
    // Header
    results.push(`# ${fileName}`);
    results.push(`Language: ${language}`);
    results.push('');

    // L1/L2: Extract file info (AST + Call Graph) using daemon
    // Pass session ID for token tracking (P7)
    if (layers.includes('ast') || layers.includes('call_graph')) {
      const extractResp = queryDaemonSync(
        { cmd: 'extract', file: filePath, session: sessionId || undefined },
        projectDir
      );

      if (extractResp.status === 'ok' && extractResp.result) {
        const info = extractResp.result;

        // Functions
        if (info.functions && info.functions.length > 0) {
          results.push('## Functions');
          for (const fn of info.functions) {
            const params = fn.params ? fn.params.join(', ') : '';
            const ret = fn.return_type ? ` -> ${fn.return_type}` : '';
            results.push(`  ${fn.name}(${params})${ret}  [line ${fn.line_number || fn.line}]`);
            if (fn.docstring) {
              const doc = fn.docstring.substring(0, 100).replace(/\n/g, ' ');
              results.push(`    # ${doc}`);
            }
          }
        }

        // Classes
        if (info.classes && info.classes.length > 0) {
          results.push('');
          results.push('## Classes');
          for (const cls of info.classes) {
            results.push(`  class ${cls.name}  [line ${cls.line_number || cls.line}]`);
            if (cls.methods) {
              for (const m of cls.methods.slice(0, 10)) {
                results.push(`    .${m.name}()`);
              }
            }
          }
        }

        // Call Graph
        if (layers.includes('call_graph') && info.call_graph && info.call_graph.calls) {
          results.push('');
          results.push('## Call Graph');
          const entries = Object.entries(info.call_graph.calls).slice(0, 15);
          for (const [caller, callees] of entries) {
            results.push(`  ${caller} -> ${callees}`);
          }
        }
      }
    }

    // L3: CFG (Control Flow Graph)
    if (layers.includes('cfg')) {
      const funcName = target || 'main';
      const cfgResp = queryDaemonSync(
        { cmd: 'cfg', file: filePath, function: funcName, language },
        projectDir
      );

      if (cfgResp.status === 'ok' && cfgResp.result) {
        const cfg = cfgResp.result;
        results.push('');
        results.push(`## CFG: ${funcName}`);
        results.push(`  Blocks: ${cfg.num_blocks || 'N/A'}, Cyclomatic: ${cfg.cyclomatic_complexity || 'N/A'}`);
        if (cfg.blocks && Array.isArray(cfg.blocks)) {
          for (const b of cfg.blocks.slice(0, 8)) {
            results.push(`    Block ${b.id}: lines ${b.start_line}-${b.end_line} (${b.block_type})`);
          }
        }
      }
    }

    // L4: DFG (Data Flow Graph)
    if (layers.includes('dfg')) {
      const funcName = target || 'main';
      const dfgResp = queryDaemonSync(
        { cmd: 'dfg', file: filePath, function: funcName, language },
        projectDir
      );

      if (dfgResp.status === 'ok' && dfgResp.result) {
        const dfg = dfgResp.result;
        results.push('');
        results.push(`## DFG: ${funcName}`);
        if (dfg.definitions && dfg.definitions.length > 0) {
          results.push('  Definitions:');
          for (const d of dfg.definitions.slice(0, 10)) {
            results.push(`    ${d.var_name} @ line ${d.line}`);
          }
        }
        if (dfg.uses && dfg.uses.length > 0) {
          results.push('  Uses:');
          for (const u of dfg.uses.slice(0, 8)) {
            results.push(`    ${u.var_name} @ line ${u.line}`);
          }
        }
      }
    }

    // L5: PDG (Program Dependency Graph) via slice
    if (layers.includes('pdg')) {
      const funcName = target || 'main';
      const sliceResp = queryDaemonSync(
        { cmd: 'slice', file: filePath, function: funcName, line: 10, direction: 'backward' },
        projectDir
      );

      if (sliceResp.status === 'ok' && sliceResp.result) {
        const slice = sliceResp.result;
        results.push('');
        results.push(`## PDG: ${funcName}`);
        if (slice.lines && slice.lines.length > 0) {
          results.push(`  Slice lines: ${slice.lines.length}`);
        }
        if (slice.variables && slice.variables.length > 0) {
          results.push(`  Variables: ${slice.variables.join(', ')}`);
        }
      }
    }

    return results.length > 3 ? results.join('\n') : null;  // > 3 means we have more than just header
  } catch {
    return null;
  }
}

function readStdin(): string {
  return readFileSync(0, 'utf-8');
}

async function main() {
  const input: HookInput = JSON.parse(readStdin());

  if (input.tool_name !== 'Read') {
    console.log('{}');
    return;
  }

  const filePath = input.tool_input.file_path || '';

  // Allow non-code files
  if (!isCodeFile(filePath)) {
    console.log('{}');
    return;
  }

  // Allow explicitly permitted files
  if (isAllowedFile(filePath)) {
    console.log('{}');
    return;
  }

  // If requesting specific lines (offset/limit), allow - they know what they want
  if (input.tool_input.offset || (input.tool_input.limit && input.tool_input.limit < 100)) {
    console.log('{}');
    return;
  }

  // Small files: TLDR overhead not worth it, just read directly
  try {
    const stats = statSync(filePath);
    if (stats.size < 3000) {  // ~100 lines
      console.log('{}');
      return;
    }
  } catch {
    // File doesn't exist or can't stat, let Read handle the error
    console.log('{}');
    return;
  }

  // Get TLDR context instead of raw file
  const language = detectLanguage(filePath);

  // Try to detect intent from multiple sources (in priority order)
  let layers = ['ast', 'call_graph'];  // Default layers
  let target: string | null = null;
  let contextSource = 'default';

  // 1. Check for search context from smart-search-router (highest priority)
  const searchContext = getSearchContext(input.session_id);
  if (searchContext) {
    layers = searchContext.suggestedLayers;
    target = searchContext.target;
    contextSource = `${searchContext.targetType}: ${searchContext.target}`;
  }
  // 2. Analyze transcript for intent (fallback when no search context)
  else if (input.transcript_path) {
    const transcriptIntent = analyzeTranscript(input.transcript_path);
    if (transcriptIntent) {
      layers = transcriptIntent.layers;
      target = transcriptIntent.target;
      contextSource = transcriptIntent.source;
    }
  }

  const tldrContext = getTldrContext(filePath, language, layers, target, input.session_id);

  if (!tldrContext) {
    // TLDR failed, allow normal read
    console.log('{}');
    return;
  }

  // Format layer names for display
  const layerNames = layers.map(l => {
    switch(l) {
      case 'ast': return 'L1:AST';
      case 'call_graph': return 'L2:CallGraph';
      case 'cfg': return 'L3:CFG';
      case 'dfg': return 'L4:DFG';
      case 'pdg': return 'L5:PDG';
      default: return l;
    }
  }).join(' + ');

  // Format cross-file usage (L6) if available
  let crossFileSection = '';
  if (searchContext?.callers && searchContext.callers.length > 0) {
    const callerLines = searchContext.callers.slice(0, 10).map(c => {
      // Format: /full/path/file.py:123 → file.py:123
      const parts = c.split('/');
      const fileAndLine = parts[parts.length - 1];
      const dir = parts.length > 2 ? parts[parts.length - 2] : '';
      return `  ${dir ? dir + '/' : ''}${fileAndLine}`;
    });
    crossFileSection = `
## Cross-File Usage (${searchContext.callers.length} refs)
${callerLines.join('\n')}${searchContext.callers.length > 10 ? `\n  ... and ${searchContext.callers.length - 10} more` : ''}
`;
  }

  // Add definition location if different from current file
  let definitionSection = '';
  if (searchContext?.definitionLocation && !searchContext.definitionLocation.includes(basename(filePath))) {
    definitionSection = `\n📍 Defined at: ${searchContext.definitionLocation}\n`;
  }

  // Track hook activity (P8)
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  trackHookActivitySync('tldr-read-enforcer', projectDir, true, {
    reads_intercepted: 1,
    layers_returned: layers.length,
  });

  // BLOCK the read and return TLDR context
  const output: HookOutput = {
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'deny',
      permissionDecisionReason: `📊 TLDR Context (${layerNames}) - 95% token savings:
${searchContext ? `🔗 Context: ${contextSource}` : ''}${definitionSection}

${tldrContext}${crossFileSection}
---
To read specific lines, use: Read with offset/limit
To read full file anyway, use: Read ${basename(filePath)} (test files bypass this)`,
    }
  };

  console.log(JSON.stringify(output));
}

main().catch((err) => {
  console.error(`TLDR enforcer error: ${err.message}`);
  console.log('{}');
});
