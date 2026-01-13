/**
 * Skill Router Hook - Phase 7 Novel Task Detection
 *
 * Entry point for the self-improving skill system.
 * Phase 3 adds keyword and regex pattern matching from skill-rules.json.
 * Phase 6 adds memory lookup when keyword matching fails.
 * Phase 7 adds novel task detection to distinguish tasks from conversation.
 *
 * Future phases will add:
 * - JIT skill generation for novel tasks (Phase 8-12)
 *
 * Plan: thoughts/shared/plans/self-improving-skill-system.md
 */
import { existsSync, readFileSync } from 'fs';
import { join } from 'path';
import {
  CircularDependencyError,
  SkillRulesConfig,
  SkillLookupResult,
  SkillRule,
} from './shared/skill-router-types.js';
import { searchMemory, isMemoryAvailable } from './shared/memory-client.js';
import { detectTask } from './shared/task-detector.js';

/** Priority values for sorting matches (higher = more important) */
const PRIORITY_VALUES: Record<string, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

/** Similarity threshold for memory lookup (per plan: 0.7) */
const MEMORY_SIMILARITY_THRESHOLD = 0.7;

/** Cached skill rules to avoid repeated file reads */
let cachedSkillRules: SkillRulesConfig | null = null;

// =============================================================================
// Prerequisite, Co-activation, and Loading Mode Functions (Phase 9-14)
// =============================================================================

/**
 * Topological sort using depth-first search.
 * Returns skills in dependency order (dependencies first).
 * @throws CircularDependencyError if cycle detected
 */
export function topologicalSort(skillName: string, rules: SkillRulesConfig): string[] {
  const visited = new Set<string>();
  const result: string[] = [];
  const inProgress = new Set<string>();

  function visit(name: string, path: string[] = []): void {
    if (inProgress.has(name)) {
      throw new CircularDependencyError([...path, name]);
    }
    if (visited.has(name)) {
      return;
    }
    inProgress.add(name);
    const rule = rules.skills?.[name];
    const deps: string[] = [
      ...(rule?.prerequisites?.require || []),
      ...(rule?.prerequisites?.suggest || []),
    ];
    for (const dep of deps) {
      visit(dep, [...path, name]);
    }
    inProgress.delete(name);
    visited.add(name);
    result.push(name);
  }

  visit(skillName);
  return result; // Dependencies first, requested skill last
}

/**
 * Detects circular dependencies in prerequisite chain.
 * @returns Array of skill names forming the cycle, or null if no cycle
 */
export function detectCircularDependency(
  skillName: string,
  rules: SkillRulesConfig,
  visited = new Set<string>(),
  stack = new Set<string>(),
  path: string[] = []
): string[] | null {
  if (stack.has(skillName)) {
    return [...path, skillName];
  }
  if (visited.has(skillName)) {
    return null;
  }
  visited.add(skillName);
  stack.add(skillName);
  path.push(skillName);
  const rule = rules.skills?.[skillName];
  const deps: string[] = [
    ...(rule?.prerequisites?.require || []),
    ...(rule?.prerequisites?.suggest || []),
  ];
  for (const dep of deps) {
    const cycle = detectCircularDependency(dep, rules, visited, stack, [...path]);
    if (cycle) {
      return cycle;
    }
  }
  stack.delete(skillName);
  return null;
}

/**
 * Resolve prerequisites for a given skill.
 * @throws CircularDependencyError if cycle detected
 */
export function resolvePrerequisites(
  skillName: string,
  rules: SkillRulesConfig
): { suggest: string[]; require: string[]; loadOrder: string[] } {
  const rule = rules.skills?.[skillName];
  if (!rule?.prerequisites) {
    return { suggest: [], require: [], loadOrder: [skillName] };
  }
  // Check for cycles first
  const cycle = detectCircularDependency(skillName, rules);
  if (cycle) {
    throw new CircularDependencyError(cycle);
  }
  // Get topologically sorted order
  const loadOrder = topologicalSort(skillName, rules);
  return {
    suggest: rule.prerequisites.suggest || [],
    require: rule.prerequisites.require || [],
    loadOrder,
  };
}

/**
 * Resolve co-activation peers for a given skill.
 */
export function resolveCoActivation(
  skillName: string,
  rules: SkillRulesConfig
): { peers: string[]; mode: 'all' | 'any' } {
  const rule = rules.skills?.[skillName];
  if (!rule?.coActivate) {
    return { peers: [], mode: 'any' };
  }
  // Filter out self-references
  const peers = rule.coActivate.filter((peer) => peer !== skillName);
  // Warn about non-existent peers
  for (const peer of peers) {
    if (!rules.skills?.[peer]) {
      console.warn(`Co-activation peer "${peer}" not found in skill rules`);
    }
  }
  return {
    peers,
    mode: rule.coActivateMode || 'any',
  };
}

/**
 * Get the loading mode for a skill.
 */
export function getLoadingMode(skillName: string, rules: SkillRulesConfig): 'lazy' | 'eager' | 'eager-prerequisites' {
  const rule = rules.skills?.[skillName];
  const loading = rule?.loading;
  if (!loading) {
    return 'lazy';
  }
  if (loading === 'lazy' || loading === 'eager' || loading === 'eager-prerequisites') {
    return loading;
  }
  console.warn(`Invalid loading mode "${loading}" for skill "${skillName}", defaulting to lazy`);
  return 'lazy';
}

/**
 * Build an enhanced lookup result with prerequisites, co-activation, and loading mode.
 */
export function buildEnhancedLookupResult(
  match: { skillName: string; source: 'keyword' | 'intent' | 'memory' | 'jit'; priorityValue: number },
  rules: SkillRulesConfig
): SkillLookupResult {
  const projectDir = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
  // Get base result
  const result: SkillLookupResult = {
    found: true,
    skillName: match.skillName,
    skillPath: join(projectDir, '.claude', 'skills', match.skillName, 'SKILL.md'),
    confidence: match.priorityValue / 4,
    source: match.source,
  };
  // Add prerequisites
  try {
    result.prerequisites = resolvePrerequisites(match.skillName, rules);
  } catch (error) {
    if (error instanceof CircularDependencyError) {
      console.error(`Circular dependency in ${match.skillName}: ${error.message}`);
      result.prerequisites = { suggest: [], require: [], loadOrder: [match.skillName] };
    } else {
      throw error;
    }
  }
  // Add co-activation
  result.coActivation = resolveCoActivation(match.skillName, rules);
  // Add loading mode
  result.loading = getLoadingMode(match.skillName, rules);
  return result;
}

// =============================================================================
// Private helper functions (not exported)
// =============================================================================

async function readStdin(): Promise<string> {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.on('data', (chunk) => (data += chunk));
    process.stdin.on('end', () => resolve(data));
  });
}

/**
 * Load skill rules from skill-rules.json.
 *
 * Checks project directory first, then falls back to global ~/.claude/skills.
 *
 * @returns SkillRulesConfig or null if file not found
 */
function loadSkillRules(): SkillRulesConfig | null {
  // Return cached rules if available
  if (cachedSkillRules !== null) {
    return cachedSkillRules;
  }
  const projectDir = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
  const possiblePaths = [
    join(projectDir, '.claude', 'skills', 'skill-rules.json'),
    join(process.env.HOME ?? '', '.claude', 'skills', 'skill-rules.json'),
  ];
  for (const rulesPath of possiblePaths) {
    try {
      if (existsSync(rulesPath)) {
        const content = readFileSync(rulesPath, 'utf-8');
        cachedSkillRules = JSON.parse(content) as SkillRulesConfig;
        return cachedSkillRules;
      }
    } catch {
      // Continue to next path on error
      console.error(`skill-router: Failed to load rules from ${rulesPath}`);
    }
  }
  return null;
}

/**
 * Check if any keyword matches the prompt (case-insensitive).
 */
function matchesKeyword(promptLower: string, keywords: string[]): boolean {
  return keywords.some((kw) => promptLower.includes(kw.toLowerCase()));
}

/**
 * Check if any intent pattern matches the prompt (case-insensitive regex).
 */
function matchesIntentPattern(prompt: string, patterns: string[]): boolean {
  for (const pattern of patterns) {
    try {
      if (new RegExp(pattern, 'i').test(prompt)) {
        return true;
      }
    } catch {
      // Skip invalid regex patterns silently
    }
  }
  return false;
}

/**
 * Sort matches by priority (descending), then prefer keyword over intent.
 */
function sortMatches(
  a: { priorityValue: number; source: string },
  b: { priorityValue: number; source: string }
): number {
  if (a.priorityValue !== b.priorityValue) {
    return b.priorityValue - a.priorityValue;
  }
  if (a.source === 'keyword' && b.source === 'intent') {
    return -1;
  }
  if (a.source === 'intent' && b.source === 'keyword') {
    return 1;
  }
  return 0;
}

/**
 * Build a SkillLookupResult from the best match.
 */
function buildLookupResult(match: { skillName: string; source: 'keyword' | 'intent' | 'memory'; priorityValue: number }): SkillLookupResult {
  const projectDir = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
  return {
    found: true,
    skillName: match.skillName,
    skillPath: join(projectDir, '.claude', 'skills', match.skillName, 'SKILL.md'),
    confidence: match.priorityValue / 4,
    source: match.source,
  };
}

/**
 * Match a prompt against skill keywords and intent patterns.
 *
 * @param prompt - The user's prompt to match
 * @param rules - The skill rules configuration
 * @returns SkillLookupResult indicating if a match was found
 */
function matchSkillByKeyword(prompt: string, rules: SkillRulesConfig): SkillLookupResult {
  const promptLower = prompt.toLowerCase();
  const matches: Array<{ skillName: string; source: 'keyword' | 'intent'; priorityValue: number }> = [];
  const allSkills: Record<string, SkillRule> = { ...rules.skills, ...(rules.agents ?? {}) };
  for (const [skillName, rule] of Object.entries(allSkills)) {
    const triggers = rule.promptTriggers;
    if (!triggers) continue;
    const priorityValue = PRIORITY_VALUES[rule.priority ?? 'low'] ?? 1;
    // Check keywords first
    if (triggers.keywords && matchesKeyword(promptLower, triggers.keywords)) {
      matches.push({ skillName, source: 'keyword', priorityValue });
      continue; // Don't check patterns if keyword matched
    }
    // Check intent patterns
    if (triggers.intentPatterns && matchesIntentPattern(prompt, triggers.intentPatterns)) {
      matches.push({ skillName, source: 'intent', priorityValue });
    }
  }
  if (matches.length === 0) {
    return { found: false, confidence: 0 };
  }
  matches.sort(sortMatches);
  return buildLookupResult(matches[0]);
}

/**
 * Look up a skill in memory based on semantic similarity.
 *
 * Searches memory for past skill executions or stored skill references
 * that match the given prompt. Only returns matches above the similarity
 * threshold (0.7) to avoid false positives.
 *
 * @param prompt - The user's prompt to search for in memory
 * @returns SkillLookupResult indicating if a memory match was found
 */
function lookupSkillInMemory(prompt: string): SkillLookupResult {
  // Check if memory service is available
  if (!isMemoryAvailable()) {
    return { found: false, confidence: 0 };
  }
  // Search memory for similar content
  const results = searchMemory(prompt, 3);
  // Filter results by similarity threshold
  const validResults = results.filter((r) => r.similarity >= MEMORY_SIMILARITY_THRESHOLD);
  if (validResults.length === 0) {
    return { found: false, confidence: 0 };
  }
  // Find results that contain skill references in metadata
  const skillResult = validResults.find(
    (r) => r.metadata?.type === 'skill' || r.metadata?.skillName !== undefined
  );
  if (skillResult?.metadata?.skillName) {
    const projectDir = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
    const skillName = String(skillResult.metadata.skillName);
    return {
      found: true,
      skillName,
      skillPath: join(projectDir, '.claude', 'skills', skillName, 'SKILL.md'),
      confidence: skillResult.similarity,
      source: 'memory',
    };
  }
  // If no skill reference found but high similarity content exists,
  // return the content as a partial match for context
  const topResult = validResults[0];
  return {
    found: true,
    skillName: undefined,
    confidence: topResult.similarity,
    source: 'memory',
  };
}

/**
 * Look up a skill that matches the given prompt.
 *
 * Phase 6: Enhanced lookup flow:
 * 1. Try keyword/intent matching first (fast, high confidence)
 * 2. If not found, try memory lookup (semantic similarity)
 * 3. Return not found (Phase 7+ will add JIT generation)
 *
 * @param prompt - The user's prompt to match against skills
 * @returns SkillLookupResult indicating if a match was found
 */
async function lookupSkill(prompt: string): Promise<SkillLookupResult> {
  // Load skill rules
  const rules = loadSkillRules();
  if (!rules) {
    // If no rules, still try memory lookup
    const memoryResult = lookupSkillInMemory(prompt);
    if (memoryResult.found) {
      return memoryResult;
    }
    return {
      found: false,
      confidence: 0,
    };
  }
  // 1. Try keyword/intent matching first (fast, high confidence)
  const keywordResult = matchSkillByKeyword(prompt, rules);
  if (keywordResult.found) {
    return keywordResult;
  }
  // 2. Try memory lookup (semantic similarity)
  const memoryResult = lookupSkillInMemory(prompt);
  if (memoryResult.found) {
    return memoryResult;
  }
  // 3. Return not found (Phase 7+ will add JIT generation)
  return { found: false, confidence: 0 };
}

// =============================================================================
// Main entry point (not exported - called when running as hook)
// =============================================================================

interface TaskDetectionResult {
  isTask: boolean;
  taskType?: string;
  confidence: number;
  triggers: string[];
}

async function main(): Promise<void> {
  const rawInput = await readStdin();
  // Parse input (gracefully handle malformed JSON)
  let input: { prompt?: string };
  try {
    input = JSON.parse(rawInput);
  } catch {
    // Log to stderr, still return valid output
    console.error('skill-router: Failed to parse input JSON');
    input = {};
  }
  const prompt = input.prompt ?? '';
  // Phase 6: Perform skill lookup (keyword, intent, then memory)
  const lookupResult = await lookupSkill(prompt);
  // Build output based on lookup result
  const output: { result: string; message?: string } = {
    result: 'continue',
  };
  // Add message with skill info when found
  if (lookupResult.found && lookupResult.skillName) {
    const source = lookupResult.source ?? 'unknown';
    output.message = `Skill "${lookupResult.skillName}" matches this prompt (source: ${source}).`;
  } else if (lookupResult.found && lookupResult.source === 'memory') {
    // Memory match without specific skill name (general context match)
    output.message = `Found relevant context in memory (confidence: ${lookupResult.confidence.toFixed(2)}).`;
  } else {
    // Phase 7: No skill or memory match - check if this is a novel task
    const taskResult = detectTask(prompt) as TaskDetectionResult;
    if (taskResult.isTask) {
      // This is a novel task that might benefit from JIT skill generation
      // Phase 8+ will ask clarifying questions and generate a skill
      const taskTypeMsg = taskResult.taskType ? ` (${taskResult.taskType})` : '';
      const triggersMsg = taskResult.triggers.length > 0 ? ` Triggers: ${taskResult.triggers.join(', ')}.` : '';
      output.message = `Novel task detected${taskTypeMsg} with confidence ${taskResult.confidence.toFixed(2)}.${triggersMsg} No existing skill matches. JIT skill generation available in future phases.`;
    }
    // If not a task (conversational), no message needed - just continue
  }
  console.log(JSON.stringify(output));
}

main().catch((err) => {
  console.error('skill-router error:', err);
  // Return valid JSON even on error to avoid breaking the hook chain
  console.log(JSON.stringify({ result: 'continue' }));
  process.exit(1);
});
