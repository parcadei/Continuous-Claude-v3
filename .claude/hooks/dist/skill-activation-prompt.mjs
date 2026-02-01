#!/usr/bin/env node

// src/skill-activation-prompt.ts
import { readFileSync as readFileSync2, existsSync as existsSync2 } from "fs";
import { join as join2 } from "path";
import { spawnSync } from "child_process";
import { tmpdir as tmpdir2 } from "os";

// src/shared/resource-reader.ts
import { readFileSync, existsSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
var DEFAULT_RESOURCE_STATE = {
  freeMemMB: 4096,
  activeAgents: 0,
  maxAgents: 10,
  contextPct: 0
};
function getSessionId() {
  return process.env.CLAUDE_SESSION_ID || String(process.ppid || process.pid);
}
function getResourceFilePath(sessionId) {
  return join(tmpdir(), `claude-resources-${sessionId}.json`);
}
function readResourceState() {
  const sessionId = getSessionId();
  const resourceFile = getResourceFilePath(sessionId);
  if (!existsSync(resourceFile)) {
    return null;
  }
  try {
    const content = readFileSync(resourceFile, "utf-8");
    const data = JSON.parse(content);
    return {
      freeMemMB: typeof data.freeMemMB === "number" ? data.freeMemMB : DEFAULT_RESOURCE_STATE.freeMemMB,
      activeAgents: typeof data.activeAgents === "number" ? data.activeAgents : DEFAULT_RESOURCE_STATE.activeAgents,
      maxAgents: typeof data.maxAgents === "number" ? data.maxAgents : DEFAULT_RESOURCE_STATE.maxAgents,
      contextPct: typeof data.contextPct === "number" ? data.contextPct : DEFAULT_RESOURCE_STATE.contextPct
    };
  } catch {
    return null;
  }
}

// src/shared/output.ts
function outputContinue() {
  console.log(JSON.stringify({ result: "continue" }));
}

// src/skill-validation-prompt.ts
var AMBIGUOUS_KEYWORDS = /* @__PURE__ */ new Set([
  "commit",
  "push",
  "pull",
  "merge",
  "branch",
  "checkout",
  "debug",
  "build",
  "implement",
  "plan",
  "research",
  "deploy",
  "release",
  "fix",
  "test",
  "validate",
  "review",
  "analyze",
  "document",
  "refactor",
  "optimize"
]);
var SPECIFIC_TECHNICAL_TERMS = /* @__PURE__ */ new Set([
  "sympy",
  "braintrust",
  "perplexity",
  "agentica",
  "firecrawl",
  "qlty",
  "repoprompt",
  "ast-grep",
  "morph",
  "ragie",
  "lean4",
  "mathlib",
  "z3",
  "shapely",
  "pint"
]);
var TECHNICAL_CONTEXT_INDICATORS = {
  commit: ["git", "changes", "files", "message", "push", "repository", "branch", "staged"],
  push: ["git", "remote", "origin", "branch", "repository", "upstream"],
  pull: ["git", "remote", "origin", "branch", "merge", "rebase", "request"],
  merge: ["git", "branch", "conflict", "pull request", "pr"],
  branch: ["git", "checkout", "create", "switch", "feature"],
  checkout: ["git", "branch", "file", "commit", "HEAD"],
  debug: ["error", "bug", "issue", "logs", "stack trace", "exception", "crash", "breakpoint"],
  build: ["npm", "yarn", "cargo", "make", "compile", "webpack", "bundle", "project"],
  implement: ["code", "feature", "function", "class", "method", "api", "interface", "module"],
  plan: ["implementation", "phase", "architecture", "design", "roadmap", "milestone"],
  research: ["api", "library", "documentation", "docs", "best practices", "pattern", "codebase"],
  deploy: ["server", "production", "staging", "kubernetes", "docker", "cloud", "ci/cd"],
  release: ["version", "tag", "changelog", "npm", "package", "publish"],
  fix: ["bug", "error", "issue", "broken", "failing", "test", "regression"],
  test: ["unit", "integration", "e2e", "coverage", "spec", "jest", "pytest", "vitest"],
  validate: ["input", "schema", "data", "form", "field", "type"],
  review: ["code", "pr", "pull request", "changes", "diff"],
  analyze: ["code", "codebase", "performance", "metrics", "logs"],
  document: ["api", "readme", "docs", "jsdoc", "docstring", "comments"],
  refactor: ["code", "function", "class", "module", "clean up", "simplify"],
  optimize: ["performance", "speed", "memory", "query", "algorithm"]
};
function shouldValidateWithLLM(match) {
  if (match.matchType === "explicit") {
    return false;
  }
  if (match.enforcement === "block") {
    return false;
  }
  if (match.matchType === "intent") {
    return false;
  }
  const termLower = match.matchedTerm.toLowerCase();
  if (SPECIFIC_TECHNICAL_TERMS.has(termLower)) {
    return false;
  }
  if (match.matchType === "keyword" && AMBIGUOUS_KEYWORDS.has(termLower)) {
    const promptLower = match.prompt.toLowerCase();
    const technicalIndicators = TECHNICAL_CONTEXT_INDICATORS[termLower] || [];
    for (const indicator of technicalIndicators) {
      const regex = new RegExp(`\\b${indicator.toLowerCase()}\\b`);
      if (regex.test(promptLower)) {
        return false;
      }
    }
    return true;
  }
  return false;
}

// src/skill-activation-prompt.ts
var PATTERN_AGENT_MAP = {
  "swarm": "research-agent",
  "hierarchical": "kraken",
  "pipeline": "kraken",
  "generator_critic": "review-agent",
  "adversarial": "validate-agent",
  "map_reduce": "kraken",
  "jury": "validate-agent",
  "blackboard": "maestro",
  "circuit_breaker": "kraken",
  "chain_of_responsibility": "maestro",
  "event_driven": "kraken"
};
var WORKFLOW_TRIGGERS = [
  {
    skill: "fix",
    pattern: /\b(fix|debug|broken|failing)\s+(the\s+)?(bug|error|issue|problem)/i,
    antiPattern: /\b(don't|do\s+not|no\s+need\s+to)\s+fix/i,
    confidence: 0.95,
    description: "Bug/error investigation and resolution"
  },
  {
    skill: "build",
    pattern: /\b(build|create|implement)\s+(?:a\s+)?(?:new\s+)?(feature|component|page|module|api|endpoint)/i,
    antiPattern: /\b(don't|do\s+not)\s+(build|create|implement)/i,
    confidence: 0.9,
    description: "Feature development workflow"
  },
  {
    skill: "commit",
    pattern: /\b(commit|save)\s+(these\s+|the\s+|my\s+)?changes/i,
    antiPattern: /\b(don't|do\s+not|before\s+you)\s+commit/i,
    confidence: 0.95,
    description: "Git commit workflow"
  },
  {
    skill: "explore",
    pattern: /\b(explore|understand|navigate|analyze)\s+(the\s+)?(codebase|project|repository|code\s+structure)/i,
    confidence: 0.9,
    description: "Codebase exploration and understanding"
  },
  {
    skill: "ralph",
    pattern: /\b(start|run|launch|use)\s+ralph/i,
    confidence: 0.99,
    description: "Ralph autonomous development workflow"
  },
  {
    skill: "refactor",
    pattern: /\brefactor\s+(the\s+)?(this\s+)?(code|function|class|module|component)/i,
    confidence: 0.9,
    description: "Code refactoring workflow"
  },
  {
    skill: "test",
    pattern: /\b(write|add|create)\s+(unit\s+|integration\s+)?tests?\s+for/i,
    confidence: 0.85,
    description: "Test writing workflow"
  }
];
function checkWorkflowTriggers(prompt) {
  for (const trigger of WORKFLOW_TRIGGERS) {
    if (trigger.pattern.test(prompt)) {
      if (trigger.antiPattern && trigger.antiPattern.test(prompt)) {
        continue;
      }
      return trigger;
    }
  }
  return null;
}
function runPatternInference(prompt, projectDir) {
  const homeDir = process.env.HOME || process.env.USERPROFILE || "";
  if (homeDir) {
    const claudeDir = homeDir.replace(/\\/g, "/") + "/.claude";
    const normalizedProject = projectDir.replace(/\\/g, "/");
    if (normalizedProject === claudeDir || normalizedProject.endsWith("/.claude")) {
      return null;
    }
  }
  try {
    const scriptPath = join2(projectDir, "scripts", "agentica_patterns", "pattern_inference.py");
    if (!existsSync2(scriptPath)) {
      return null;
    }
    const pythonCode = `
import sys
import json
import importlib.util

# Direct import bypassing __init__.py
spec = importlib.util.spec_from_file_location(
    'pattern_inference',
    ${JSON.stringify(scriptPath)}
)
pattern_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pattern_mod)

prompt = ${JSON.stringify(prompt)}
result = pattern_mod.infer_pattern(prompt)
output = result.to_dict()
output['work_breakdown_detailed'] = pattern_mod.generate_work_breakdown(result)
print(json.dumps(output))
`;
    const result = spawnSync("uv", ["run", "python", "-c", pythonCode], {
      encoding: "utf-8",
      timeout: 2e3,
      cwd: projectDir,
      stdio: ["pipe", "pipe", "pipe"],
      killSignal: "SIGKILL"
    });
    if (result.status !== 0 || !result.stdout) {
      return null;
    }
    return JSON.parse(result.stdout.trim());
  } catch (err) {
    return null;
  }
}
function generateAgenticaOutput(inference, prompt) {
  let output = "\n";
  output += "=".repeat(50) + "\n";
  output += "AGENTICA PATTERN INFERENCE\n";
  output += "=".repeat(50) + "\n";
  output += "\n";
  if (inference.confidence >= 0.7) {
    const suggestedAgent = PATTERN_AGENT_MAP[inference.pattern] || "kraken";
    output += "SUGGESTED APPROACH:\n";
    output += `  Agent: ${suggestedAgent}
`;
    output += `  Pattern: ${inference.work_breakdown_detailed}
`;
    const confidencePct = Math.round(inference.confidence * 100);
    output += `  Confidence: ${confidencePct}%
`;
    output += "\n";
    output += "ACTION: Use AskUserQuestion to confirm before spawning:\n";
    output += `  "I'll use ${suggestedAgent} to ${inference.work_breakdown}. Proceed?"
`;
    output += "  Options: [Yes, proceed] [Different approach] [Let me explain more]\n";
    if (inference.alternatives.length > 0) {
      output += `
Alternative approaches available: ${inference.alternatives.join(", ")}
`;
    }
  } else {
    output += "CLARIFICATION NEEDED:\n";
    output += "\n";
    if (inference.clarification_probe) {
      output += `Ask the user: "${inference.clarification_probe}"
`;
    }
    output += "\n";
    output += "Initial analysis suggests: " + inference.work_breakdown + "\n";
    const confidencePct = Math.round(inference.confidence * 100);
    output += `Confidence: ${confidencePct}%
`;
    output += "\n";
    output += "ACTION: Use AskUserQuestion to clarify before proceeding.\n";
  }
  output += "=".repeat(50) + "\n";
  return output;
}
function detectSemanticQuery(prompt) {
  const semanticPatterns = [
    /^(how|what|where|why|when|which)\s/i,
    /\?$/,
    /^(find|show|list|get|explain)\s+(all|the|every|any)/i,
    /^.*\s+(implementation|architecture|flow|pattern|logic|system)$/i
  ];
  const isSemanticQuery = semanticPatterns.some((p) => p.test(prompt.trim()));
  if (!isSemanticQuery) {
    return { isSemanticQuery: false };
  }
  const shortPrompt = prompt.length > 50 ? prompt.slice(0, 50) + "..." : prompt;
  const suggestion = `\u{1F4A1} **Semantic Query Detected**

Your question "${shortPrompt}" may benefit from semantic code search.

**Try:**
\`\`\`bash
tldr semantic search "${prompt.slice(0, 100)}" .
\`\`\`

Or use the /explore skill for guided exploration.
`;
  return { isSemanticQuery: true, suggestion };
}
async function main() {
  try {
    const input = readFileSync2(0, "utf-8");
    let data;
    try {
      data = JSON.parse(input);
    } catch {
      outputContinue();
      process.exit(0);
    }
    if (!data.prompt || typeof data.prompt !== "string") {
      outputContinue();
      process.exit(0);
    }
    const homeDir = process.env.HOME || process.env.USERPROFILE || "";
    if (homeDir) {
      const claudeDir = homeDir.replace(/\\/g, "/") + "/.claude";
      const normalizedCwd = (data.cwd || "").replace(/\\/g, "/");
      if (normalizedCwd === claudeDir || normalizedCwd.endsWith("/.claude")) {
        outputContinue();
        process.exit(0);
      }
    }
    const prompt = data.prompt.toLowerCase();
    const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
    const projectRulesPath = join2(projectDir, ".claude", "skills", "skill-rules.json");
    const globalRulesPath = join2(homeDir, ".claude", "skills", "skill-rules.json");
    let rulesPath = "";
    if (existsSync2(projectRulesPath)) {
      rulesPath = projectRulesPath;
    } else if (existsSync2(globalRulesPath)) {
      rulesPath = globalRulesPath;
    } else {
      outputContinue();
      process.exit(0);
    }
    const rules = JSON.parse(readFileSync2(rulesPath, "utf-8"));
    const workflowTrigger = checkWorkflowTriggers(data.prompt);
    if (workflowTrigger && workflowTrigger.confidence >= 0.9) {
      const confidencePct = Math.round(workflowTrigger.confidence * 100);
      const autoInvokeMessage = `
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u{1F680} WORKFLOW DETECTED: /${workflowTrigger.skill}
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

High-confidence workflow match (${confidencePct}%):
  \u2192 ${workflowTrigger.description}

\u26A0\uFE0F ACTION REQUIRED - INVOKE SKILL FIRST:
Use the Skill tool with: { "skill": "${workflowTrigger.skill}" }

Do NOT skip this step. The skill provides:
- Structured methodology for this task type
- Built-in verification steps
- Proper agent orchestration

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
`;
      console.log(autoInvokeMessage);
      outputContinue();
      process.exit(0);
    }
    const patternInference = runPatternInference(data.prompt, projectDir);
    const semanticQuery = detectSemanticQuery(data.prompt);
    const matchedSkills = [];
    for (const [skillName, config] of Object.entries(rules.skills)) {
      const triggers = config.promptTriggers;
      if (!triggers) {
        continue;
      }
      if (triggers.keywords) {
        const matchedKeyword = triggers.keywords.find(
          (kw) => prompt.includes(kw.toLowerCase())
        );
        if (matchedKeyword) {
          const skillMatchForValidation = {
            skillName,
            matchType: "keyword",
            matchedTerm: matchedKeyword,
            prompt: data.prompt,
            // Use original prompt (not lowercased)
            skillDescription: config.description,
            enforcement: config.enforcement
          };
          const needsValidation = shouldValidateWithLLM(skillMatchForValidation);
          matchedSkills.push({
            name: skillName,
            matchType: "keyword",
            matchedTerm: matchedKeyword,
            config,
            needsValidation
          });
          continue;
        }
      }
      if (triggers.intentPatterns) {
        const intentMatch = triggers.intentPatterns.some((pattern) => {
          try {
            const regex = new RegExp(pattern, "i");
            return regex.test(prompt);
          } catch {
            return false;
          }
        });
        if (intentMatch) {
          matchedSkills.push({
            name: skillName,
            matchType: "intent",
            config,
            needsValidation: false
          });
        }
      }
    }
    const matchedAgents = [];
    if (rules.agents) {
      for (const [agentName, config] of Object.entries(rules.agents)) {
        const triggers = config.promptTriggers;
        if (!triggers) {
          continue;
        }
        if (triggers.keywords) {
          const matchedKeyword = triggers.keywords.find(
            (kw) => prompt.includes(kw.toLowerCase())
          );
          if (matchedKeyword) {
            const skillMatchForValidation = {
              skillName: agentName,
              matchType: "keyword",
              matchedTerm: matchedKeyword,
              prompt: data.prompt,
              skillDescription: config.description,
              enforcement: config.enforcement
            };
            const needsValidation = shouldValidateWithLLM(skillMatchForValidation);
            matchedAgents.push({
              name: agentName,
              matchType: "keyword",
              matchedTerm: matchedKeyword,
              config,
              isAgent: true,
              needsValidation
            });
            continue;
          }
        }
        if (triggers.intentPatterns) {
          const intentMatch = triggers.intentPatterns.some((pattern) => {
            try {
              const regex = new RegExp(pattern, "i");
              return regex.test(prompt);
            } catch {
              return false;
            }
          });
          if (intentMatch) {
            matchedAgents.push({
              name: agentName,
              matchType: "intent",
              config,
              isAgent: true,
              needsValidation: false
            });
          }
        }
      }
    }
    if (matchedSkills.length > 0 || matchedAgents.length > 0 || patternInference || semanticQuery.isSemanticQuery) {
      const skillsNeedingValidation = matchedSkills.filter((s) => s.needsValidation);
      const agentsNeedingValidation = matchedAgents.filter((a) => a.needsValidation);
      const allNeedingValidation = [...skillsNeedingValidation, ...agentsNeedingValidation];
      const confirmedSkills = matchedSkills.filter((s) => !s.needsValidation);
      const confirmedAgents = matchedAgents.filter((a) => !a.needsValidation);
      let output = "";
      if (patternInference) {
        output += generateAgenticaOutput(patternInference, data.prompt);
        output += "\n";
      }
      if (semanticQuery.isSemanticQuery && semanticQuery.suggestion) {
        output += semanticQuery.suggestion;
        output += "\n";
      }
      if (matchedSkills.length > 0 || matchedAgents.length > 0) {
        output += "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n";
        output += "\u{1F3AF} SKILL ACTIVATION CHECK\n";
        output += "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n";
        if (allNeedingValidation.length > 0) {
          output += "\u2753 AMBIGUOUS MATCHES (validate before activating):\n";
          output += "   The following skills matched on keywords that may be used\n";
          output += "   in a non-technical context. Consider if they're needed:\n\n";
          for (const item of allNeedingValidation) {
            const isAgent = item.isAgent ? " [agent]" : "";
            output += `   \u2022 ${item.name}${isAgent}
`;
            output += `     Matched: "${item.matchedTerm}" (keyword match)
`;
            if (item.config.description) {
              output += `     Purpose: ${item.config.description}
`;
            }
            output += `     \u2192 Skip if the user is NOT asking for this functionality
`;
            output += "\n";
          }
          output += "   VALIDATION: Before activating these, ask yourself:\n";
          output += `   "Is the user asking for this skill's capability, or just
`;
          output += '    using the word in everyday language?"\n\n';
        }
        const critical = confirmedSkills.filter((s) => s.config.priority === "critical");
        const high = confirmedSkills.filter((s) => s.config.priority === "high");
        const medium = confirmedSkills.filter((s) => s.config.priority === "medium");
        const low = confirmedSkills.filter((s) => s.config.priority === "low");
        if (critical.length > 0) {
          output += "\u26A0\uFE0F CRITICAL SKILLS (REQUIRED):\n";
          critical.forEach((s) => output += `  \u2192 ${s.name}
`);
          output += "\n";
        }
        if (high.length > 0) {
          output += "\u{1F4DA} RECOMMENDED SKILLS:\n";
          high.forEach((s) => output += `  \u2192 ${s.name}
`);
          output += "\n";
        }
        if (medium.length > 0) {
          output += "\u{1F4A1} SUGGESTED SKILLS:\n";
          medium.forEach((s) => output += `  \u2192 ${s.name}
`);
          output += "\n";
        }
        if (low.length > 0) {
          output += "\u{1F4CC} OPTIONAL SKILLS:\n";
          low.forEach((s) => output += `  \u2192 ${s.name}
`);
          output += "\n";
        }
        if (confirmedAgents.length > 0) {
          output += "\u{1F916} RECOMMENDED AGENTS (token-efficient):\n";
          confirmedAgents.forEach((a) => output += `  \u2192 ${a.name}
`);
          output += "\n";
        }
        if (confirmedSkills.length > 0) {
          output += "ACTION: Use Skill tool BEFORE responding\n";
        }
        if (confirmedAgents.length > 0) {
          output += "ACTION: Use Task tool with agent for exploration\n";
        }
        output += "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n";
        const blockingSkills = matchedSkills.filter((s) => s.config.enforcement === "block");
        if (blockingSkills.length > 0) {
          const blockMessage = output + "\n\u26D4 BLOCKING: You MUST invoke " + blockingSkills.map((s) => s.name).join(", ") + " skill(s) before generating ANY response.";
          console.log(JSON.stringify({
            result: "block",
            reason: blockMessage
          }));
          process.exit(0);
        }
      }
      console.log(output);
    }
    const rawSessionId = data.session_id || process.env.CLAUDE_SESSION_ID || process.env.CLAUDE_PPID || "default";
    const sessionId = rawSessionId.slice(0, 8);
    const contextFile = join2(tmpdir2(), `claude-context-pct-${sessionId}.txt`);
    if (existsSync2(contextFile)) {
      try {
        const pct = parseInt(readFileSync2(contextFile, "utf-8").trim(), 10);
        let contextWarning = "";
        if (pct >= 90) {
          contextWarning = "\n" + "=".repeat(50) + "\n  CONTEXT CRITICAL: " + pct + "%\n  Run /create_handoff NOW before auto-compact!\n" + "=".repeat(50) + "\n";
        } else if (pct >= 80) {
          contextWarning = "\nCONTEXT WARNING: " + pct + "%\nRecommend: /create_handoff then /clear soon\n";
        } else if (pct >= 70) {
          contextWarning = "\nContext at " + pct + "%. Consider handoff when you reach a stopping point.\n";
        }
        if (contextWarning) {
          console.log(contextWarning);
        }
      } catch {
      }
    }
    const resources = readResourceState();
    if (resources && resources.maxAgents > 0) {
      const utilization = resources.activeAgents / resources.maxAgents;
      let resourceWarning = "";
      if (utilization >= 1) {
        resourceWarning = "\n" + "=".repeat(50) + "\nRESOURCE CRITICAL: At limit (" + resources.activeAgents + "/" + resources.maxAgents + " agents)\nDo NOT spawn new agents until existing ones complete.\n" + "=".repeat(50) + "\n";
      } else if (utilization >= 0.8) {
        const remaining = resources.maxAgents - resources.activeAgents;
        resourceWarning = "\nRESOURCE WARNING: Near limit (" + resources.activeAgents + "/" + resources.maxAgents + " agents)\nOnly " + remaining + " agent slot(s) remaining. Limit spawning.\n";
      }
      if (resourceWarning) {
        console.log(resourceWarning);
      }
    }
    outputContinue();
    process.exit(0);
  } catch (err) {
    console.error("Error in skill-activation-prompt hook:", err);
    outputContinue();
    process.exit(1);
  }
}
main().catch((err) => {
  console.error("Uncaught error:", err);
  outputContinue();
  process.exit(1);
});
