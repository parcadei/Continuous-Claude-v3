// src/subagent-stop.ts
import { readFileSync } from "fs";

// src/shared/pattern-router.ts
function detectPattern() {
  const pattern = process.env.PATTERN_TYPE;
  if (!pattern) return null;
  return pattern;
}
var SAFE_ID_PATTERN = /^[a-zA-Z0-9_-]{1,64}$/;
function isValidId(id) {
  return SAFE_ID_PATTERN.test(id);
}

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
function completeAgentPg(agentId, status = "completed", errorMessage = null) {
  const pythonCode = `
from scripts.agentica_patterns.coordination_pg import CoordinationDBPg
import json

agent_id = sys.argv[1]
status = sys.argv[2]
error_message = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != 'null' else None

async def main():
    try:
        async with CoordinationDBPg() as db:
            await db.complete_agent(
                agent_id=agent_id,
                status=status,
                result_summary=error_message
            )
        print('ok')
    except Exception as e:
        print(f'error: {e}')

asyncio.run(main())
`;
  const args = [
    agentId,
    status,
    errorMessage || "null"
  ];
  const result = runPgQuery(pythonCode, args);
  if (!result.success || result.stdout !== "ok") {
    return {
      success: false,
      error: result.stderr || result.stdout || "Unknown error"
    };
  }
  return { success: true };
}

// src/patterns/swarm.ts
import { existsSync } from "fs";

// src/shared/db-utils.ts
import { spawnSync as spawnSync2 } from "child_process";
import { join as join2 } from "path";
function getDbPath() {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  return join2(
    projectDir,
    ".claude",
    "cache",
    "agentica-coordination",
    "coordination.db"
  );
}
function runPythonQuery(script, args) {
  try {
    const result = spawnSync2("python3", ["-c", script, ...args], {
      encoding: "utf-8",
      maxBuffer: 1024 * 1024
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

// src/patterns/swarm.ts
async function onSubagentStop(input) {
  const swarmId = process.env.SWARM_ID;
  if (!swarmId) {
    return { result: "continue" };
  }
  if (!isValidId(swarmId)) {
    return { result: "continue" };
  }
  const agentId = input.agent_id ?? "unknown";
  if (!isValidId(agentId)) {
    return { result: "continue" };
  }
  const dbPath = getDbPath();
  if (!existsSync(dbPath)) {
    return { result: "continue" };
  }
  try {
    const query = `
import sqlite3
import json
import sys
from datetime import datetime
from uuid import uuid4

db_path = sys.argv[1]
swarm_id = sys.argv[2]
agent_id = sys.argv[3]

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Insert done broadcast with auto flag
broadcast_id = uuid4().hex[:12]
conn.execute('''
    INSERT INTO broadcasts (id, swarm_id, sender_agent, broadcast_type, payload, created_at)
    VALUES (?, ?, ?, 'done', '{"auto": true}', ?)
''', (broadcast_id, swarm_id, agent_id, datetime.now().isoformat()))
conn.commit()

# Count agents that have broadcast "done" - distinct sender_agent
cursor = conn.execute('''
    SELECT COUNT(DISTINCT sender_agent) as done_count
    FROM broadcasts
    WHERE swarm_id = ? AND broadcast_type = 'done'
''', (swarm_id,))
done_count = cursor.fetchone()[0]

# Count total agents - any agent that has ever broadcast anything in this swarm
cursor = conn.execute('''
    SELECT COUNT(DISTINCT sender_agent) as total_count
    FROM broadcasts
    WHERE swarm_id = ?
''', (swarm_id,))
total_count = cursor.fetchone()[0]

conn.close()
print(json.dumps({'done': done_count, 'total': total_count}))
`;
    const result = runPythonQuery(query, [dbPath, swarmId, agentId]);
    if (!result.success) {
      console.error("SubagentStop Python error:", result.stderr);
      return { result: "continue" };
    }
    let counts;
    try {
      counts = JSON.parse(result.stdout);
    } catch (parseErr) {
      return { result: "continue" };
    }
    console.error(`[subagent-stop] Agent ${agentId} done. Progress: ${counts.done}/${counts.total}`);
    if (counts.done >= counts.total && counts.total > 0) {
      return {
        result: "continue",
        message: "All agents complete. Consider synthesizing findings into final report."
      };
    }
    return { result: "continue" };
  } catch (err) {
    console.error("SubagentStop hook error:", err);
    return { result: "continue" };
  }
}

// src/patterns/jury.ts
import { existsSync as existsSync2 } from "fs";
async function onSubagentStop2(input) {
  const juryId = process.env.JURY_ID;
  if (!juryId) {
    return { result: "continue" };
  }
  if (!isValidId(juryId)) {
    return { result: "continue" };
  }
  const jurorId = input.agent_id ?? "unknown";
  if (!isValidId(jurorId)) {
    return { result: "continue" };
  }
  const jurorIndex = process.env.JUROR_INDEX || "0";
  const totalJurors = parseInt(process.env.TOTAL_JURORS || "1", 10);
  const dbPath = getDbPath();
  if (!existsSync2(dbPath)) {
    return { result: "continue" };
  }
  try {
    const query = `
import sqlite3
import json
import sys
from datetime import datetime
from uuid import uuid4

db_path = sys.argv[1]
jury_id = sys.argv[2]
juror_id = sys.argv[3]
juror_index = sys.argv[4]

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Create table if not exists
conn.execute('''
    CREATE TABLE IF NOT EXISTS jury_votes (
        id TEXT PRIMARY KEY,
        jury_id TEXT NOT NULL,
        juror_id TEXT NOT NULL,
        vote TEXT,
        created_at TEXT NOT NULL,
        completed BOOLEAN DEFAULT 0
    )
''')
conn.execute('''
    CREATE INDEX IF NOT EXISTS idx_jury_votes
        ON jury_votes(jury_id, completed)
''')

# Insert or update vote completion
vote_id = f"{jury_id}_{juror_index}"
conn.execute('''
    INSERT OR REPLACE INTO jury_votes (id, jury_id, juror_id, vote, created_at, completed)
    VALUES (?, ?, ?, NULL, ?, 1)
''', (vote_id, jury_id, juror_id, datetime.now().isoformat()))
conn.commit()

# Count completed jurors
cursor = conn.execute('''
    SELECT COUNT(*) as completed_count
    FROM jury_votes
    WHERE jury_id = ? AND completed = 1
''', (jury_id,))
completed_count = cursor.fetchone()[0]

conn.close()
print(json.dumps({'completed': completed_count}))
`;
    const result = runPythonQuery(query, [dbPath, juryId, jurorId, jurorIndex]);
    if (!result.success) {
      console.error("SubagentStop Python error:", result.stderr);
      return { result: "continue" };
    }
    let counts;
    try {
      counts = JSON.parse(result.stdout);
    } catch (parseErr) {
      return { result: "continue" };
    }
    console.error(`[jury] Juror ${jurorId} done. Progress: ${counts.completed}/${totalJurors}`);
    if (counts.completed >= totalJurors && totalJurors > 0) {
      return {
        result: "continue",
        message: "All jurors have completed their deliberations. Review the votes and provide your final verdict."
      };
    }
    return { result: "continue" };
  } catch (err) {
    console.error("SubagentStop hook error:", err);
    return { result: "continue" };
  }
}

// src/patterns/hierarchical.ts
import { existsSync as existsSync3 } from "fs";
async function onSubagentStop3(input) {
  const hierarchyId = process.env.HIERARCHY_ID;
  if (!hierarchyId) {
    return { result: "continue" };
  }
  if (!isValidId(hierarchyId)) {
    return { result: "continue" };
  }
  const agentId = input.agent_id ?? "unknown";
  if (!isValidId(agentId)) {
    return { result: "continue" };
  }
  const agentRole = process.env.AGENT_ROLE || "specialist";
  const coordinatorId = process.env.COORDINATOR_ID;
  const hierarchyLevel = parseInt(process.env.HIERARCHY_LEVEL || "1", 10);
  const dbPath = getDbPath();
  if (!existsSync3(dbPath)) {
    return { result: "continue" };
  }
  if (agentRole !== "specialist") {
    return { result: "continue" };
  }
  try {
    const query = `
import sqlite3
import json
import sys
from datetime import datetime

db_path = sys.argv[1]
hierarchy_id = sys.argv[2]
agent_id = sys.argv[3]
coordinator_id = sys.argv[4]
level = int(sys.argv[5])

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Create table if not exists
conn.execute('''
    CREATE TABLE IF NOT EXISTS hierarchy_agents (
        id TEXT PRIMARY KEY,
        hierarchy_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        role TEXT NOT NULL,
        coordinator_id TEXT,
        level INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active',
        created_at TEXT NOT NULL
    )
''')
conn.execute('''
    CREATE INDEX IF NOT EXISTS idx_hierarchy_agents
        ON hierarchy_agents(hierarchy_id, status)
''')

# Update or insert specialist status
specialist_id = f"{hierarchy_id}_{agent_id}"
conn.execute('''
    INSERT OR REPLACE INTO hierarchy_agents
        (id, hierarchy_id, agent_id, role, coordinator_id, level, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
''', (specialist_id, hierarchy_id, agent_id, 'specialist', coordinator_id, level, 'completed'))
conn.commit()

# Count completed specialists for this hierarchy
cursor = conn.execute('''
    SELECT COUNT(*) as completed_count
    FROM hierarchy_agents
    WHERE hierarchy_id = ? AND role = 'specialist' AND status = 'completed'
''', (hierarchy_id,))
completed_count = cursor.fetchone()[0]

# Count total specialists for this hierarchy
cursor = conn.execute('''
    SELECT COUNT(*) as total_count
    FROM hierarchy_agents
    WHERE hierarchy_id = ? AND role = 'specialist'
''', (hierarchy_id,))
total_count = cursor.fetchone()[0]

conn.close()
print(json.dumps({'completed': completed_count, 'total': total_count}))
`;
    const result = runPythonQuery(query, [
      dbPath,
      hierarchyId,
      agentId,
      coordinatorId || "",
      hierarchyLevel.toString()
    ]);
    if (!result.success) {
      console.error("SubagentStop Python error:", result.stderr);
      return { result: "continue" };
    }
    let counts;
    try {
      counts = JSON.parse(result.stdout);
    } catch (parseErr) {
      return { result: "continue" };
    }
    console.error(`[hierarchical] Specialist ${agentId} done. Progress: ${counts.completed}/${counts.total}`);
    if (counts.completed >= counts.total && counts.total > 0) {
      return {
        result: "continue",
        message: `All ${counts.total} specialists have completed their subtasks. Ready for synthesis.`
      };
    } else {
      const remaining = counts.total - counts.completed;
      return {
        result: "continue",
        message: `Specialist completed. Waiting for ${remaining} more specialist(s) to finish.`
      };
    }
  } catch (err) {
    console.error("SubagentStop hook error:", err);
    return { result: "continue" };
  }
}

// src/patterns/generator-critic.ts
import { existsSync as existsSync4 } from "fs";
async function onSubagentStop4(input) {
  const gcId = process.env.GC_ID;
  if (!gcId) {
    return { result: "continue" };
  }
  if (!isValidId(gcId)) {
    return { result: "continue" };
  }
  const role = process.env.AGENT_ROLE || "unknown";
  const iteration = parseInt(process.env.GC_ITERATION || "1", 10);
  const dbPath = getDbPath();
  if (!existsSync4(dbPath)) {
    return { result: "continue" };
  }
  try {
    const query = `
import sqlite3
import json
import sys
from datetime import datetime

db_path = sys.argv[1]
gc_id = sys.argv[2]
iteration = int(sys.argv[3])
role = sys.argv[4]

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Create table if not exists
conn.execute('''
    CREATE TABLE IF NOT EXISTS gc_iterations (
        id TEXT PRIMARY KEY,
        gc_id TEXT NOT NULL,
        iteration INTEGER NOT NULL,
        generator_output TEXT,
        critic_feedback TEXT,
        approved BOOLEAN DEFAULT 0,
        created_at TEXT NOT NULL
    )
''')
conn.execute('''
    CREATE INDEX IF NOT EXISTS idx_gc_iterations
        ON gc_iterations(gc_id, iteration)
''')

# Record iteration completion
iter_id = f"{gc_id}_iter_{iteration}"
now = datetime.now().isoformat()

# Check if iteration exists
cursor = conn.execute(
    "SELECT id FROM gc_iterations WHERE id = ?",
    (iter_id,)
)
exists = cursor.fetchone() is not None

if not exists:
    conn.execute('''
        INSERT INTO gc_iterations (id, gc_id, iteration, created_at)
        VALUES (?, ?, ?, ?)
    ''', (iter_id, gc_id, iteration, now))
else:
    # Update existing record based on role
    if role == "generator":
        conn.execute('''
            UPDATE gc_iterations
            SET generator_output = ?
            WHERE id = ?
        ''', ("(output recorded)", iter_id))
    elif role == "critic":
        conn.execute('''
            UPDATE gc_iterations
            SET critic_feedback = ?
            WHERE id = ?
        ''', ("(feedback recorded)", iter_id))

conn.commit()
conn.close()

print(json.dumps({'success': True}))
`;
    const result = runPythonQuery(query, [dbPath, gcId, iteration.toString(), role]);
    if (!result.success) {
      console.error("SubagentStop Python error:", result.stderr);
      return { result: "continue" };
    }
    console.error(`[gc] ${role} completed iteration ${iteration}`);
    return { result: "continue" };
  } catch (err) {
    console.error("SubagentStop hook error:", err);
    return { result: "continue" };
  }
}

// src/patterns/blackboard.ts
import { existsSync as existsSync5 } from "fs";
async function onSubagentStop5(input) {
  const blackboardId = process.env.BLACKBOARD_ID;
  if (!blackboardId) {
    return { result: "continue" };
  }
  if (!isValidId(blackboardId)) {
    return { result: "continue" };
  }
  const agentId = input.agent_id ?? "unknown";
  if (!isValidId(agentId)) {
    return { result: "continue" };
  }
  const role = process.env.AGENT_ROLE || "specialist";
  const dbPath = getDbPath();
  if (!existsSync5(dbPath)) {
    return { result: "continue" };
  }
  try {
    const query = `
import sqlite3
import sys
from datetime import datetime

db_path = sys.argv[1]
blackboard_id = sys.argv[2]
agent_id = sys.argv[3]
role = sys.argv[4]

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Create table if not exists
conn.execute('''
    CREATE TABLE IF NOT EXISTS blackboard_state (
        id TEXT PRIMARY KEY,
        blackboard_id TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT,
        updated_by TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(blackboard_id, key)
    )
''')

# Record that this agent contributed (even if no specific keys written yet)
# This is just a marker that the specialist finished
state_id = f"{blackboard_id}_{agent_id}_completed"
conn.execute('''
    INSERT OR REPLACE INTO blackboard_state (id, blackboard_id, key, value, updated_by, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
''', (state_id, blackboard_id, f"_completed_{agent_id}", "true", agent_id, datetime.now().isoformat()))
conn.commit()
conn.close()
`;
    const result = runPythonQuery(query, [dbPath, blackboardId, agentId, role]);
    if (!result.success) {
      console.error("SubagentStop Python error:", result.stderr);
      return { result: "continue" };
    }
    console.error(`[blackboard] ${role} ${agentId} completed contribution`);
    return { result: "continue" };
  } catch (err) {
    console.error("SubagentStop hook error:", err);
    return { result: "continue" };
  }
}

// src/patterns/circuit-breaker.ts
import { existsSync as existsSync6 } from "fs";
async function onSubagentStop6(input) {
  const cbId = process.env.CB_ID;
  if (!cbId) {
    return { result: "continue" };
  }
  if (!isValidId(cbId)) {
    return { result: "continue" };
  }
  const agentId = input.agent_id ?? "unknown";
  if (!isValidId(agentId)) {
    return { result: "continue" };
  }
  const role = process.env.AGENT_ROLE || "primary";
  const dbPath = getDbPath();
  if (!existsSync6(dbPath)) {
    return { result: "continue" };
  }
  try {
    const query = `
import sqlite3
import json
import sys

db_path = sys.argv[1]
cb_id = sys.argv[2]

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Create table if not exists
conn.execute('''
    CREATE TABLE IF NOT EXISTS circuit_state (
        id TEXT PRIMARY KEY,
        cb_id TEXT NOT NULL,
        state TEXT DEFAULT 'closed',
        failure_count INTEGER DEFAULT 0,
        last_failure_at TEXT,
        created_at TEXT NOT NULL
    )
''')

# Get current circuit state
cursor = conn.execute('''
    SELECT state, failure_count
    FROM circuit_state
    WHERE cb_id = ?
''', (cb_id,))
row = cursor.fetchone()

if row:
    state, failure_count = row
else:
    state = 'closed'
    failure_count = 0

conn.close()
print(json.dumps({'state': state, 'failure_count': failure_count}))
`;
    const result = runPythonQuery(query, [dbPath, cbId]);
    if (!result.success) {
      console.error("SubagentStop Python error:", result.stderr);
      return { result: "continue" };
    }
    let state;
    try {
      state = JSON.parse(result.stdout);
    } catch (parseErr) {
      return { result: "continue" };
    }
    console.error(`[circuit-breaker] Agent ${agentId} (${role}) completed. Circuit state: ${state.state} (failures: ${state.failure_count})`);
    return { result: "continue" };
  } catch (err) {
    console.error("SubagentStop hook error:", err);
    return { result: "continue" };
  }
}

// src/patterns/map-reduce.ts
import { existsSync as existsSync7 } from "fs";
async function onSubagentStop7(input) {
  const mrId = process.env.MR_ID;
  if (!mrId) {
    return { result: "continue" };
  }
  if (!isValidId(mrId)) {
    return { result: "continue" };
  }
  const agentRole = process.env.AGENT_ROLE || "mapper";
  if (agentRole !== "mapper") {
    return { result: "continue" };
  }
  const mapperId = input.agent_id ?? "unknown";
  if (!isValidId(mapperId)) {
    return { result: "continue" };
  }
  const mapperIndex = parseInt(process.env.MAPPER_INDEX || "0", 10);
  const totalMappers = parseInt(process.env.TOTAL_MAPPERS || "1", 10);
  const dbPath = getDbPath();
  if (!existsSync7(dbPath)) {
    return { result: "continue" };
  }
  try {
    const query = `
import sqlite3
import json
import sys
from datetime import datetime

db_path = sys.argv[1]
mr_id = sys.argv[2]
mapper_id = sys.argv[3]
mapper_index = sys.argv[4]

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Create table if not exists
conn.execute('''
    CREATE TABLE IF NOT EXISTS mr_mappers (
        id TEXT PRIMARY KEY,
        mr_id TEXT NOT NULL,
        mapper_index INTEGER NOT NULL,
        agent_id TEXT,
        status TEXT DEFAULT 'pending',
        output TEXT,
        created_at TEXT NOT NULL
    )
''')
conn.execute('''
    CREATE INDEX IF NOT EXISTS idx_mr_mappers
        ON mr_mappers(mr_id, status)
''')

# Insert or update mapper completion
record_id = f"{mr_id}_{mapper_index}"
conn.execute('''
    INSERT OR REPLACE INTO mr_mappers (id, mr_id, mapper_index, agent_id, status, output, created_at)
    VALUES (?, ?, ?, ?, 'completed', NULL, ?)
''', (record_id, mr_id, mapper_index, mapper_id, datetime.now().isoformat()))
conn.commit()

# Count completed mappers
cursor = conn.execute('''
    SELECT COUNT(*) as completed_count
    FROM mr_mappers
    WHERE mr_id = ? AND status = 'completed'
''', (mr_id,))
completed_count = cursor.fetchone()[0]

conn.close()
print(json.dumps({'completed': completed_count}))
`;
    const result = runPythonQuery(query, [dbPath, mrId, mapperId, mapperIndex.toString()]);
    if (!result.success) {
      console.error("SubagentStop Python error:", result.stderr);
      return { result: "continue" };
    }
    let counts;
    try {
      counts = JSON.parse(result.stdout);
    } catch (parseErr) {
      return { result: "continue" };
    }
    console.error(`[map-reduce] Mapper ${mapperId} done. Progress: ${counts.completed}/${totalMappers}`);
    if (counts.completed >= totalMappers && totalMappers > 0) {
      return {
        result: "continue",
        message: "All mappers have completed. Proceeding to reduce phase."
      };
    }
    return { result: "continue" };
  } catch (err) {
    console.error("SubagentStop hook error:", err);
    return { result: "continue" };
  }
}

// src/patterns/chain-of-responsibility.ts
import { existsSync as existsSync8 } from "fs";
async function onSubagentStop8(input) {
  const corId = process.env.COR_ID;
  if (!corId) {
    return { result: "continue" };
  }
  if (!isValidId(corId)) {
    return { result: "continue" };
  }
  const handlerId = input.agent_id ?? "unknown";
  if (!isValidId(handlerId)) {
    return { result: "continue" };
  }
  const handlerPriority = parseInt(process.env.HANDLER_PRIORITY || "0", 10);
  const escalate = process.env.COR_ESCALATE === "true";
  const dbPath = getDbPath();
  if (!existsSync8(dbPath)) {
    return { result: "continue" };
  }
  try {
    const query = `
import sqlite3
import json
import sys
from datetime import datetime

db_path = sys.argv[1]
cor_id = sys.argv[2]
handler_id = sys.argv[3]
priority = int(sys.argv[4])
escalate = sys.argv[5] == 'true'

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Create table if not exists
conn.execute('''
    CREATE TABLE IF NOT EXISTS cor_handlers (
        id TEXT PRIMARY KEY,
        cor_id TEXT NOT NULL,
        priority INTEGER NOT NULL,
        agent_id TEXT,
        handled BOOLEAN DEFAULT 0,
        escalated BOOLEAN DEFAULT 0,
        created_at TEXT NOT NULL
    )
''')
conn.execute('''
    CREATE INDEX IF NOT EXISTS idx_cor_handlers
        ON cor_handlers(cor_id, priority)
''')

# Insert or update handler completion
handler_record_id = f"{cor_id}_{priority}"
handled = 0 if escalate else 1
escalated = 1 if escalate else 0

conn.execute('''
    INSERT OR REPLACE INTO cor_handlers
    (id, cor_id, priority, agent_id, handled, escalated, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
''', (handler_record_id, cor_id, priority, handler_id, handled, escalated, datetime.now().isoformat()))
conn.commit()

conn.close()
print(json.dumps({'success': True, 'handled': handled, 'escalated': escalated}))
`;
    const result = runPythonQuery(query, [
      dbPath,
      corId,
      handlerId,
      handlerPriority.toString(),
      escalate ? "true" : "false"
    ]);
    if (!result.success) {
      console.error("SubagentStop Python error:", result.stderr);
      return { result: "continue" };
    }
    const action = escalate ? "escalated" : "handled";
    console.error(`[chain-of-responsibility] Handler ${handlerPriority} ${action} request`);
    return { result: "continue" };
  } catch (err) {
    console.error("SubagentStop hook error:", err);
    return { result: "continue" };
  }
}

// src/patterns/event-driven.ts
import { existsSync as existsSync9 } from "fs";
async function onSubagentStop9(input) {
  const busId = process.env.EVENT_BUS_ID;
  if (!busId) {
    return { result: "continue" };
  }
  if (!isValidId(busId)) {
    return { result: "continue" };
  }
  const agentRole = process.env.AGENT_ROLE;
  const agentId = input.agent_id ?? "unknown";
  if (!isValidId(agentId)) {
    return { result: "continue" };
  }
  if (agentRole !== "subscriber") {
    return { result: "continue" };
  }
  const dbPath = getDbPath();
  if (!existsSync9(dbPath)) {
    return { result: "continue" };
  }
  try {
    const query = `
import sqlite3
import json
import sys

db_path = sys.argv[1]
bus_id = sys.argv[2]
agent_id = sys.argv[3]

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Delete subscription
conn.execute('''
    DELETE FROM event_subscriptions
    WHERE bus_id = ? AND agent_id = ?
''', (bus_id, agent_id))
conn.commit()

deleted = conn.total_changes
conn.close()

print(json.dumps({'deleted': deleted}))
`;
    const result = runPythonQuery(query, [dbPath, busId, agentId]);
    if (!result.success) {
      console.error("SubagentStop Python error:", result.stderr);
      return { result: "continue" };
    }
    console.error(`[event-driven] Unsubscribed agent ${agentId}`);
    return { result: "continue" };
  } catch (err) {
    console.error("SubagentStop hook error:", err);
    return { result: "continue" };
  }
}

// src/patterns/adversarial.ts
async function onSubagentStop10(input) {
  const advId = process.env.ADV_ID;
  if (!advId) {
    return { result: "continue" };
  }
  if (!isValidId(advId)) {
    return { result: "continue" };
  }
  const role = process.env.AGENT_ROLE || "unknown";
  const round = parseInt(process.env.ADVERSARIAL_ROUND || "1", 10);
  const maxRounds = parseInt(process.env.ADVERSARIAL_MAX_ROUNDS || "3", 10);
  console.error(`[adversarial] ${role} completed round ${round}/${maxRounds}`);
  if (round < maxRounds) {
    return {
      result: "continue",
      message: `Round ${round} of ${maxRounds} complete. Prepare for next round of debate.`
    };
  } else if (round === maxRounds && role !== "judge") {
    return {
      result: "continue",
      message: `All ${maxRounds} debate rounds complete. Ready for judge's verdict.`
    };
  }
  return { result: "continue" };
}

// src/subagent-stop.ts
function handlePipeline(input) {
  const stageIndex = process.env.PIPELINE_STAGE_INDEX;
  const totalStages = process.env.PIPELINE_TOTAL_STAGES;
  const pipelineId = process.env.PATTERN_ID;
  console.error(
    `[pipeline] Stage ${stageIndex} of ${totalStages} completed for pipeline ${pipelineId}`
  );
  return { result: "continue" };
}
async function main() {
  let input;
  try {
    const rawInput = readFileSync(0, "utf-8");
    if (!rawInput.trim()) {
      console.log(JSON.stringify({ result: "continue" }));
      return;
    }
    input = JSON.parse(rawInput);
  } catch (err) {
    console.log(JSON.stringify({ result: "continue" }));
    return;
  }
  const agentId = input.agent_id || input.session_id;
  if (agentId) {
    const result = completeAgentPg(agentId, "completed");
    if (!result.success) {
      console.error(`[subagent-stop] Failed to complete agent: ${result.error}`);
    }
  }
  const pattern = detectPattern();
  let output;
  switch (pattern) {
    case "swarm":
      output = await onSubagentStop(input);
      break;
    case "jury":
      output = await onSubagentStop2(input);
      break;
    case "pipeline":
      output = handlePipeline(input);
      break;
    case "generator_critic":
      output = await onSubagentStop4(input);
      break;
    case "hierarchical":
      output = await onSubagentStop3(input);
      break;
    case "map_reduce":
      output = await onSubagentStop7(input);
      break;
    case "blackboard":
      output = await onSubagentStop5(input);
      break;
    case "circuit_breaker":
      output = await onSubagentStop6(input);
      break;
    case "chain_of_responsibility":
      output = await onSubagentStop8(input);
      break;
    case "adversarial":
      output = await onSubagentStop10(input);
      break;
    case "event_driven":
      output = await onSubagentStop9(input);
      break;
    default:
      output = { result: "continue" };
  }
  console.log(JSON.stringify(output));
}
main().catch((err) => {
  console.error("Uncaught error:", err);
  console.log(JSON.stringify({ result: "continue" }));
});
