#!/usr/bin/env node

// src/maestro-cleanup.ts
import { readFileSync, existsSync as existsSync2, unlinkSync as unlinkSync2 } from "fs";

// src/shared/session-isolation.ts
import { tmpdir, hostname } from "os";
import { join } from "path";
import { existsSync, readdirSync, statSync, unlinkSync } from "fs";
function getSessionId() {
  if (process.env.CLAUDE_SESSION_ID) {
    return process.env.CLAUDE_SESSION_ID;
  }
  const host = hostname().replace(/[^a-zA-Z0-9]/g, "").substring(0, 8);
  return `${host}-${process.pid}`;
}
function getSessionStatePath(baseName, sessionId) {
  const sid = sessionId || getSessionId();
  const safeSid = sid.replace(/[^a-zA-Z0-9-_]/g, "_").substring(0, 32);
  return join(tmpdir(), `claude-${baseName}-${safeSid}.json`);
}
function getLegacyStatePath(baseName) {
  return join(tmpdir(), `claude-${baseName}.json`);
}
function getStatePathWithMigration(baseName, sessionId) {
  const sessionPath = getSessionStatePath(baseName, sessionId);
  const legacyPath = getLegacyStatePath(baseName);
  if (existsSync(sessionPath)) {
    return sessionPath;
  }
  if (existsSync(legacyPath)) {
    try {
      const stat = statSync(legacyPath);
      const oneHourAgo = Date.now() - 60 * 60 * 1e3;
      if (stat.mtimeMs > oneHourAgo) {
        return legacyPath;
      }
    } catch {
    }
  }
  return sessionPath;
}
function cleanupOldStateFiles(baseName, maxAgeMs = 24 * 60 * 60 * 1e3) {
  const tmpDir = tmpdir();
  const pattern = new RegExp(`^claude-${baseName}-.*\\.json$`);
  let cleaned = 0;
  try {
    const files = readdirSync(tmpDir);
    const now = Date.now();
    for (const file of files) {
      if (!pattern.test(file)) continue;
      const fullPath = join(tmpDir, file);
      try {
        const stat = statSync(fullPath);
        if (now - stat.mtimeMs > maxAgeMs) {
          unlinkSync(fullPath);
          cleaned++;
        }
      } catch {
      }
    }
  } catch {
  }
  return cleaned;
}

// src/maestro-cleanup.ts
var STATE_FILES = ["maestro-state", "ralph-state"];
function readStdin() {
  try {
    return readFileSync(0, "utf-8");
  } catch {
    return "{}";
  }
}
function cleanupStateFile(baseName, sessionId) {
  try {
    const stateFile = getStatePathWithMigration(baseName, sessionId);
    if (existsSync2(stateFile)) {
      unlinkSync2(stateFile);
      return true;
    }
  } catch {
  }
  return false;
}
async function main() {
  let input = {};
  try {
    input = JSON.parse(readStdin());
  } catch {
  }
  const sessionId = input.session_id;
  const cleaned = [];
  for (const baseName of STATE_FILES) {
    if (cleanupStateFile(baseName, sessionId)) {
      cleaned.push(baseName);
    }
  }
  for (const baseName of STATE_FILES) {
    cleanupOldStateFiles(baseName, 24 * 60 * 60 * 1e3);
  }
  if (cleaned.length > 0) {
    console.log(JSON.stringify({
      result: "continue",
      message: `Cleaned up state: ${cleaned.join(", ")}`
    }));
  } else {
    console.log(JSON.stringify({ result: "continue" }));
  }
}
main().catch(() => {
  console.log(JSON.stringify({ result: "continue" }));
});
