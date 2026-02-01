#!/usr/bin/env node

// src/heartbeat.ts
import { existsSync as existsSync2, readFileSync as readFileSync2, writeFileSync as writeFileSync2, mkdirSync as mkdirSync2 } from "fs";
import { join as join3 } from "path";

// src/shared/db-utils-pg.ts
import { spawnSync } from "child_process";

// src/shared/opc-path.ts
import { existsSync } from "fs";
import { join } from "path";
function getOpcDir() {
  const envOpcDir = process.env.CLAUDE_OPC_DIR;
  if (envOpcDir && existsSync(envOpcDir)) {
    return envOpcDir;
  }
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const localOpc = join(projectDir, "opc");
  if (existsSync(localOpc)) {
    return localOpc;
  }
  const homeDir = process.env.HOME || process.env.USERPROFILE || "";
  if (homeDir) {
    const globalClaude = join(homeDir, ".claude");
    const globalScripts = join(globalClaude, "scripts", "core");
    if (existsSync(globalScripts) && globalClaude !== projectDir) {
      return globalClaude;
    }
  }
  return null;
}
function requireOpcDir() {
  const opcDir = getOpcDir();
  if (!opcDir) {
    console.log(JSON.stringify({ result: "continue" }));
    process.exit(0);
  }
  return opcDir;
}

// src/shared/db-utils-pg.ts
function getPgConnectionString() {
  return process.env.CONTINUOUS_CLAUDE_DB_URL || process.env.DATABASE_URL || process.env.OPC_POSTGRES_URL || "postgresql://claude:claude_dev@localhost:5434/continuous_claude";
}
function runPgQuery(pythonCode, args = []) {
  const opcDir = requireOpcDir();
  const wrappedCode = `
import sys
import os
import asyncio
import json

# Add opc to path for imports
sys.path.insert(0, '${opcDir.replace(/\\/g, "/")}')
os.chdir('${opcDir.replace(/\\/g, "/")}')

${pythonCode}
`;
  try {
    const result = spawnSync("uv", ["run", "python", "-c", wrappedCode, ...args], {
      encoding: "utf-8",
      maxBuffer: 1024 * 1024,
      timeout: 3e3,
      // 3 second timeout (reduced for faster startup)
      cwd: opcDir,
      env: {
        ...process.env,
        CONTINUOUS_CLAUDE_DB_URL: getPgConnectionString()
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
function registerSession(sessionId, project, workingOn = "") {
  const pythonCode = `
import asyncpg
import os
from datetime import datetime

session_id = sys.argv[1]
project = sys.argv[2]
working_on = sys.argv[3] if len(sys.argv) > 3 else ''
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5432/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        # Create table if not exists
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                project TEXT NOT NULL,
                working_on TEXT,
                started_at TIMESTAMP DEFAULT NOW(),
                last_heartbeat TIMESTAMP DEFAULT NOW()
            )
        ''')

        # Upsert session
        await conn.execute('''
            INSERT INTO sessions (id, project, working_on, started_at, last_heartbeat)
            VALUES ($1, $2, $3, NOW(), NOW())
            ON CONFLICT (id) DO UPDATE SET
                working_on = EXCLUDED.working_on,
                last_heartbeat = NOW()
        ''', session_id, project, working_on)

        print('ok')
    finally:
        await conn.close()

asyncio.run(main())
`;
  const result = runPgQuery(pythonCode, [sessionId, project, workingOn]);
  if (!result.success || result.stdout !== "ok") {
    return {
      success: false,
      error: result.stderr || result.stdout || "Unknown error"
    };
  }
  return { success: true };
}

// src/shared/session-id.ts
import { mkdirSync, readFileSync, writeFileSync } from "fs";
import { join as join2 } from "path";
var SESSION_ID_FILENAME = ".coordination-session-id";
function getSessionIdFile(options = {}) {
  const claudeDir = join2(process.env.HOME || "/tmp", ".claude");
  if (options.createDir) {
    try {
      mkdirSync(claudeDir, { recursive: true, mode: 448 });
    } catch {
    }
  }
  return join2(claudeDir, SESSION_ID_FILENAME);
}
function generateSessionId() {
  const spanId = process.env.BRAINTRUST_SPAN_ID;
  if (spanId) {
    return spanId.slice(0, 8);
  }
  return `s-${Date.now().toString(36)}`;
}
function readSessionId() {
  try {
    const sessionFile = getSessionIdFile();
    const id = readFileSync(sessionFile, "utf-8").trim();
    return id || null;
  } catch {
    return null;
  }
}
function getSessionId(options = {}) {
  if (process.env.COORDINATION_SESSION_ID) {
    return process.env.COORDINATION_SESSION_ID;
  }
  const fileId = readSessionId();
  if (fileId) {
    return fileId;
  }
  if (options.debug) {
    console.error("[session-id] WARNING: No persisted session ID found, generating new one");
  }
  return generateSessionId();
}

// src/heartbeat.ts
var CACHE_TTL_MS = 3e4;
var CACHE_DIR = join3(process.env.HOME || process.env.USERPROFILE || "", ".claude", "cache");
var CACHE_FILE = join3(CACHE_DIR, "heartbeat-last.json");
function shouldUpdateHeartbeat(sessionId) {
  try {
    if (!existsSync2(CACHE_FILE)) return true;
    const cache = JSON.parse(readFileSync2(CACHE_FILE, "utf-8"));
    if (cache.sessionId !== sessionId) return true;
    const elapsed = Date.now() - cache.timestamp;
    return elapsed >= CACHE_TTL_MS;
  } catch {
    return true;
  }
}
function updateCache(sessionId) {
  try {
    mkdirSync2(CACHE_DIR, { recursive: true });
    writeFileSync2(CACHE_FILE, JSON.stringify({ sessionId, timestamp: Date.now() }));
  } catch {
  }
}
function readStdin() {
  return readFileSync2(0, "utf-8");
}
function main() {
  let input = {};
  try {
    const rawInput = readStdin().trim();
    if (rawInput) {
      input = JSON.parse(rawInput);
    }
  } catch {
  }
  const sessionId = input.session_id || getSessionId();
  const project = input.cwd || process.cwd();
  const homeDir = process.env.HOME || process.env.USERPROFILE || "";
  if (homeDir) {
    const claudeDir = homeDir.replace(/\\/g, "/") + "/.claude";
    const normalizedProject = project.replace(/\\/g, "/");
    if (normalizedProject === claudeDir || normalizedProject.endsWith("/.claude")) {
      console.log(JSON.stringify({ result: "continue" }));
      return;
    }
  }
  const workingOn = input.prompt ? input.prompt.split("\n")[0].substring(0, 100) : void 0;
  if (!shouldUpdateHeartbeat(sessionId)) {
    console.log(JSON.stringify({ result: "continue" }));
    return;
  }
  const result = registerSession(sessionId, project, workingOn);
  if (!result.success) {
    console.error(`Heartbeat update failed: ${result.error}`);
  } else {
    updateCache(sessionId);
  }
  console.log(JSON.stringify({ result: "continue" }));
}
try {
  main();
} catch (err) {
  console.error("Heartbeat error:", err);
  console.log(JSON.stringify({ result: "continue" }));
}
