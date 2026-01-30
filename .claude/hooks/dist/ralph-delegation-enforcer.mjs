#!/usr/bin/env node

// src/ralph-delegation-enforcer.ts
import { readFileSync, existsSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
var RALPH_STATE_FILE = join(tmpdir(), "claude-ralph-state.json");
var STATE_TTL = 4 * 60 * 60 * 1e3;
function readRalphState() {
  if (!existsSync(RALPH_STATE_FILE)) {
    return null;
  }
  try {
    const content = readFileSync(RALPH_STATE_FILE, "utf-8");
    const state = JSON.parse(content);
    if (Date.now() - state.activatedAt > STATE_TTL) {
      return null;
    }
    return state;
  } catch {
    return null;
  }
}
function readStdin() {
  return readFileSync(0, "utf-8");
}
function makeBlockOutput(reason) {
  const output = {
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: reason
    }
  };
  console.log(JSON.stringify(output));
}
function makeAllowOutput() {
  console.log(JSON.stringify({}));
}
function isCodeFile(filePath) {
  const codeExtensions = [
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".py",
    ".pyi",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".scala",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".vue",
    ".svelte"
  ];
  return codeExtensions.some((ext) => filePath.endsWith(ext));
}
function isTestCommand(command) {
  const testPatterns = [
    /\bnpm\s+(run\s+)?test/i,
    /\byarn\s+test/i,
    /\bpnpm\s+test/i,
    /\bpytest\b/i,
    /\bgo\s+test\b/i,
    /\bcargo\s+test\b/i,
    /\bjest\b/i,
    /\bvitest\b/i,
    /\bmocha\b/i,
    /\bnpm\s+run\s+lint/i,
    /\bnpm\s+run\s+typecheck/i,
    /\btsc\s+--noEmit/i,
    /\bruff\s+check/i,
    /\bmypy\b/i,
    /\bgolangci-lint/i
  ];
  return testPatterns.some((p) => p.test(command));
}
function isAllowedConfigFile(filePath) {
  const configPatterns = [
    /\.ralph\//,
    /IMPLEMENTATION_PLAN\.md$/,
    /tasks\/.*\.md$/,
    /\.json$/,
    /\.yaml$/,
    /\.yml$/,
    /\.env/,
    /\.gitignore$/,
    /package\.json$/,
    /tsconfig\.json$/,
    /\.md$/
  ];
  return configPatterns.some((p) => p.test(filePath));
}
async function main() {
  try {
    const rawInput = readStdin();
    if (!rawInput.trim()) {
      makeAllowOutput();
      return;
    }
    let input;
    try {
      input = JSON.parse(rawInput);
    } catch {
      makeAllowOutput();
      return;
    }
    const state = readRalphState();
    if (!state || !state.active) {
      makeAllowOutput();
      return;
    }
    if (input.tool_name === "Edit") {
      const filePath = input.tool_input.file_path || "";
      if (isAllowedConfigFile(filePath)) {
        makeAllowOutput();
        return;
      }
      if (isCodeFile(filePath)) {
        makeBlockOutput(`
\u{1F6D1} RALPH DELEGATION ENFORCER

Ralph mode is active. Direct code edits are BLOCKED.

**BLOCKED:** Edit on ${filePath}

**INSTEAD:** Delegate to an agent:
\`\`\`
Task(subagent_type: kraken, prompt: |
  Story: ${state.storyId}
  Task: <what you want to change>
  File: ${filePath}
  ...
)
\`\`\`

Or for quick fixes (<20 lines):
\`\`\`
Task(subagent_type: spark, prompt: ...)
\`\`\`

Ralph orchestrates, agents implement.
`);
        return;
      }
      makeAllowOutput();
      return;
    }
    if (input.tool_name === "Write") {
      const filePath = input.tool_input.file_path || "";
      if (isAllowedConfigFile(filePath)) {
        makeAllowOutput();
        return;
      }
      if (isCodeFile(filePath)) {
        makeBlockOutput(`
\u{1F6D1} RALPH DELEGATION ENFORCER

Ralph mode is active. Direct code writes are BLOCKED.

**BLOCKED:** Write to ${filePath}

**INSTEAD:** Delegate to an agent:
\`\`\`
Task(subagent_type: kraken, prompt: |
  Story: ${state.storyId}
  Task: Create new file ${filePath}
  Requirements: ...
)
\`\`\`

Ralph orchestrates, agents implement.
`);
        return;
      }
      makeAllowOutput();
      return;
    }
    if (input.tool_name === "Bash") {
      const command = input.tool_input.command || "";
      if (isTestCommand(command)) {
        makeBlockOutput(`
\u{1F6D1} RALPH DELEGATION ENFORCER

Ralph mode is active. Direct test/lint commands are BLOCKED.

**BLOCKED:** ${command}

**INSTEAD:** Delegate to arbiter:
\`\`\`
Task(subagent_type: arbiter, prompt: |
  Story: ${state.storyId}
  Task: Run tests and verify implementation
  Files: <affected files>
)
\`\`\`

Ralph orchestrates, agents test.
`);
        return;
      }
      makeAllowOutput();
      return;
    }
    makeAllowOutput();
  } catch (err) {
    makeAllowOutput();
  }
}
main();
