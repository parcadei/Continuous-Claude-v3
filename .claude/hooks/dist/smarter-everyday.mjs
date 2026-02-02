#!/usr/bin/env node
var __require = /* @__PURE__ */ ((x) => typeof require !== "undefined" ? require : typeof Proxy !== "undefined" ? new Proxy(x, {
  get: (a, b) => (typeof require !== "undefined" ? require : a)[b]
}) : x)(function(x) {
  if (typeof require !== "undefined") return require.apply(this, arguments);
  throw Error('Dynamic require of "' + x + '" is not supported');
});

// src/smarter-everyday.ts
import * as fs from "fs";
import * as path from "path";
var TEST_COMMANDS = [
  /\b(npm|yarn|pnpm)\s+(run\s+)?test/i,
  /\bpytest\b/i,
  /\bcargo\s+test\b/i,
  /\bgo\s+test\b/i,
  /\bjest\b/i,
  /\bvitest\b/i,
  /\bmocha\b/i,
  /\bmake\s+test\b/i,
  /\bnpm\s+run\s+check/i,
  /\btsc\s+--noEmit/i
];
var SUCCESS_PATTERNS = [
  /\bpassed\b/i,
  /\bpassing\b/i,
  /\b0\s+(failures?|errors?)\b/i,
  /[\u2713\u2714\u221A]/,
  // Check marks
  /All tests passed/i,
  /PASS\s/,
  /Tests:\s+\d+\s+passed/i,
  /OK\s*\(/i
];
var FAILURE_PATTERNS = [
  /\bfailed\b/i,
  /\bfailing\b/i,
  /\berror\b/i,
  /\bexception\b/i,
  /\b[1-9]\d*\s+(failures?|errors?)\b/i,
  /[\u2717\u2718\u00D7]/,
  // X marks
  /FAILED/,
  /Tests:\s+\d+\s+failed/i
];
var VICTORY_TURN_THRESHOLD = 3;
function getStateFilePath(projectDir) {
  return path.join(projectDir, ".claude", "smarter-everyday-state.json");
}
function loadState(stateFile, sessionId) {
  const defaultState = {
    session_id: sessionId,
    state: "IDLE",
    tracked_file: null,
    attempts: 0,
    failures: [],
    candidate_turn: null,
    last_edit_content: null,
    test_command: null,
    context: null,
    current_turn: 0
  };
  if (!fs.existsSync(stateFile)) {
    return defaultState;
  }
  try {
    const data = JSON.parse(fs.readFileSync(stateFile, "utf-8"));
    if (data.session_id !== sessionId) {
      return defaultState;
    }
    return { ...defaultState, ...data };
  } catch {
    return defaultState;
  }
}
function saveState(stateFile, state) {
  const dir = path.dirname(stateFile);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(stateFile, JSON.stringify(state, null, 2));
}
function isTestCommand(command) {
  return TEST_COMMANDS.some((pattern) => pattern.test(command));
}
function isTestSuccess(output) {
  const hasSuccess = SUCCESS_PATTERNS.some((p) => p.test(output));
  const hasFailure = FAILURE_PATTERNS.some((p) => p.test(output));
  return hasSuccess && !hasFailure;
}
function isTestFailure(output) {
  return FAILURE_PATTERNS.some((p) => p.test(output));
}
function extractErrorMessage(output) {
  const lines = output.split("\n");
  for (const line of lines) {
    if (/error:|exception:|failed:/i.test(line)) {
      return line.trim().slice(0, 200);
    }
  }
  for (const line of lines) {
    if (line.trim() && /\b(error|fail|exception)\b/i.test(line)) {
      return line.trim().slice(0, 200);
    }
  }
  return "Unknown error";
}
function getOpcDir() {
  return process.env.CLAUDE_OPC_DIR || path.join(process.env.HOME || process.env.USERPROFILE || "", "continuous-claude", "opc");
}
async function storeVictoryLearning(state, projectDir) {
  const opcDir = getOpcDir();
  const failedApproaches = state.failures.map((f) => f.error).filter((v, i, a) => a.indexOf(v) === i).slice(0, 3).join("; ");
  const content = `Problem solved after ${state.attempts} attempts.
File: ${state.tracked_file}
Solution: ${state.last_edit_content || "Final edit"}
${failedApproaches ? `Failed approaches: ${failedApproaches}` : ""}
Test: ${state.test_command || "Unknown test command"}`;
  const script = "scripts/core/store_learning.py";
  const escapedContent = content.slice(0, 2e3).replace(/"/g, '\\"');
  const contextStr = `Victory: ${state.context || state.tracked_file}`;
  const tagsStr = `victory,verified,attempts:${state.attempts}`;
  const cmd = `uv run python ${script} --session-id "${state.session_id}" --type WORKING_SOLUTION --content "${escapedContent}" --context "${contextStr}" --tags "${tagsStr}" --confidence high --project-dir "${projectDir}"`;
  try {
    const { execSync } = __require("child_process");
    execSync(cmd, {
      encoding: "utf-8",
      cwd: opcDir,
      timeout: 6e4,
      stdio: ["pipe", "pipe", "pipe"],
      shell: true
    });
    return true;
  } catch {
    return false;
  }
}
function processTransition(state, toolName, toolInput, toolResponse, projectDir) {
  const newState = { ...state, current_turn: state.current_turn + 1 };
  let message = null;
  if (toolName === "Edit" || toolName === "Write") {
    const filePath = toolInput.file_path || "";
    const normalizedPath = path.basename(filePath);
    if (newState.state === "IDLE") {
      newState.state = "ATTEMPTING";
      newState.tracked_file = filePath;
      newState.attempts = 1;
      newState.failures = [];
      newState.context = `Editing ${normalizedPath}`;
    } else if (newState.state === "CANDIDATE" && filePath === newState.tracked_file) {
      newState.state = "ATTEMPTING";
      newState.attempts += 1;
      newState.candidate_turn = null;
    } else if (newState.state === "ATTEMPTING" && filePath === newState.tracked_file) {
      newState.attempts += 1;
    } else if (filePath !== newState.tracked_file) {
      if (newState.state === "CANDIDATE" && newState.candidate_turn) {
        const turnsSince = newState.current_turn - newState.candidate_turn;
        if (turnsSince >= VICTORY_TURN_THRESHOLD) {
          storeVictoryLearning(newState, projectDir);
          message = `[SmarterEveryDay] Victory captured: ${normalizedPath} fixed after ${newState.attempts} attempts`;
          newState.state = "IDLE";
          newState.tracked_file = null;
          newState.attempts = 0;
          newState.failures = [];
          newState.candidate_turn = null;
        }
      }
    }
    if (toolInput.new_string) {
      newState.last_edit_content = String(toolInput.new_string).slice(0, 500);
    } else if (toolInput.content) {
      newState.last_edit_content = String(toolInput.content).slice(0, 500);
    }
  }
  if (toolName === "Bash") {
    const command = toolInput.command || "";
    if (isTestCommand(command)) {
      newState.test_command = command;
      const output = String(toolResponse?.output || "");
      if (newState.state === "ATTEMPTING") {
        newState.state = "TESTING";
        if (isTestSuccess(output)) {
          newState.state = "CANDIDATE";
          newState.candidate_turn = newState.current_turn;
        } else if (isTestFailure(output)) {
          newState.state = "ATTEMPTING";
          newState.failures.push({
            turn: newState.current_turn,
            error: extractErrorMessage(output)
          });
          if (newState.failures.length > 5) {
            newState.failures = newState.failures.slice(-5);
          }
        }
      } else if (newState.state === "CANDIDATE") {
        if (isTestSuccess(output)) {
        } else if (isTestFailure(output)) {
          newState.state = "ATTEMPTING";
          newState.candidate_turn = null;
          newState.failures.push({
            turn: newState.current_turn,
            error: extractErrorMessage(output)
          });
        }
      }
    }
  }
  if (toolName === "TaskUpdate") {
    const status = toolInput.status || "";
    if (status === "completed" && newState.state === "CANDIDATE") {
      storeVictoryLearning(newState, projectDir);
      message = `[SmarterEveryDay] Victory confirmed (task complete): ${newState.tracked_file} fixed after ${newState.attempts} attempts`;
      newState.state = "IDLE";
      newState.tracked_file = null;
      newState.attempts = 0;
      newState.failures = [];
      newState.candidate_turn = null;
    }
  }
  if (newState.state === "CANDIDATE" && newState.candidate_turn) {
    const turnsSince = newState.current_turn - newState.candidate_turn;
    if (turnsSince >= VICTORY_TURN_THRESHOLD && newState.attempts >= 2) {
      storeVictoryLearning(newState, projectDir);
      message = `[SmarterEveryDay] Victory (${turnsSince} turns stable): ${newState.tracked_file} fixed after ${newState.attempts} attempts`;
      newState.state = "IDLE";
      newState.tracked_file = null;
      newState.attempts = 0;
      newState.failures = [];
      newState.candidate_turn = null;
    }
  }
  return { newState, message };
}
async function main() {
  const input = await readStdin();
  if (!input.trim()) {
    console.log(JSON.stringify({ continue: true }));
    return;
  }
  let data;
  try {
    data = JSON.parse(input);
  } catch {
    console.log(JSON.stringify({ continue: true }));
    return;
  }
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const stateFile = getStateFilePath(projectDir);
  const state = loadState(stateFile, data.session_id);
  const { newState, message } = processTransition(
    state,
    data.tool_name,
    data.tool_input,
    data.tool_response,
    projectDir
  );
  saveState(stateFile, newState);
  const output = {
    continue: true,
    systemMessage: message || void 0
  };
  console.log(JSON.stringify(output));
}
async function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf-8");
    process.stdin.on("data", (chunk) => data += chunk);
    process.stdin.on("end", () => resolve(data));
  });
}
main().catch((err) => {
  console.error("smarter-everyday error:", err);
  console.log(JSON.stringify({ continue: true }));
});
