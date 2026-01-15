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
    if (existsSync(globalScripts)) {
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
  return process.env.CONTINUOUS_CLAUDE_DB_URL || process.env.DATABASE_URL || process.env.OPC_POSTGRES_URL || "postgresql://claude:claude_dev@localhost:5432/continuous_claude";
}
function runPgQuery(pythonCode, args = []) {
  const opcDir = requireOpcDir();
  const wrappedCode = `
import sys
import os
import asyncio
import json

# Add opc to path for imports
sys.path.insert(0, '${opcDir}')
os.chdir('${opcDir}')

${pythonCode}
`;
  try {
    const result = spawnSync("uv", ["run", "python", "-c", wrappedCode, ...args], {
      encoding: "utf-8",
      maxBuffer: 1024 * 1024,
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

// src/shared/session-id.ts
import { mkdirSync, readFileSync, writeFileSync } from "fs";
import { join as join2 } from "path";
var SESSION_ID_FILENAME = ".coordination-session-id";
function getSessionIdFile(options = {}) {
  const projectDir = getProject();
  const claudeDir = join2(projectDir, ".claude");
  if (options.createDir) {
    try {
      mkdirSync(claudeDir, { recursive: true, mode: 448 });
    } catch {
    }
  }
  return join2(claudeDir, SESSION_ID_FILENAME);
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
function getProject() {
  return process.env.CLAUDE_PROJECT_DIR || process.cwd();
}

// src/heartbeat.ts
function main() {
  if (process.env.CONTINUOUS_CLAUDE_COORDINATION !== "true") {
    console.log(JSON.stringify({ result: "continue" }));
    return;
  }
  const sessionId = readSessionId();
  const project = getProject();
  if (!sessionId) {
    console.log(JSON.stringify({ result: "continue" }));
    return;
  }
  const pythonCode = `
import sys
import asyncio
import asyncpg
import os

session_id = sys.argv[1]
project = sys.argv[2]
# Connection URL from environment - no hardcoded credentials
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL') or os.environ.get('DATABASE_URL')
if not pg_url:
    print('CONTINUOUS_CLAUDE_DB_URL or DATABASE_URL not set', file=sys.stderr)
    sys.exit(1)

async def main():
    try:
        # 5 second timeout to avoid hanging on unreachable DB
        conn = await asyncio.wait_for(asyncpg.connect(pg_url), timeout=5.0)
    except asyncio.TimeoutError:
        print('connection_timeout', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'connection_error: {e}', file=sys.stderr)
        sys.exit(1)
    try:
        result = await conn.execute('''
            UPDATE sessions
            SET last_heartbeat = NOW(), project = $2
            WHERE id = $1
        ''', session_id, project)
        # Check if any row was updated
        if result == 'UPDATE 0':
            print('no_session_found', file=sys.stderr)
        else:
            print('ok')
    finally:
        await conn.close()

asyncio.run(main())
`;
  const result = runPgQuery(pythonCode, [sessionId, project]);
  if (!result.success && result.stderr) {
    console.error(`[heartbeat] WARNING: ${result.stderr}`);
  }
  console.log(JSON.stringify({ result: "continue" }));
}
main();
export {
  main
};
