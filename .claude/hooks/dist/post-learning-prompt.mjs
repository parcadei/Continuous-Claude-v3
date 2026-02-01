// src/post-learning-prompt.ts
import { readFileSync, existsSync, writeFileSync, mkdirSync } from "fs";
import { homedir } from "os";
import { join, dirname } from "path";
var STATE_FILE = join(homedir(), ".claude", "cache", "learning-state.json");
var PROMPT_COOLDOWN_MS = 3e5;
var EDIT_SEQUENCE_THRESHOLD = 3;
var EDIT_WINDOW_MS = 12e4;
function loadState(sessionId) {
  try {
    if (existsSync(STATE_FILE)) {
      const data = JSON.parse(readFileSync(STATE_FILE, "utf-8"));
      return data[sessionId] || createDefaultState();
    }
  } catch {
  }
  return createDefaultState();
}
function saveState(sessionId, state) {
  try {
    const dir = dirname(STATE_FILE);
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }
    let data = {};
    if (existsSync(STATE_FILE)) {
      try {
        data = JSON.parse(readFileSync(STATE_FILE, "utf-8"));
      } catch {
      }
    }
    data[sessionId] = state;
    const keys = Object.keys(data);
    if (keys.length > 10) {
      const sortedKeys = keys.sort((a, b) => data[b].lastEditTime - data[a].lastEditTime);
      data = Object.fromEntries(sortedKeys.slice(0, 10).map((k) => [k, data[k]]));
    }
    writeFileSync(STATE_FILE, JSON.stringify(data, null, 2));
  } catch {
  }
}
function createDefaultState() {
  return {
    editCount: 0,
    lastEditTime: 0,
    recentTools: [],
    errorDiscussed: false,
    lastPromptTime: 0
  };
}
function shouldPrompt(state, now) {
  if (now - state.lastPromptTime < PROMPT_COOLDOWN_MS) {
    return { shouldPrompt: false, reason: "cooldown" };
  }
  if (state.editCount >= EDIT_SEQUENCE_THRESHOLD && now - state.lastEditTime < EDIT_WINDOW_MS) {
    return { shouldPrompt: true, reason: "edit_sequence" };
  }
  if (state.errorDiscussed && state.recentTools.slice(-1)[0] === "Edit") {
    return { shouldPrompt: true, reason: "error_fix" };
  }
  return { shouldPrompt: false, reason: "none" };
}
function getPromptMessage(reason) {
  switch (reason) {
    case "edit_sequence":
      return "Multiple file edits detected. If you discovered a pattern or made an architectural decision, consider storing it: `/remember` or use store_learning.py";
    case "error_fix":
      return "Bug fix completed. If this fix involved non-obvious insights, consider storing the solution: `/remember` or use store_learning.py";
    default:
      return "";
  }
}
async function main() {
  const input = JSON.parse(readFileSync(0, "utf-8"));
  const now = Date.now();
  const state = loadState(input.session_id);
  state.recentTools.push(input.tool_name);
  if (state.recentTools.length > 10) {
    state.recentTools.shift();
  }
  if (input.tool_name === "Edit" || input.tool_name === "Write") {
    if (now - state.lastEditTime > EDIT_WINDOW_MS) {
      state.editCount = 0;
    }
    state.editCount++;
    state.lastEditTime = now;
  }
  if (input.tool_name === "Grep" || input.tool_name === "Read") {
    const toolInput = input.tool_input || {};
    const content = JSON.stringify(toolInput).toLowerCase();
    if (content.includes("error") || content.includes("bug") || content.includes("fix") || content.includes("debug")) {
      state.errorDiscussed = true;
    }
  }
  const { shouldPrompt: doPrompt, reason } = shouldPrompt(state, now);
  if (doPrompt) {
    const message = getPromptMessage(reason);
    state.lastPromptTime = now;
    state.editCount = 0;
    state.errorDiscussed = false;
    saveState(input.session_id, state);
    const output = {
      hookSpecificOutput: {
        hookEventName: "PostToolUse",
        additionalContext: `
\u{1F4A1} **Learning Prompt**: ${message}
`
      }
    };
    console.log(JSON.stringify(output));
    return;
  }
  saveState(input.session_id, state);
  console.log("{}");
}
main().catch(() => console.log("{}"));
