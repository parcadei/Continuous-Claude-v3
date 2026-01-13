// src/session-register.ts
import { readFileSync as readFileSync2 } from "fs";

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
  return process.env.OPC_POSTGRES_URL || process.env.DATABASE_URL || "postgresql://claude:claude_dev@localhost:5432/continuous_claude";
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
        OPC_POSTGRES_URL: getPgConnectionString()
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
pg_url = os.environ.get('OPC_POSTGRES_URL', 'postgresql://claude:claude_dev@localhost:5432/continuous_claude')

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
function getActiveSessions(project) {
  const pythonCode = `
import asyncpg
import os
import json
from datetime import datetime, timedelta

project_filter = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != 'null' else None
pg_url = os.environ.get('OPC_POSTGRES_URL', 'postgresql://claude:claude_dev@localhost:5432/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        # Get sessions active in last 5 minutes
        cutoff = datetime.utcnow() - timedelta(minutes=5)

        if project_filter:
            rows = await conn.fetch('''
                SELECT id, project, working_on, started_at, last_heartbeat
                FROM sessions
                WHERE project = $1 AND last_heartbeat > $2
                ORDER BY started_at DESC
            ''', project_filter, cutoff)
        else:
            rows = await conn.fetch('''
                SELECT id, project, working_on, started_at, last_heartbeat
                FROM sessions
                WHERE last_heartbeat > $1
                ORDER BY started_at DESC
            ''', cutoff)

        sessions = []
        for row in rows:
            sessions.append({
                'id': row['id'],
                'project': row['project'],
                'working_on': row['working_on'],
                'started_at': row['started_at'].isoformat() if row['started_at'] else None,
                'last_heartbeat': row['last_heartbeat'].isoformat() if row['last_heartbeat'] else None
            })

        print(json.dumps(sessions))
    except Exception as e:
        print(json.dumps([]))
    finally:
        await conn.close()

asyncio.run(main())
`;
  const result = runPgQuery(pythonCode, [project || "null"]);
  if (!result.success) {
    return { success: false, sessions: [] };
  }
  try {
    const sessions = JSON.parse(result.stdout || "[]");
    return { success: true, sessions };
  } catch {
    return { success: false, sessions: [] };
  }
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
function writeSessionId(sessionId) {
  try {
    const filePath = getSessionIdFile({ createDir: true });
    writeFileSync(filePath, sessionId, { encoding: "utf-8", mode: 384 });
    return true;
  } catch {
    return false;
  }
}
function getProject() {
  return process.env.CLAUDE_PROJECT_DIR || process.cwd();
}

// src/session-register.ts
function main() {
  let input;
  try {
    const stdinContent = readFileSync2(0, "utf-8");
    input = JSON.parse(stdinContent);
  } catch {
    console.log(JSON.stringify({ result: "continue" }));
    return;
  }
  const sessionId = generateSessionId();
  const project = getProject();
  const projectName = project.split("/").pop() || "unknown";
  process.env.COORDINATION_SESSION_ID = sessionId;
  if (!writeSessionId(sessionId)) {
    console.error(`[session-register] WARNING: Failed to persist session ID ${sessionId} to file`);
  }
  const registerResult = registerSession(sessionId, project, "");
  const sessionsResult = getActiveSessions(project);
  const otherSessions = sessionsResult.sessions.filter((s) => s.id !== sessionId);
  let awarenessMessage = `
<system-reminder>
MULTI-SESSION COORDINATION ACTIVE

Session: ${sessionId}
Project: ${projectName}
`;
  if (otherSessions.length > 0) {
    awarenessMessage += `
Active peer sessions (${otherSessions.length}):
${otherSessions.map((s) => `  - ${s.id}: ${s.working_on || "working..."}`).join("\n")}

Coordination features:
- File edits are tracked to prevent conflicts
- Research findings are shared automatically
- Use Task tool normally - coordination happens via hooks
`;
  } else {
    awarenessMessage += `
No other sessions active on this project.
You are the only session currently working here.
`;
  }
  awarenessMessage += `</system-reminder>`;
  const output = {
    result: "continue",
    message: awarenessMessage
  };
  console.log(JSON.stringify(output));
}
main();
export {
  main
};
