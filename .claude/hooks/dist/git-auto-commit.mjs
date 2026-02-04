#!/usr/bin/env node

// src/git-auto-commit.ts
import { readFileSync, writeFileSync, existsSync, statSync } from "fs";
import { execSync } from "child_process";
import { join, resolve } from "path";
import { homedir } from "os";
var CLAUDE_DIR = join(homedir(), ".claude");
function checkGitAvailable() {
  try {
    execSync("git --version", { stdio: "pipe" });
    return null;
  } catch {
    return {
      type: "GIT_NOT_FOUND",
      message: "Git not found in PATH",
      suggestedAction: "Install git: https://git-scm.com/downloads"
    };
  }
}
function checkIsGitRepo() {
  try {
    execSync("git rev-parse --git-dir", { cwd: CLAUDE_DIR, stdio: "pipe" });
    return null;
  } catch {
    return {
      type: "NOT_GIT_REPO",
      message: `${CLAUDE_DIR} is not a git repository`,
      suggestedAction: "Run: cd ~/.claude && git init"
    };
  }
}
var DEBOUNCE_FILE = join(CLAUDE_DIR, ".last-git-sync");
var DEBOUNCE_MS = 10 * 60 * 1e3;
function isInClaudeDir(filePath) {
  const normalizedFile = resolve(filePath).replace(/\\/g, "/");
  const normalizedClaudeDir = CLAUDE_DIR.replace(/\\/g, "/");
  return normalizedFile.startsWith(normalizedClaudeDir);
}
function isTrackedByGit(filePath) {
  try {
    execSync(`git check-ignore -q "${filePath}"`, {
      cwd: CLAUDE_DIR,
      stdio: "pipe"
    });
    return false;
  } catch {
    return true;
  }
}
function shouldCommit() {
  if (!existsSync(DEBOUNCE_FILE)) {
    return true;
  }
  try {
    const stats = statSync(DEBOUNCE_FILE);
    const elapsed = Date.now() - stats.mtimeMs;
    return elapsed >= DEBOUNCE_MS;
  } catch {
    return true;
  }
}
function hasChanges() {
  try {
    const status = execSync("git status --porcelain", {
      cwd: CLAUDE_DIR,
      encoding: "utf-8"
    });
    return status.trim().length > 0;
  } catch {
    return false;
  }
}
function getChangeSummary() {
  try {
    const status = execSync("git status --porcelain", {
      cwd: CLAUDE_DIR,
      encoding: "utf-8"
    });
    const lines = status.trim().split("\n").filter(Boolean);
    const changes = [];
    for (const line of lines.slice(0, 5)) {
      const file = line.slice(3).trim();
      changes.push(file);
    }
    if (lines.length > 5) {
      changes.push(`+${lines.length - 5} more`);
    }
    return changes.join(", ");
  } catch {
    return "changes";
  }
}
function doCommit() {
  try {
    execSync("git add -A", { cwd: CLAUDE_DIR, stdio: "pipe" });
    const staged = execSync("git diff --cached --name-only", {
      cwd: CLAUDE_DIR,
      encoding: "utf-8"
    });
    if (!staged.trim()) {
      return false;
    }
    const summary = getChangeSummary();
    const timestamp = (/* @__PURE__ */ new Date()).toISOString().replace("T", " ").slice(0, 19);
    const message = `Auto: ${timestamp} - ${summary}`;
    execSync(`git commit -m "${message}"`, {
      cwd: CLAUDE_DIR,
      stdio: "pipe"
    });
    writeFileSync(DEBOUNCE_FILE, (/* @__PURE__ */ new Date()).toISOString());
    return true;
  } catch (err) {
    console.error("Git commit failed:", err);
    return false;
  }
}
async function main() {
  const gitError = checkGitAvailable();
  if (gitError) {
    console.log(JSON.stringify({
      result: "continue",
      message: `[git-auto-commit] ${gitError.message}. ${gitError.suggestedAction || ""}`
    }));
    return;
  }
  const repoError = checkIsGitRepo();
  if (repoError) {
    console.log(JSON.stringify({
      result: "continue",
      message: `[git-auto-commit] ${repoError.message}. ${repoError.suggestedAction || ""}`
    }));
    return;
  }
  let input;
  try {
    input = JSON.parse(readFileSync(0, "utf-8"));
  } catch {
    console.log("{}");
    return;
  }
  if (!["Write", "Edit"].includes(input.tool_name)) {
    console.log("{}");
    return;
  }
  const filePath = input.tool_input?.file_path;
  if (!filePath) {
    console.log("{}");
    return;
  }
  if (!isInClaudeDir(filePath) || !isTrackedByGit(filePath)) {
    console.log("{}");
    return;
  }
  if (!shouldCommit()) {
    console.log("{}");
    return;
  }
  if (!hasChanges()) {
    console.log("{}");
    return;
  }
  const committed = doCommit();
  if (committed) {
    console.log(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PostToolUse",
        additionalContext: "[Git] Auto-committed ~/.claude changes"
      }
    }));
  } else {
    console.log("{}");
  }
}
main().catch((err) => {
  console.log(JSON.stringify({
    result: "continue",
    message: `[git-auto-commit error] ${err.message || "Unknown error"}`
  }));
});
