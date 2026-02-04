#!/usr/bin/env node

// src/sync-to-repo.ts
import { execSync } from "child_process";
import * as fs from "fs";
import * as path from "path";
var BASH_LOCATIONS = [
  process.env.GIT_BASH_PATH,
  "C:\\Program Files\\Git\\bin\\bash.exe",
  "C:\\Program Files (x86)\\Git\\bin\\bash.exe",
  process.env.PROGRAMFILES ? process.env.PROGRAMFILES + "\\Git\\bin\\bash.exe" : null,
  process.env.LOCALAPPDATA ? process.env.LOCALAPPDATA + "\\Programs\\Git\\bin\\bash.exe" : null
];
function findBash() {
  for (const loc of BASH_LOCATIONS) {
    if (loc && fs.existsSync(loc)) return loc;
  }
  return null;
}
var CLAUDE_DIR = process.env.HOME ? path.join(process.env.HOME, ".claude") : path.join(process.env.USERPROFILE || "", ".claude");
var REPO_DIR = process.env.USERPROFILE ? path.join(process.env.USERPROFILE, "continuous-claude") : path.join(process.env.HOME || "", "continuous-claude");
var SYNC_SCRIPT = path.join(REPO_DIR, "scripts", "sync-claude.sh");
var SYNC_PATTERNS = [
  /[\\\/]hooks[\\\/]src[\\\/]/,
  /[\\\/]hooks[\\\/]dist[\\\/]/,
  /[\\\/]hooks[\\\/][^\\\/]+\.(sh|py|ts|mjs)$/,
  /[\\\/]skills[\\\/]/,
  /[\\\/]rules[\\\/]/,
  /[\\\/]agents[\\\/]/,
  /[\\\/]scripts[\\\/]/
];
var NEVER_SYNC = [
  "CLAUDE.md",
  "RULES.md",
  "settings.json",
  ".env",
  "knowledge-tree.json"
];
function shouldSync(filePath) {
  if (!filePath) return false;
  const normalized = filePath.replace(/\\/g, "/");
  if (!normalized.includes(".claude/")) return false;
  const basename2 = path.basename(filePath);
  if (NEVER_SYNC.includes(basename2)) return false;
  return SYNC_PATTERNS.some((pattern) => pattern.test(filePath));
}
function runSync() {
  if (!fs.existsSync(SYNC_SCRIPT)) {
    return {
      success: false,
      message: `Sync script not found at ${SYNC_SCRIPT}`
    };
  }
  try {
    const isWindows = process.platform === "win32";
    let bashCmd;
    if (isWindows) {
      const bashPath = findBash();
      if (!bashPath) {
        return {
          success: false,
          message: "Git Bash not found. Set GIT_BASH_PATH env var or install Git for Windows."
        };
      }
      bashCmd = `"${bashPath}" -c "source '${SYNC_SCRIPT.replace(/\\/g, "/")}' --to-repo"`;
    } else {
      bashCmd = `bash "${SYNC_SCRIPT}" --to-repo`;
    }
    const output = execSync(bashCmd, {
      cwd: REPO_DIR,
      encoding: "utf8",
      timeout: 3e4,
      windowsHide: true
    });
    const syncMatch = output.match(/Synced: (\d+) files/);
    const syncCount = syncMatch ? syncMatch[1] : "?";
    return {
      success: true,
      message: `Auto-synced ${syncCount} files to continuous-claude repo`
    };
  } catch (error) {
    return {
      success: false,
      message: `Sync failed: ${error.message}`
    };
  }
}
async function hook(input2) {
  const filePath = input2.tool_input?.file_path || input2.tool_input?.path;
  if (!shouldSync(filePath || "")) {
    return { continue: true };
  }
  const stateFile = path.join(CLAUDE_DIR, ".last-repo-sync");
  const now = Date.now();
  if (fs.existsSync(stateFile)) {
    const lastSync = parseInt(fs.readFileSync(stateFile, "utf8"), 10);
    if (now - lastSync < 1e4) {
      return { continue: true };
    }
  }
  const result = runSync();
  if (result.success) {
    fs.writeFileSync(stateFile, now.toString());
  }
  return {
    continue: true,
    message: result.message
  };
}
var input = JSON.parse(
  fs.readFileSync(process.stdin.fd, "utf8")
);
hook(input).then((output) => {
  console.log(JSON.stringify(output));
}).catch((error) => {
  console.log(JSON.stringify({
    continue: true,
    message: `sync-to-repo hook error: ${error.message}`
  }));
});
