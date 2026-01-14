// src/working-on-sync.ts
import { readFileSync } from "fs";

// src/shared/db-utils-pg.ts
import { spawnSync } from "child_process";
import { join } from "path";
function getPgConnectionString() {
  return process.env.OPC_POSTGRES_URL || "process.env.DATABASE_URL || "postgresql://claude:claude_dev@localhost:5432/continuous_claude"";
}
function runPgQuery(pythonCode, args = []) {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const opcDir = join(projectDir, "opc");
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

// src/working-on-sync.ts
function getSessionId() {
  return process.env.COORDINATION_SESSION_ID || process.env.BRAINTRUST_SPAN_ID?.slice(0, 8) || "";
}
function getProject() {
  return process.env.CLAUDE_PROJECT_DIR || process.cwd();
}
function readStdin() {
  try {
    return readFileSync(0, "utf-8");
  } catch {
    return "{}";
  }
}
function main() {
  if (process.env.CONTINUOUS_CLAUDE_COORDINATION !== "true") {
    console.log(JSON.stringify({ result: "continue" }));
    return;
  }
  let input;
  try {
    input = JSON.parse(readStdin());
  } catch {
    console.log(JSON.stringify({ result: "continue" }));
    return;
  }
  if (input.tool_name !== "TodoWrite") {
    console.log(JSON.stringify({ result: "continue" }));
    return;
  }
  const sessionId = getSessionId();
  const project = getProject();
  if (!sessionId) {
    console.log(JSON.stringify({ result: "continue" }));
    return;
  }
  const todos = input.tool_input?.todos || [];
  const inProgressTodo = todos.find((t) => t.status === "in_progress");
  const workingOn = inProgressTodo ? inProgressTodo.activeForm || inProgressTodo.content : "";
  const pythonCode = `
import asyncpg
import os

session_id = sys.argv[1]
project = sys.argv[2]
working_on = sys.argv[3] if len(sys.argv) > 3 else ''
pg_url = os.environ.get('CONTINUOUS_CLAUDE_DB_URL', 'postgresql://claude:claude_dev@localhost:5432/continuous_claude')

async def main():
    conn = await asyncpg.connect(pg_url)
    try:
        await conn.execute('''
            UPDATE sessions
            SET working_on = $3, last_heartbeat = NOW()
            WHERE id = $1 AND project = $2
        ''', session_id, project, working_on)
        print('ok')
    finally:
        await conn.close()

asyncio.run(main())
`;
  runPgQuery(pythonCode, [sessionId, project, workingOn]);
  console.log(JSON.stringify({ result: "continue" }));
}
main();
export {
  main
};
