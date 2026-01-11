/**
 * PreToolUse Hook: Smart Search Router
 *
 * Routes Grep calls to the most token-efficient tool:
 * 1. AST-grep - structural code queries (most efficient)
 * 2. LEANN - semantic/conceptual queries
 * 3. Grep - literal patterns (fallback)
 *
 * Uses TLDR daemon for fast symbol lookups when available.
 */

import { existsSync, mkdirSync, writeFileSync, readFileSync } from 'fs';
import { execSync } from 'child_process';
import { queryDaemonSync, DaemonResponse } from './daemon-client.js';

interface GrepInput {
  pattern: string;
  path?: string;
  glob?: string;
  type?: string;
  output_mode?: string;
}

interface PreToolUseInput {
  tool_name: string;
  tool_input: GrepInput;
  session_id?: string;
}

type QueryType = 'structural' | 'semantic' | 'literal';

// Search context for TLDR layer routing
interface SearchContext {
  timestamp: number;
  queryType: QueryType;
  pattern: string;
  target: string | null;
  targetType: 'function' | 'class' | 'variable' | 'import' | 'decorator' | 'unknown';
  suggestedLayers: string[];
  definitionLocation?: string;  // Where the symbol is defined
  callers?: string[];           // Cross-file: where the symbol is called/used
}

const CONTEXT_DIR = '/tmp/claude-search-context';

function storeSearchContext(sessionId: string, context: SearchContext): void {
  try {
    if (!existsSync(CONTEXT_DIR)) {
      mkdirSync(CONTEXT_DIR, { recursive: true });
    }
    writeFileSync(
      `${CONTEXT_DIR}/${sessionId}.json`,
      JSON.stringify(context, null, 2)
    );
  } catch {
    // Ignore errors - context storage is best-effort
  }
}

// TLDR-based symbol lookup via daemon (faster than spawning CLI)
interface TLDRSearchResult {
  file: string;
  line: number;
  content: string;
}

/**
 * Search using TLDR daemon with ripgrep fallback.
 * Uses daemon when available, falls back to ripgrep when indexing/unavailable.
 */
function tldrSearch(pattern: string, projectDir: string = '.'): TLDRSearchResult[] {
  try {
    // Try daemon first
    const response = queryDaemonSync({ cmd: 'search', pattern }, projectDir);

    // If daemon is indexing or unavailable, fall back to ripgrep
    if (response.indexing || response.status === 'unavailable') {
      return ripgrepFallback(pattern, projectDir);
    }

    // Parse successful daemon response
    if (response.status === 'ok' && response.results) {
      return response.results as TLDRSearchResult[];
    }

    return [];
  } catch {
    // Fall back to ripgrep on any error
    return ripgrepFallback(pattern, projectDir);
  }
}

/**
 * Ripgrep fallback for when daemon is unavailable.
 */
function ripgrepFallback(pattern: string, projectDir: string): TLDRSearchResult[] {
  try {
    const escaped = pattern.replace(/"/g, '\\"').replace(/\$/g, '\\$');
    const result = execSync(
      `rg "${escaped}" "${projectDir}" --type py --line-number --max-count 10 2>/dev/null`,
      { encoding: 'utf-8', timeout: 3000 }
    );
    // Parse ripgrep output: file:line:content
    return result.trim().split('\n').filter(l => l).slice(0, 10).map(line => {
      const match = line.match(/^([^:]+):(\d+):(.*)$/);
      if (match) {
        return { file: match[1], line: parseInt(match[2], 10), content: match[3] };
      }
      return { file: line, line: 0, content: '' };
    });
  } catch {
    return [];
  }
}

/**
 * Semantic search using TLDR daemon embeddings.
 * Returns relevant code snippets for natural language queries.
 */
interface SemanticResult {
  file: string;
  function: string;
  score: number;
  snippet?: string;
}

function tldrSemantic(query: string, projectDir: string = '.'): SemanticResult[] {
  try {
    const response = queryDaemonSync({ cmd: 'semantic', query, k: 5 }, projectDir);

    if (response.indexing || response.status === 'unavailable') {
      return [];
    }

    if (response.status === 'ok' && response.results) {
      return response.results as SemanticResult[];
    }

    return [];
  } catch {
    return [];
  }
}

/**
 * Get callers of a function using TLDR daemon.
 */
function tldrImpact(funcName: string, projectDir: string = '.'): string[] {
  try {
    const response = queryDaemonSync({ cmd: 'impact', func: funcName }, projectDir);

    // Skip if indexing or unavailable
    if (response.indexing || response.status === 'unavailable') {
      return [];
    }

    // Parse callers from response
    if (response.status === 'ok' && response.callers) {
      return response.callers.map((c: any) => `${c.file}:${c.line}`);
    }

    return [];
  } catch {
    return [];
  }
}

function lookupCallers(pattern: string): string[] {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || '.';
  return tldrImpact(pattern, projectDir).slice(0, 20);
}

function lookupSymbol(pattern: string): { type: SearchContext['targetType']; location: string } | null {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || '.';

  // Try function first (most common)
  const funcResults = tldrSearch(`def ${pattern}`, projectDir);
  if (funcResults.length > 0) {
    return {
      type: 'function',
      location: `${funcResults[0].file}:${funcResults[0].line}`,
    };
  }

  // Try class
  const classResults = tldrSearch(`class ${pattern}`, projectDir);
  if (classResults.length > 0) {
    return {
      type: 'class',
      location: `${classResults[0].file}:${classResults[0].line}`,
    };
  }

  // Try variable (SCREAMING_CASE assignment)
  if (/^[A-Z][A-Z0-9_]+$/.test(pattern)) {
    const varResults = tldrSearch(`${pattern} =`, projectDir);
    if (varResults.length > 0) {
      return {
        type: 'variable',
        location: `${varResults[0].file}:${varResults[0].line}`,
      };
    }
  }

  return null;
}

// Verb prefixes AND standalone verbs that indicate a function (not a variable)
// Prefixes: get_, set_, is_, has_, etc.
// Standalone: poll, call, exec, sync, etc. (common method names that are single verbs)
const FUNCTION_VERB_PREFIXES = /^(get|set|is|has|do|can|create|update|delete|fetch|load|save|read|write|parse|build|make|init|setup|run|start|stop|handle|process|validate|check|find|search|filter|sort|map|reduce|transform|convert|format|render|display|show|hide|enable|disable|add|remove|insert|append|push|pop|clear|reset|close|open|connect|disconnect|send|receive|emit|on_|async_|_get|_set|_is|_has|_do|_create|_update|_delete|_fetch|_load|_save|_read|_write|_parse|_build|_make|_init|_setup|_run|_handle|_process|_validate|_check|_find|poll|call|exec|execute|invoke|apply|bind|dispatch|trigger|fire|notify|broadcast|publish|subscribe|unsubscribe|listen|watch|observe|register|unregister|mount|unmount|attach|detach|flush|dump|log|warn|error|debug|trace|print|throw|raise|assert|test|mock|stub|spy|wait|sleep|delay|retry|abort|cancel|pause|resume|refresh|reload|rerun|revert|rollback|commit|merge|split|join|clone|copy|move|swap|toggle|flip|increment|decrement|next|prev|first|last|peek|drain|consume|produce|yield|spawn|fork|join|kill|terminate|shutdown|cleanup|destroy|dispose|release|acquire|lock|unlock|enter|exit|begin|end|finalize)(_|$)/;

function extractTarget(pattern: string): { target: string | null; targetType: SearchContext['targetType'] } {
  // 1. Try AST-based symbol index first (100% accurate if indexed)
  const indexed = lookupSymbol(pattern);
  if (indexed) {
    return { target: pattern, targetType: indexed.type };
  }

  // 2. Fall back to heuristics for unindexed patterns
  // Explicit keywords first
  const classMatch = pattern.match(/^class\s+(\w+)/);
  if (classMatch) return { target: classMatch[1], targetType: 'class' };

  const defMatch = pattern.match(/^(?:async\s+)?def\s+(\w+)/);
  if (defMatch) return { target: defMatch[1], targetType: 'function' };

  const functionMatch = pattern.match(/^(?:async\s+)?function\s+(\w+)/);
  if (functionMatch) return { target: functionMatch[1], targetType: 'function' };

  const decoratorMatch = pattern.match(/^@(\w+)/);
  if (decoratorMatch) return { target: decoratorMatch[1], targetType: 'decorator' };

  const importMatch = pattern.match(/^(?:import|from)\s+(\w+)/);
  if (importMatch) return { target: importMatch[1], targetType: 'import' };

  // Self/this attribute access (handle escaped dots too: self\._data)
  const attrMatch = pattern.match(/(?:self|this)(?:\.|\\\.|\\\.\s*)(\w+)/);
  if (attrMatch) {
    const attr = attrMatch[1];
    // Check if it looks like a method (verb prefix) or variable
    if (FUNCTION_VERB_PREFIXES.test(attr)) {
      return { target: attr, targetType: 'function' };
    }
    return { target: attr, targetType: 'variable' };
  }

  // Python dunder handling
  if (/^__[a-z][a-z0-9_]*__$/.test(pattern)) {
    // Module-level dunder VARIABLES (not methods)
    const moduleVars = ['__all__', '__version__', '__author__', '__doc__', '__file__', '__name__', '__package__', '__path__', '__cached__', '__loader__', '__spec__', '__builtins__', '__dict__', '__module__', '__slots__', '__annotations__'];
    if (moduleVars.includes(pattern)) {
      return { target: pattern, targetType: 'variable' };
    }
    // All other dunders are methods (e.g., __init__, __str__, __repr__, __eq__)
    return { target: pattern, targetType: 'function' };
  }

  // SCREAMING_CASE = constant (variable)
  if (/^[A-Z][A-Z0-9_]+$/.test(pattern)) return { target: pattern, targetType: 'variable' };

  // PascalCase = class
  if (/^[A-Z][a-zA-Z0-9]+$/.test(pattern)) return { target: pattern, targetType: 'class' };

  // snake_case with verb prefix = function
  if (/^_?[a-z][a-z0-9_]*$/.test(pattern) && FUNCTION_VERB_PREFIXES.test(pattern)) {
    return { target: pattern, targetType: 'function' };
  }

  // snake_case WITHOUT verb prefix = variable (e.g., _pool, cpu_percent, data_source)
  if (/^_?[a-z][a-z0-9_]*$/.test(pattern)) {
    return { target: pattern, targetType: 'variable' };
  }

  // camelCase with verb prefix = function (e.g., handleClick, useState, fetchData)
  const camelCaseVerbPattern = /^(get|set|is|has|do|can|use|create|update|delete|fetch|load|save|read|write|parse|build|make|init|setup|run|start|stop|handle|process|validate|check|find|search|filter|sort|map|reduce|transform|convert|format|render|display|show|hide|enable|disable|add|remove|insert|append|push|pop|clear|reset|close|open|connect|disconnect|send|receive|emit|on|async|poll|call|exec|execute|invoke|apply|bind|dispatch|trigger|fire|notify|broadcast|publish|subscribe|watch|observe|register|mount|attach|flush|dump|log|warn|error|debug|print|throw|assert|test|mock|wait|sleep|retry|abort|cancel|pause|resume|refresh|reload|revert|commit|merge|clone|copy|move|toggle|spawn|fork|kill|terminate|shutdown|cleanup|destroy|dispose|release|acquire|lock|unlock|enter|exit|begin|end)[A-Z]/;
  if (camelCaseVerbPattern.test(pattern)) {
    return { target: pattern, targetType: 'function' };
  }

  // camelCase WITHOUT verb prefix = variable (e.g., sessionId, userData, configOptions)
  if (/^[a-z][a-zA-Z0-9]*$/.test(pattern) && /[A-Z]/.test(pattern)) {
    return { target: pattern, targetType: 'variable' };
  }

  // Fallback: extract any identifier
  const identMatch = pattern.match(/\b([a-zA-Z_][a-zA-Z0-9_]{2,})\b/);
  if (identMatch) return { target: identMatch[1], targetType: 'unknown' };

  return { target: null, targetType: 'unknown' };
}

function suggestLayers(targetType: SearchContext['targetType'], queryType: QueryType): string[] {
  switch (targetType) {
    case 'function': return ['ast', 'call_graph', 'cfg'];
    case 'class': return ['ast', 'call_graph'];
    case 'variable': return ['ast', 'dfg'];
    case 'import': return ['ast'];
    case 'decorator': return ['ast', 'call_graph'];
    default:
      return queryType === 'semantic' ? ['ast', 'call_graph', 'cfg'] : ['ast', 'call_graph'];
  }
}

interface HookOutput {
  hookSpecificOutput?: {
    hookEventName: string;
    permissionDecision: 'allow' | 'deny' | 'ask';
    permissionDecisionReason?: string;
  };
  systemMessage?: string;
}

function readStdin(): Promise<string> {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => { data += chunk; });
    process.stdin.on('end', () => resolve(data));
  });
}

/**
 * Classifies query type for optimal tool routing
 */
function classifyQuery(pattern: string): QueryType {
  // STRUCTURAL: Code patterns that AST-grep handles best
  const structuralPatterns = [
    /^(class|function|def|async def|const|let|var|interface|type|export)\s+\w+/,
    /^(import|from|require)\s/,
    /^\w+\s*\([^)]*\)/, // function calls
    /^async\s+(function|def)/,
    /\$\w+/, // AST-grep metavariables
    /^@\w+/, // decorators
  ];

  if (structuralPatterns.some(p => p.test(pattern))) {
    return 'structural';
  }

  // LITERAL: Exact identifiers, regex, file paths
  // Regex patterns
  if (pattern.includes('\\') || pattern.includes('[') || /\([^)]*\|/.test(pattern)) {
    return 'literal';
  }

  // Exact identifier patterns (CamelCase, snake_case, SCREAMING_CASE)
  if (/^[A-Z][a-zA-Z0-9]*$/.test(pattern) || /^[a-z_][a-z0-9_]*$/.test(pattern) || /^[A-Z_][A-Z0-9_]*$/.test(pattern)) {
    return 'literal';
  }

  // File paths
  if (pattern.includes('/') || /\.(ts|py|js|go|rs|md)/.test(pattern)) {
    return 'literal';
  }

  // Short patterns (1-2 words, no question words) are likely literal
  const words = pattern.split(/\s+/).filter(w => w.length > 0);
  if (words.length <= 2 && !/^(how|what|where|why|when|find|show|list)/i.test(pattern)) {
    return 'literal';
  }

  // SEMANTIC: Natural language, questions, conceptual
  const semanticPatterns = [
    /^(how|what|where|why|when|which)\s/i,
    /\?$/,
    /^(find|show|list|get|explain)\s+(all|the|every|any)/i,
    /works?$/i,
    /^.*\s+(implementation|architecture|flow|pattern|logic|system)$/i,
  ];

  if (semanticPatterns.some(p => p.test(pattern))) {
    return 'semantic';
  }

  // 3+ words without code indicators → likely semantic
  if (words.length >= 3) {
    return 'semantic';
  }

  return 'literal';
}

// LEANN functions removed - TLDR cross-file covers this use case

function getAstGrepSuggestion(pattern: string, lang: string = 'python'): string {
  // Convert natural language to AST-grep pattern hints
  const suggestions: Record<string, string> = {
    'function': `def $FUNC($$$):`,
    'async': `async def $FUNC($$$):`,
    'class': `class $NAME:`,
    'import': `import $MODULE`,
    'decorator': `@$DECORATOR`,
  };

  for (const [keyword, astPattern] of Object.entries(suggestions)) {
    if (pattern.toLowerCase().includes(keyword)) {
      return astPattern;
    }
  }
  return `$PATTERN($$$)`;
}

async function main() {
  const input: PreToolUseInput = JSON.parse(await readStdin());

  // Only intercept Grep tool
  if (input.tool_name !== 'Grep') {
    console.log('{}');
    return;
  }

  const pattern = input.tool_input.pattern;
  const queryType = classifyQuery(pattern);
  const sessionId = input.session_id || 'default';

  // Extract target and store context for downstream hooks (tldr-read-enforcer)
  const { target, targetType } = extractTarget(pattern);
  const layers = suggestLayers(targetType, queryType);

  // Look up cross-file info from indexes
  const symbolInfo = target ? lookupSymbol(target) : null;
  const callers = target ? lookupCallers(target) : [];

  storeSearchContext(sessionId, {
    timestamp: Date.now(),
    queryType,
    pattern,
    target,
    targetType,
    suggestedLayers: layers,
    definitionLocation: symbolInfo?.location,
    callers: callers.slice(0, 20),  // Limit to 20 callers for token efficiency
  });

  // LITERAL: Run tldr search and provide results via systemMessage
  if (queryType === 'literal') {
    const projectDir = process.env.CLAUDE_PROJECT_DIR || '.';
    const searchResults = tldrSearch(pattern, projectDir);
    
    let systemMsg = `🔍 **TLDR Search Results** for "${pattern}":\n\n`;
    
    if (searchResults.length > 0) {
      systemMsg += searchResults.slice(0, 10).map(r => 
        `  - ${r.file}:${r.line}: ${r.content.trim().substring(0, 80)}`
      ).join('\n');
      systemMsg += '\n\n*Grep proceeding as fallback. Consider using Read tool on specific files above.*';
    } else {
      systemMsg += `No TLDR results found. Grep proceeding normally.`;
    }

    const output: HookOutput = {
      hookSpecificOutput: {
        hookEventName: 'PreToolUse',
        permissionDecision: 'allow',
      },
      systemMessage: systemMsg
    };
    console.log(JSON.stringify(output));
    return;
  }

  // STRUCTURAL: Provide AST-grep suggestion via systemMessage, allow Grep as fallback
  if (queryType === 'structural') {
    const astPattern = getAstGrepSuggestion(pattern);
    const projectDir = process.env.CLAUDE_PROJECT_DIR || '.';
    const searchResults = tldrSearch(pattern, projectDir);
    
    let systemMsg = `🎯 **Structural Query Detected**: "${pattern}"\n\n`;
    systemMsg += `**AST-grep pattern**: \`${astPattern}\`\n\n`;
    
    if (searchResults.length > 0) {
      systemMsg += `**TLDR found**:\n`;
      systemMsg += searchResults.slice(0, 5).map(r => 
        `  - ${r.file}:${r.line}`
      ).join('\n');
      systemMsg += '\n\n';
    }
    
    systemMsg += `*Grep proceeding. For richer context, try: \`tldr search "${target || pattern}" .\`*`;

    const output: HookOutput = {
      hookSpecificOutput: {
        hookEventName: 'PreToolUse',
        permissionDecision: 'allow',
      },
      systemMessage: systemMsg
    };
    console.log(JSON.stringify(output));
    return;
  }

  // SEMANTIC: Run semantic search and provide results via systemMessage
  const projectDir = process.env.CLAUDE_PROJECT_DIR || '.';
  const semanticResults = tldrSemantic(pattern, projectDir);

  let systemMsg: string;
  if (semanticResults.length > 0) {
    const resultsStr = semanticResults.map(r => {
      const loc = `${r.file}:${r.function || 'module'}`;
      const score = r.score ? ` (${(r.score * 100).toFixed(0)}%)` : '';
      return `  - ${loc}${score}`;
    }).join('\n');

    systemMsg = `🧠 **Semantic Search Results** (via TLDR daemon):\n\n${resultsStr}\n\n`;
    systemMsg += `*Grep proceeding as fallback. Consider Read tool on: \`${semanticResults[0].file}\`*`;
  } else {
    systemMsg = `🧠 Semantic query detected: "${pattern}"\n`;
    systemMsg += `*No TLDR semantic results. Grep proceeding. For deep analysis, try: Task(subagent_type="scout")*`;
  }

  const output: HookOutput = {
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'allow',
    },
    systemMessage: systemMsg
  };
  console.log(JSON.stringify(output));
}

main().catch(console.error);
