// src/skill-router.ts
import { existsSync, readFileSync } from "fs";
import { join } from "path";

// src/shared/skill-router-types.ts
var CircularDependencyError = class extends Error {
  constructor(cyclePath) {
    super(`Circular dependency detected: ${cyclePath.join(" -> ")}`);
    this.cyclePath = cyclePath;
    this.name = "CircularDependencyError";
  }
};

// src/shared/memory-client.ts
import { spawnSync } from "child_process";
var MemoryClient = class {
  sessionId;
  agentId;
  timeoutMs;
  projectDir;
  constructor(options = {}) {
    this.sessionId = options.sessionId || "default";
    this.agentId = options.agentId || null;
    this.timeoutMs = options.timeoutMs || 5e3;
    this.projectDir = options.projectDir || process.env.CLAUDE_PROJECT_DIR || process.cwd();
  }
  /**
   * Search for similar content in memory.
   *
   * Uses the Python memory service's search functionality.
   * Returns empty array on any error (graceful fallback).
   *
   * @param query - Natural language search query
   * @param limit - Maximum number of results (default: 5)
   * @returns Array of matching results sorted by relevance
   */
  searchSimilar(query, limit = 5) {
    if (!query || !query.trim()) {
      return [];
    }
    const pythonScript = this.buildSearchScript();
    const args = [query, String(limit), this.sessionId];
    if (this.agentId) {
      args.push(this.agentId);
    }
    const result = this.runPython(pythonScript, args);
    if (!result.success) {
      if (process.env.DEBUG) {
        console.error("Memory search failed:", result.stderr);
      }
      return [];
    }
    try {
      const parsed = JSON.parse(result.stdout);
      if (!Array.isArray(parsed)) {
        return [];
      }
      return parsed.map(this.normalizeResult);
    } catch {
      return [];
    }
  }
  /**
   * Store content in memory.
   *
   * @param content - The content to store
   * @param metadata - Optional metadata to attach
   * @returns Memory ID if successful, null on failure
   */
  store(content, metadata = {}) {
    if (!content || !content.trim()) {
      return null;
    }
    const pythonScript = this.buildStoreScript();
    const args = [
      content,
      JSON.stringify(metadata),
      this.sessionId
    ];
    if (this.agentId) {
      args.push(this.agentId);
    }
    const result = this.runPython(pythonScript, args);
    if (!result.success) {
      if (process.env.DEBUG) {
        console.error("Memory store failed:", result.stderr);
      }
      return null;
    }
    try {
      const parsed = JSON.parse(result.stdout);
      return parsed.id || null;
    } catch {
      return null;
    }
  }
  /**
   * Check if memory service is available.
   *
   * @returns true if memory service is reachable
   */
  isAvailable() {
    const pythonScript = `
import json
import sys
try:
    from scripts.core.db.memory_factory import get_default_backend
    backend = get_default_backend()
    print(json.dumps({"available": True, "backend": backend}))
except Exception as e:
    print(json.dumps({"available": False, "error": str(e)}))
`;
    const result = this.runPython(pythonScript, []);
    if (!result.success) {
      return false;
    }
    try {
      const parsed = JSON.parse(result.stdout);
      return parsed.available === true;
    } catch {
      return false;
    }
  }
  /**
   * Build Python script for memory search.
   */
  buildSearchScript() {
    return `
import json
import sys
import asyncio
import os

# Add project to path for imports
project_dir = os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
sys.path.insert(0, project_dir)

async def search():
    query = sys.argv[1]
    limit = int(sys.argv[2])
    session_id = sys.argv[3]
    agent_id = sys.argv[4] if len(sys.argv) > 4 else None

    try:
        from scripts.core.db.memory_factory import create_default_memory_service
        memory = create_default_memory_service(session_id)

        await memory.connect()

        # Try vector search first, fall back to text search
        results = await memory.search(query, limit=limit)

        await memory.close()

        # Convert to JSON-safe format with normalized field names
        safe_results = []
        for r in results:
            safe_results.append({
                "content": r.get("content", ""),
                # Use similarity if available, otherwise rank (BM25)
                "similarity": float(r.get("similarity", r.get("rank", 0.0))),
                "metadata": r.get("metadata", {})
            })

        print(json.dumps(safe_results))
    except Exception as e:
        # Return empty array on error - graceful fallback
        print(json.dumps([]))
        sys.exit(0)  # Exit 0 to avoid breaking the hook

asyncio.run(search())
`;
  }
  /**
   * Build Python script for memory store.
   */
  buildStoreScript() {
    return `
import json
import sys
import asyncio
import os

# Add project to path for imports
project_dir = os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
sys.path.insert(0, project_dir)

async def store():
    content = sys.argv[1]
    metadata = json.loads(sys.argv[2])
    session_id = sys.argv[3]
    agent_id = sys.argv[4] if len(sys.argv) > 4 else None

    try:
        from scripts.core.db.memory_factory import create_default_memory_service
        memory = create_default_memory_service(session_id)

        await memory.connect()

        memory_id = await memory.store(content, metadata=metadata)

        await memory.close()

        print(json.dumps({"id": memory_id}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

asyncio.run(store())
`;
  }
  /**
   * Execute Python script via subprocess.
   */
  runPython(script, args) {
    try {
      const result = spawnSync("python3", ["-c", script, ...args], {
        encoding: "utf-8",
        maxBuffer: 1024 * 1024,
        timeout: this.timeoutMs,
        cwd: this.projectDir,
        env: {
          ...process.env,
          CLAUDE_PROJECT_DIR: this.projectDir
        }
      });
      return {
        success: result.status === 0,
        stdout: result.stdout?.trim() || "",
        stderr: result.stderr || ""
      };
    } catch (err) {
      return {
        success: false,
        stdout: "",
        stderr: String(err)
      };
    }
  }
  /**
   * Normalize a search result to the standard interface.
   */
  normalizeResult(raw) {
    return {
      content: String(raw.content || ""),
      similarity: typeof raw.similarity === "number" ? raw.similarity : 0,
      metadata: raw.metadata || {}
    };
  }
};
function searchMemory(query, limit = 5, options = {}) {
  const client = new MemoryClient(options);
  return client.searchSimilar(query, limit);
}
function isMemoryAvailable(options = {}) {
  const client = new MemoryClient(options);
  return client.isAvailable();
}

// src/shared/task-detector.ts
var IMPLEMENTATION_INDICATORS = [
  { pattern: /\bimplement\b/i, keyword: "implement", type: "implementation", weight: 0.9 },
  { pattern: /\bbuild\b/i, keyword: "build", type: "implementation", weight: 0.9 },
  { pattern: /\bcreate\b/i, keyword: "create", type: "implementation", weight: 0.8 },
  { pattern: /\badd\s+(a\s+)?feature/i, keyword: "add feature", type: "implementation", weight: 0.85 },
  { pattern: /\bwrite\s+(a\s+)?(function|class|method|component|module)/i, keyword: "write", type: "implementation", weight: 0.85 },
  { pattern: /\bdevelop\b/i, keyword: "develop", type: "implementation", weight: 0.8 },
  { pattern: /\bset\s*up\b/i, keyword: "set up", type: "implementation", weight: 0.7 },
  { pattern: /\bconfigure\b/i, keyword: "configure", type: "implementation", weight: 0.7 },
  { pattern: /\brefactor\b/i, keyword: "refactor", type: "implementation", weight: 0.8 },
  { pattern: /\bmigrate\b/i, keyword: "migrate", type: "implementation", weight: 0.75 }
];
var DEBUG_INDICATORS = [
  { pattern: /\bdebug\b/i, keyword: "debug", type: "debug", weight: 0.9 },
  { pattern: /\bfix\s+(the\s+)?(bug|issue|error|problem)/i, keyword: "fix bug", type: "debug", weight: 0.9 },
  { pattern: /\binvestigate\b/i, keyword: "investigate", type: "debug", weight: 0.85 },
  { pattern: /\btroubleshoot\b/i, keyword: "troubleshoot", type: "debug", weight: 0.85 },
  { pattern: /\bdiagnose\b/i, keyword: "diagnose", type: "debug", weight: 0.8 },
  { pattern: /\bwhy\s+is\s+.*\b(failing|broken|not\s+working)/i, keyword: "why failing", type: "debug", weight: 0.75 },
  { pattern: /\bfix\b/i, keyword: "fix", type: "debug", weight: 0.6 }
];
var RESEARCH_INDICATORS = [
  { pattern: /\bhow\s+do\s+I\b/i, keyword: "how do I", type: "research", weight: 0.85 },
  { pattern: /\bfind\s+out\b/i, keyword: "find out", type: "research", weight: 0.8 },
  { pattern: /\bresearch\b/i, keyword: "research", type: "research", weight: 0.85 },
  { pattern: /\blook\s+into\b/i, keyword: "look into", type: "research", weight: 0.8 },
  { pattern: /\bexplore\s+(the\s+)?(options|possibilities|approaches)/i, keyword: "explore", type: "research", weight: 0.75 },
  { pattern: /\bwhat\s+are\s+(the\s+)?(best\s+practices|options|ways)/i, keyword: "best practices", type: "research", weight: 0.7 },
  { pattern: /\blearn\s+about\b/i, keyword: "learn about", type: "research", weight: 0.7 }
];
var PLANNING_INDICATORS = [
  { pattern: /\bplan\b/i, keyword: "plan", type: "planning", weight: 0.85 },
  { pattern: /\bdesign\b/i, keyword: "design", type: "planning", weight: 0.85 },
  { pattern: /\barchitect\b/i, keyword: "architect", type: "planning", weight: 0.9 },
  { pattern: /\boutline\b/i, keyword: "outline", type: "planning", weight: 0.75 },
  { pattern: /\bstrateg(y|ize)\b/i, keyword: "strategy", type: "planning", weight: 0.8 },
  { pattern: /\bpropose\b/i, keyword: "propose", type: "planning", weight: 0.7 },
  { pattern: /\bstructure\b/i, keyword: "structure", type: "planning", weight: 0.65 }
];
var CONVERSATIONAL_PATTERNS = [
  /\bwhat\s+is\b/i,
  /\bexplain\b/i,
  /\bshow\s+me\b/i,
  /\btell\s+me\s+about\b/i,
  /\bdescribe\b/i,
  /\bcan\s+you\s+explain\b/i,
  /\bhelp\s+me\s+understand\b/i,
  /\bwhat\s+does\b/i,
  /\bhow\s+does\b/i,
  /\bwhy\s+does\b/i,
  /\bwhat's\s+the\s+difference\b/i,
  /\bhello\b/i,
  /\bhi\b/i,
  /\bthanks?\b/i,
  /\bthank\s+you\b/i,
  /\bgreat\b/i,
  /\bnice\b/i,
  /\bgood\s+job\b/i,
  /\bwhat\s+happened\b/i
];
var ALL_TASK_INDICATORS = [
  ...IMPLEMENTATION_INDICATORS,
  ...DEBUG_INDICATORS,
  ...RESEARCH_INDICATORS,
  ...PLANNING_INDICATORS
];
function detectTask(prompt) {
  if (!prompt?.trim()) {
    return {
      isTask: false,
      confidence: 0,
      triggers: []
    };
  }
  const promptLower = prompt.toLowerCase();
  const conversationalMatches = CONVERSATIONAL_PATTERNS.filter((p) => p.test(promptLower));
  const matches = [];
  for (const indicator of ALL_TASK_INDICATORS) {
    if (indicator.pattern.test(promptLower)) {
      matches.push({ indicator, keyword: indicator.keyword });
    }
  }
  if (matches.length === 0) {
    return {
      isTask: false,
      confidence: 0,
      triggers: []
    };
  }
  let totalWeight = 0;
  for (const match of matches) {
    totalWeight += match.indicator.weight;
  }
  let confidence = totalWeight / matches.length;
  const uniqueTypes = new Set(matches.map((m) => m.indicator.type));
  if (uniqueTypes.size > 1) {
    confidence += 0.1;
  }
  if (matches.length > 2) {
    confidence += Math.min(0.05 * (matches.length - 2), 0.15);
  }
  if (conversationalMatches.length > 0) {
    confidence -= 0.3 * conversationalMatches.length;
  }
  if (confidence < 0.4) {
    return {
      isTask: false,
      confidence: Math.max(0, confidence),
      triggers: []
    };
  }
  confidence = Math.min(1, Math.max(0, confidence));
  const sortedMatches = [...matches].sort(
    (a, b) => b.indicator.weight - a.indicator.weight
  );
  const primaryType = sortedMatches[0].indicator.type;
  const triggers = [...new Set(matches.map((m) => m.keyword))];
  return {
    isTask: true,
    taskType: primaryType,
    confidence,
    triggers
  };
}

// src/skill-router.ts
var PRIORITY_VALUES = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1
};
var MEMORY_SIMILARITY_THRESHOLD = 0.7;
var cachedSkillRules = null;
function topologicalSort(skillName, rules) {
  const visited = /* @__PURE__ */ new Set();
  const result = [];
  const inProgress = /* @__PURE__ */ new Set();
  function visit(name, path = []) {
    if (inProgress.has(name)) {
      throw new CircularDependencyError([...path, name]);
    }
    if (visited.has(name)) {
      return;
    }
    inProgress.add(name);
    const rule = rules.skills?.[name];
    const deps = [
      ...rule?.prerequisites?.require || [],
      ...rule?.prerequisites?.suggest || []
    ];
    for (const dep of deps) {
      visit(dep, [...path, name]);
    }
    inProgress.delete(name);
    visited.add(name);
    result.push(name);
  }
  visit(skillName);
  return result;
}
function detectCircularDependency(skillName, rules, visited = /* @__PURE__ */ new Set(), stack = /* @__PURE__ */ new Set(), path = []) {
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
  const deps = [
    ...rule?.prerequisites?.require || [],
    ...rule?.prerequisites?.suggest || []
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
function resolvePrerequisites(skillName, rules) {
  const rule = rules.skills?.[skillName];
  if (!rule?.prerequisites) {
    return { suggest: [], require: [], loadOrder: [skillName] };
  }
  const cycle = detectCircularDependency(skillName, rules);
  if (cycle) {
    throw new CircularDependencyError(cycle);
  }
  const loadOrder = topologicalSort(skillName, rules);
  return {
    suggest: rule.prerequisites.suggest || [],
    require: rule.prerequisites.require || [],
    loadOrder
  };
}
function resolveCoActivation(skillName, rules) {
  const rule = rules.skills?.[skillName];
  if (!rule?.coActivate) {
    return { peers: [], mode: "any" };
  }
  const peers = rule.coActivate.filter((peer) => peer !== skillName);
  for (const peer of peers) {
    if (!rules.skills?.[peer]) {
      console.warn(`Co-activation peer "${peer}" not found in skill rules`);
    }
  }
  return {
    peers,
    mode: rule.coActivateMode || "any"
  };
}
function getLoadingMode(skillName, rules) {
  const rule = rules.skills?.[skillName];
  const loading = rule?.loading;
  if (!loading) {
    return "lazy";
  }
  if (loading === "lazy" || loading === "eager" || loading === "eager-prerequisites") {
    return loading;
  }
  console.warn(`Invalid loading mode "${loading}" for skill "${skillName}", defaulting to lazy`);
  return "lazy";
}
function buildEnhancedLookupResult(match, rules) {
  const projectDir = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
  const result = {
    found: true,
    skillName: match.skillName,
    skillPath: join(projectDir, ".claude", "skills", match.skillName, "SKILL.md"),
    confidence: match.priorityValue / 4,
    source: match.source
  };
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
  result.coActivation = resolveCoActivation(match.skillName, rules);
  result.loading = getLoadingMode(match.skillName, rules);
  return result;
}
async function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.on("data", (chunk) => data += chunk);
    process.stdin.on("end", () => resolve(data));
  });
}
function loadSkillRules() {
  if (cachedSkillRules !== null) {
    return cachedSkillRules;
  }
  const projectDir = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
  const possiblePaths = [
    join(projectDir, ".claude", "skills", "skill-rules.json"),
    join(process.env.HOME ?? "", ".claude", "skills", "skill-rules.json")
  ];
  for (const rulesPath of possiblePaths) {
    try {
      if (existsSync(rulesPath)) {
        const content = readFileSync(rulesPath, "utf-8");
        cachedSkillRules = JSON.parse(content);
        return cachedSkillRules;
      }
    } catch {
      console.error(`skill-router: Failed to load rules from ${rulesPath}`);
    }
  }
  return null;
}
function matchesKeyword(promptLower, keywords) {
  return keywords.some((kw) => promptLower.includes(kw.toLowerCase()));
}
function matchesIntentPattern(prompt, patterns) {
  for (const pattern of patterns) {
    try {
      if (new RegExp(pattern, "i").test(prompt)) {
        return true;
      }
    } catch {
    }
  }
  return false;
}
function sortMatches(a, b) {
  if (a.priorityValue !== b.priorityValue) {
    return b.priorityValue - a.priorityValue;
  }
  if (a.source === "keyword" && b.source === "intent") {
    return -1;
  }
  if (a.source === "intent" && b.source === "keyword") {
    return 1;
  }
  return 0;
}
function buildLookupResult(match) {
  const projectDir = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
  return {
    found: true,
    skillName: match.skillName,
    skillPath: join(projectDir, ".claude", "skills", match.skillName, "SKILL.md"),
    confidence: match.priorityValue / 4,
    source: match.source
  };
}
function matchSkillByKeyword(prompt, rules) {
  const promptLower = prompt.toLowerCase();
  const matches = [];
  const allSkills = { ...rules.skills, ...rules.agents ?? {} };
  for (const [skillName, rule] of Object.entries(allSkills)) {
    const triggers = rule.promptTriggers;
    if (!triggers) continue;
    const priorityValue = PRIORITY_VALUES[rule.priority ?? "low"] ?? 1;
    if (triggers.keywords && matchesKeyword(promptLower, triggers.keywords)) {
      matches.push({ skillName, source: "keyword", priorityValue });
      continue;
    }
    if (triggers.intentPatterns && matchesIntentPattern(prompt, triggers.intentPatterns)) {
      matches.push({ skillName, source: "intent", priorityValue });
    }
  }
  if (matches.length === 0) {
    return { found: false, confidence: 0 };
  }
  matches.sort(sortMatches);
  return buildLookupResult(matches[0]);
}
function lookupSkillInMemory(prompt) {
  if (!isMemoryAvailable()) {
    return { found: false, confidence: 0 };
  }
  const results = searchMemory(prompt, 3);
  const validResults = results.filter((r) => r.similarity >= MEMORY_SIMILARITY_THRESHOLD);
  if (validResults.length === 0) {
    return { found: false, confidence: 0 };
  }
  const skillResult = validResults.find(
    (r) => r.metadata?.type === "skill" || r.metadata?.skillName !== void 0
  );
  if (skillResult?.metadata?.skillName) {
    const projectDir = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
    const skillName = String(skillResult.metadata.skillName);
    return {
      found: true,
      skillName,
      skillPath: join(projectDir, ".claude", "skills", skillName, "SKILL.md"),
      confidence: skillResult.similarity,
      source: "memory"
    };
  }
  const topResult = validResults[0];
  return {
    found: true,
    skillName: void 0,
    confidence: topResult.similarity,
    source: "memory"
  };
}
async function lookupSkill(prompt) {
  const rules = loadSkillRules();
  if (!rules) {
    const memoryResult2 = lookupSkillInMemory(prompt);
    if (memoryResult2.found) {
      return memoryResult2;
    }
    return {
      found: false,
      confidence: 0
    };
  }
  const keywordResult = matchSkillByKeyword(prompt, rules);
  if (keywordResult.found) {
    return keywordResult;
  }
  const memoryResult = lookupSkillInMemory(prompt);
  if (memoryResult.found) {
    return memoryResult;
  }
  return { found: false, confidence: 0 };
}
async function main() {
  const rawInput = await readStdin();
  let input;
  try {
    input = JSON.parse(rawInput);
  } catch {
    console.error("skill-router: Failed to parse input JSON");
    input = {};
  }
  const prompt = input.prompt ?? "";
  const lookupResult = await lookupSkill(prompt);
  const output = {
    result: "continue"
  };
  if (lookupResult.found && lookupResult.skillName) {
    const source = lookupResult.source ?? "unknown";
    output.message = `Skill "${lookupResult.skillName}" matches this prompt (source: ${source}).`;
  } else if (lookupResult.found && lookupResult.source === "memory") {
    output.message = `Found relevant context in memory (confidence: ${lookupResult.confidence.toFixed(2)}).`;
  } else {
    const taskResult = detectTask(prompt);
    if (taskResult.isTask) {
      const taskTypeMsg = taskResult.taskType ? ` (${taskResult.taskType})` : "";
      const triggersMsg = taskResult.triggers.length > 0 ? ` Triggers: ${taskResult.triggers.join(", ")}.` : "";
      output.message = `Novel task detected${taskTypeMsg} with confidence ${taskResult.confidence.toFixed(2)}.${triggersMsg} No existing skill matches. JIT skill generation available in future phases.`;
    }
  }
  console.log(JSON.stringify(output));
}
main().catch((err) => {
  console.error("skill-router error:", err);
  console.log(JSON.stringify({ result: "continue" }));
  process.exit(1);
});
export {
  buildEnhancedLookupResult,
  detectCircularDependency,
  getLoadingMode,
  resolveCoActivation,
  resolvePrerequisites,
  topologicalSort
};
