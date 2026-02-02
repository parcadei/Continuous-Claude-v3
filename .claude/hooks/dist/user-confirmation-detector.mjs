#!/usr/bin/env node
var __require = /* @__PURE__ */ ((x) => typeof require !== "undefined" ? require : typeof Proxy !== "undefined" ? new Proxy(x, {
  get: (a, b) => (typeof require !== "undefined" ? require : a)[b]
}) : x)(function(x) {
  if (typeof require !== "undefined") return require.apply(this, arguments);
  throw Error('Dynamic require of "' + x + '" is not supported');
});

// src/user-confirmation-detector.ts
import * as fs from "fs";
import * as path from "path";
var RESOLUTION_SIGNALS = [
  // Direct confirmations
  /(?:this|it)(?:'s| is)(?: now)? (?:fixed|working|resolved|done)/i,
  /(?:that|it) (?:worked|works)(?: now)?[.!]?$/i,
  /(?:problem|issue|bug)(?: is)? (?:fixed|solved|resolved)/i,
  /(?:all|everything)(?: is)? (?:good|working|fixed)/i,
  /(?:got it|figured it out)/i,
  // Success acknowledgments
  /^(?:perfect|excellent|great|awesome|nice)[.!]?$/i,
  /^(?:yes|yep|yeah),? (?:that|it)(?:'s| is) (?:it|right|correct)/i,
  /^thanks?,? (?:that|it) (?:worked|fixed)/i
];
var MEMORY_SIGNALS = [
  /(?:remember|note|record) (?:this|that)/i,
  /(?:make|take) a note/i,
  /(?:for )?future reference/i,
  /(?:keep|save) (?:this|that) (?:in mind|for later)/i,
  /(?:don't forget|important to remember)/i,
  /(?:store|save) (?:this|that) (?:learning|insight)/i
];
var ANTI_PATTERNS = [
  /\?$/,
  // Questions
  /^(?:can you|could you|please|would you)/i,
  /^(?:try|check|look|see|run|test|fix|change)/i,
  /^(?:wait|stop|hold on|actually)/i
];
function getOpcDir() {
  return process.env.CLAUDE_OPC_DIR || path.join(process.env.HOME || process.env.USERPROFILE || "", "continuous-claude", "opc");
}
function getSmarterStateFilePath(projectDir) {
  return path.join(projectDir, ".claude", "smarter-everyday-state.json");
}
function loadSmarterState(stateFile) {
  if (!fs.existsSync(stateFile)) return null;
  try {
    return JSON.parse(fs.readFileSync(stateFile, "utf-8"));
  } catch {
    return null;
  }
}
function saveSmarterState(stateFile, state) {
  fs.writeFileSync(stateFile, JSON.stringify(state, null, 2));
}
function isResolutionConfirmation(prompt) {
  if (ANTI_PATTERNS.some((p) => p.test(prompt))) {
    return false;
  }
  return RESOLUTION_SIGNALS.some((p) => p.test(prompt));
}
function isMemoryRequest(prompt) {
  return MEMORY_SIGNALS.some((p) => p.test(prompt));
}
async function storeUserConfirmedLearning(sessionId, prompt, context, projectDir) {
  const opcDir = getOpcDir();
  const content = context ? `User confirmed: "${prompt}". Context: ${context}` : `User confirmed: "${prompt}"`;
  const script = "scripts/core/store_learning.py";
  const escapedContent = content.slice(0, 1e3).replace(/"/g, '\\"');
  const cmd = `uv run python ${script} --session-id "${sessionId}" --type USER_PREFERENCE --content "${escapedContent}" --context "user confirmation" --tags "user_confirmed,verified" --confidence high --project-dir "${projectDir}"`;
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
async function storeVictoryFromConfirmation(state, prompt, projectDir) {
  const opcDir = getOpcDir();
  const failedApproaches = state.failures.map((f) => f.error).filter((v, i, a) => a.indexOf(v) === i).slice(0, 3).join("; ");
  const content = `Problem solved after ${state.attempts} attempts (user confirmed: "${prompt}").
File: ${state.tracked_file}
Solution: ${state.last_edit_content || "Final edit"}
${failedApproaches ? `Failed approaches: ${failedApproaches}` : ""}`;
  const script = "scripts/core/store_learning.py";
  const escapedContent = content.slice(0, 2e3).replace(/"/g, '\\"');
  const contextStr = `Victory (user confirmed): ${state.context || state.tracked_file}`;
  const tagsStr = `victory,verified,user_confirmed,attempts:${state.attempts}`;
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
  const prompt = data.prompt?.trim() || "";
  const sessionId = data.session_id;
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  if (prompt.length < 3) {
    console.log(JSON.stringify({ continue: true }));
    return;
  }
  let message = null;
  if (isResolutionConfirmation(prompt)) {
    const smarterStateFile = getSmarterStateFilePath(projectDir);
    const smarterState = loadSmarterState(smarterStateFile);
    if (smarterState && smarterState.state === "CANDIDATE") {
      const stored = await storeVictoryFromConfirmation(smarterState, prompt, projectDir);
      if (stored) {
        message = `[UserConfirm:L1] Victory confirmed by user: ${smarterState.tracked_file} (${smarterState.attempts} attempts)`;
        smarterState.state = "IDLE";
        smarterState.tracked_file = null;
        smarterState.attempts = 0;
        smarterState.failures = [];
        smarterState.candidate_turn = null;
        saveSmarterState(smarterStateFile, smarterState);
      }
    } else {
      const stored = await storeUserConfirmedLearning(
        sessionId,
        prompt,
        smarterState?.context || null,
        projectDir
      );
      if (stored) {
        message = "[UserConfirm:L1] User confirmation captured";
      }
    }
  }
  if (isMemoryRequest(prompt)) {
    message = message ? message + " (memory request noted)" : "[UserConfirm:L1] Memory request detected - watching for content to remember";
  }
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
  console.error("user-confirmation-detector error:", err);
  console.log(JSON.stringify({ continue: true }));
});
