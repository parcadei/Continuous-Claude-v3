#!/usr/bin/env node

// src/agent-validate.ts
import { readFileSync, existsSync, readdirSync } from "fs";
import { join } from "path";
import { homedir } from "os";
var AGENTS_DIR = join(homedir(), ".claude", "agents");
var BUILTIN_AGENTS = /* @__PURE__ */ new Set([
  "Bash",
  "general-purpose",
  "Explore",
  "Plan",
  "statusline-setup",
  "claude-code-guide"
]);
function readStdin() {
  return readFileSync(0, "utf-8");
}
function outputContinue() {
  const output = {
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "allow"
    }
  };
  console.log(JSON.stringify(output));
}
function outputBlock(reason) {
  const output = {
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: reason
    }
  };
  console.log(JSON.stringify(output));
}
function getAvailableAgents() {
  try {
    if (!existsSync(AGENTS_DIR)) return [];
    return readdirSync(AGENTS_DIR).filter((f) => f.endsWith(".md")).map((f) => f.replace(".md", ""));
  } catch {
    return [];
  }
}
function findSimilarAgents(agentType, available) {
  const lower = agentType.toLowerCase();
  return available.filter((a) => {
    const aLower = a.toLowerCase();
    return aLower.includes(lower) || lower.includes(aLower) || levenshteinDistance(lower, aLower) <= 3;
  }).slice(0, 3);
}
function levenshteinDistance(a, b) {
  if (a.length === 0) return b.length;
  if (b.length === 0) return a.length;
  const matrix = [];
  for (let i = 0; i <= b.length; i++) {
    matrix[i] = [i];
  }
  for (let j = 0; j <= a.length; j++) {
    matrix[0][j] = j;
  }
  for (let i = 1; i <= b.length; i++) {
    for (let j = 1; j <= a.length; j++) {
      if (b.charAt(i - 1) === a.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j] + 1
        );
      }
    }
  }
  return matrix[b.length][a.length];
}
async function main() {
  let input;
  try {
    input = JSON.parse(readStdin());
  } catch {
    outputContinue();
    return;
  }
  if (input.tool_name !== "Task") {
    outputContinue();
    return;
  }
  const agentType = input.tool_input?.subagent_type;
  if (!agentType) {
    outputContinue();
    return;
  }
  if (BUILTIN_AGENTS.has(agentType)) {
    outputContinue();
    return;
  }
  const agentFile = join(AGENTS_DIR, `${agentType}.md`);
  if (existsSync(agentFile)) {
    outputContinue();
    return;
  }
  const available = getAvailableAgents();
  const similar = findSimilarAgents(agentType, available);
  let message = `Agent "${agentType}" not found at ${agentFile}`;
  if (similar.length > 0) {
    message += `

Did you mean: ${similar.join(", ")}?`;
  }
  message += `

Available custom agents: ${available.slice(0, 10).join(", ")}${available.length > 10 ? "..." : ""}`;
  outputBlock(message);
}
main().catch(() => {
  outputContinue();
});
