// src/subagent-start.ts
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
function registerAgentPg(agentId, sessionId, pattern = null, pid = null) {
  const pythonCode = `
from scripts.agentica_patterns.coordination_pg import CoordinationDBPg
import json

agent_id = sys.argv[1]
session_id = sys.argv[2]
pattern = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != 'null' else None
pid = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] != 'null' else None

async def main():
    try:
        async with CoordinationDBPg() as db:
            await db.register_agent(
                agent_id=agent_id,
                session_id=session_id,
                pattern=pattern,
                pid=pid
            )
        print('ok')
    except Exception as e:
        print(f'error: {e}')

asyncio.run(main())
`;
  const args = [
    agentId,
    sessionId,
    pattern || "null",
    pid !== null ? String(pid) : "null"
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
async function onSubagentStart(input) {
  const swarmId = process.env.SWARM_ID;
  if (!swarmId) {
    return { result: "continue" };
  }
  if (!isValidId(swarmId)) {
    return { result: "continue" };
  }
  const agentId = input.agent_id ?? "unknown";
  const agentType = input.agent_type ?? "unknown";
  console.error(`[subagent-start] Agent ${agentId} (type: ${agentType}) joining swarm ${swarmId}`);
  return { result: "continue" };
}

// src/patterns/jury.ts
async function onSubagentStart2(input) {
  const juryId = process.env.JURY_ID;
  if (!juryId) {
    return { result: "continue" };
  }
  if (!isValidId(juryId)) {
    return { result: "continue" };
  }
  const jurorIndex = process.env.JUROR_INDEX || "0";
  const totalJurors = process.env.TOTAL_JURORS || "1";
  const isolation = process.env.JURY_ISOLATION;
  console.error(`[jury] Juror ${jurorIndex} of ${totalJurors} starting for jury ${juryId}`);
  let message = `You are Juror ${jurorIndex} (position ${parseInt(jurorIndex) + 1} of ${totalJurors}) in an independent jury panel.`;
  message += " Vote based solely on your own analysis.";
  message += " Do not attempt to coordinate with or influence other jurors.";
  if (isolation === "strict") {
    message += " STRICT ISOLATION: Your vote will be recorded independently.";
  }
  return {
    result: "continue",
    message
  };
}

// src/patterns/hierarchical.ts
async function onSubagentStart3(input) {
  const hierarchyId = process.env.HIERARCHY_ID;
  if (!hierarchyId) {
    return { result: "continue" };
  }
  if (!isValidId(hierarchyId)) {
    return { result: "continue" };
  }
  const agentRole = process.env.AGENT_ROLE || "specialist";
  const hierarchyLevel = process.env.HIERARCHY_LEVEL || "1";
  const coordinatorId = process.env.COORDINATOR_ID;
  console.error(`[hierarchical] Starting ${agentRole} at level ${hierarchyLevel} for hierarchy ${hierarchyId}`);
  let message = "";
  if (agentRole === "coordinator") {
    message = `You are the coordinator in a hierarchical pattern. `;
    message += "Your role is to decompose complex tasks into subtasks for specialist agents. ";
    message += "Delegate to specialists, then synthesize their results into a comprehensive answer.";
  } else {
    message = `You are a specialist in a hierarchical pattern (level ${hierarchyLevel}). `;
    message += "Focus on executing your assigned subtask thoroughly. ";
    message += "Your results will be aggregated by the coordinator.";
    if (coordinatorId) {
      message += ` Report to coordinator: ${coordinatorId}`;
    }
  }
  return {
    result: "continue",
    message
  };
}

// src/patterns/generator-critic.ts
async function onSubagentStart4(input) {
  const gcId = process.env.GC_ID;
  if (!gcId) {
    return { result: "continue" };
  }
  if (!isValidId(gcId)) {
    return { result: "continue" };
  }
  const role = process.env.AGENT_ROLE || "unknown";
  const iteration = parseInt(process.env.GC_ITERATION || "1", 10);
  const maxRounds = parseInt(process.env.GC_MAX_ROUNDS || "3", 10);
  console.error(`[gc] ${role} starting for iteration ${iteration}/${maxRounds} (${gcId})`);
  let message = "";
  if (role === "generator") {
    message = `You are the GENERATOR in an iterative refinement loop (iteration ${iteration}/${maxRounds}). `;
    if (iteration === 1) {
      message += "Create an initial solution to the task.";
    } else {
      message += "Refine your previous output based on critic feedback.";
    }
  } else if (role === "critic") {
    message = `You are the CRITIC in an iterative refinement loop (iteration ${iteration}/${maxRounds}). `;
    message += "Review the generator's output and provide constructive feedback. ";
    message += 'If the output meets all requirements, include "APPROVED" in your response.';
  } else {
    message = `Generator-Critic pattern active (iteration ${iteration}/${maxRounds}).`;
  }
  return {
    result: "continue",
    message
  };
}

// src/patterns/blackboard.ts
async function onSubagentStart5(input) {
  const blackboardId = process.env.BLACKBOARD_ID;
  if (!blackboardId) {
    return { result: "continue" };
  }
  if (!isValidId(blackboardId)) {
    return { result: "continue" };
  }
  const role = process.env.AGENT_ROLE || "specialist";
  const writesTo = process.env.BLACKBOARD_WRITES_TO || "";
  const readsFrom = process.env.BLACKBOARD_READS_FROM || "";
  console.error(`[blackboard] ${role} starting for blackboard ${blackboardId}`);
  let message = "";
  if (role === "controller") {
    message = "You are the controller for this blackboard pattern.";
    message += " Review the final blackboard state and determine if the solution is complete and coherent.";
    message += " Approve only when all required information is present and consistent.";
  } else {
    message = `You are a specialist in the blackboard pattern.`;
    if (writesTo) {
      const keys = writesTo.split(",").map((k) => k.trim()).filter((k) => k);
      message += `

You are responsible for writing to these blackboard keys: ${keys.join(", ")}`;
    }
    if (readsFrom) {
      const keys = readsFrom.split(",").map((k) => k.trim()).filter((k) => k);
      message += `

You may read from these blackboard keys: ${keys.join(", ")}`;
    }
    message += "\n\nProvide your contribution based on the current blackboard state.";
    message += " Focus on your assigned keys and build upon work from other specialists.";
  }
  return {
    result: "continue",
    message
  };
}

// src/patterns/circuit-breaker.ts
async function onSubagentStart6(input) {
  const cbId = process.env.CB_ID;
  if (!cbId) {
    return { result: "continue" };
  }
  if (!isValidId(cbId)) {
    return { result: "continue" };
  }
  const role = process.env.AGENT_ROLE || "primary";
  const circuitState = process.env.CIRCUIT_STATE || "closed";
  console.error(`[circuit-breaker] Agent role=${role} state=${circuitState} cb_id=${cbId}`);
  let message = "";
  if (role === "primary") {
    message = `You are the PRIMARY agent in a circuit breaker pattern (circuit state: ${circuitState}).`;
    message += " Your execution is monitored for failures.";
    if (circuitState === "half_open") {
      message += " TESTING MODE: The circuit is testing if you have recovered. A single failure will reopen the circuit.";
    } else if (circuitState === "closed") {
      message += " Normal operation - consecutive failures will open the circuit and route to fallback.";
    }
  } else if (role === "fallback") {
    message = `You are the FALLBACK agent in a circuit breaker pattern.`;
    message += " You are operating in degraded mode as a backup to the primary agent.";
    message += " Provide a simpler or safer implementation.";
  }
  return {
    result: "continue",
    message
  };
}

// src/patterns/map-reduce.ts
async function onSubagentStart7(input) {
  const mrId = process.env.MR_ID;
  if (!mrId) {
    return { result: "continue" };
  }
  if (!isValidId(mrId)) {
    return { result: "continue" };
  }
  const agentRole = process.env.AGENT_ROLE || "mapper";
  const mapperIndex = process.env.MAPPER_INDEX || "0";
  const totalMappers = process.env.TOTAL_MAPPERS || "1";
  console.error(`[map-reduce] ${agentRole} starting for MR ${mrId}`);
  let message = "";
  if (agentRole === "mapper") {
    message = `You are Mapper ${mapperIndex} (position ${parseInt(mapperIndex) + 1} of ${totalMappers}) in a MapReduce execution.`;
    message += " Process your assigned chunk and return results.";
    message += " Your output will be combined with other mappers by the reducer.";
  } else if (agentRole === "reducer") {
    message = `You are the Reducer in a MapReduce execution with ${totalMappers} mappers.`;
    message += " Synthesize the outputs from all mappers into a final result.";
  }
  return {
    result: "continue",
    message: message || void 0
  };
}

// src/patterns/chain-of-responsibility.ts
async function onSubagentStart8(input) {
  const corId = process.env.COR_ID;
  if (!corId) {
    return { result: "continue" };
  }
  if (!isValidId(corId)) {
    return { result: "continue" };
  }
  const handlerPriority = process.env.HANDLER_PRIORITY || "0";
  const chainLength = process.env.CHAIN_LENGTH || "1";
  console.error(`[chain-of-responsibility] Handler ${handlerPriority} starting for chain ${corId}`);
  let message = `You are Handler at priority ${handlerPriority} in a chain of ${chainLength} handlers.`;
  message += " Your task is to determine if you can handle this request using your can_handle predicate.";
  message += " If you can handle it, process the request and return the result.";
  message += " If you cannot handle it, the request will escalate to the next handler in the chain.";
  return {
    result: "continue",
    message
  };
}

// src/patterns/event-driven.ts
import { existsSync } from "fs";
async function onSubagentStart9(input) {
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
  const eventTypesJson = process.env.SUBSCRIBER_EVENT_TYPES;
  if (!eventTypesJson) {
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
bus_id = sys.argv[2]
agent_id = sys.argv[3]
event_types_json = sys.argv[4]

conn = sqlite3.connect(db_path)
# Set busy_timeout to prevent indefinite blocking (Finding 3: STARVATION_FINDINGS.md)
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")

# Create table if not exists
conn.execute('''
    CREATE TABLE IF NOT EXISTS event_subscriptions (
        id TEXT PRIMARY KEY,
        bus_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        event_types TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
''')

# Insert subscription
subscription_id = str(uuid4())
conn.execute('''
    INSERT INTO event_subscriptions (id, bus_id, agent_id, event_types, created_at)
    VALUES (?, ?, ?, ?, ?)
''', (subscription_id, bus_id, agent_id, event_types_json, datetime.now().isoformat()))
conn.commit()
conn.close()

print(json.dumps({'subscription_id': subscription_id}))
`;
    const result = runPythonQuery(query, [dbPath, busId, agentId, eventTypesJson]);
    if (!result.success) {
      console.error("SubagentStart Python error:", result.stderr);
      return { result: "continue" };
    }
    let eventTypes;
    try {
      eventTypes = JSON.parse(eventTypesJson);
    } catch {
      eventTypes = [];
    }
    console.error(`[event-driven] Subscribed agent ${agentId} to events: ${eventTypes.join(", ")}`);
    return {
      result: "continue",
      message: `Subscribed to event types: ${eventTypes.join(", ")}`
    };
  } catch (err) {
    console.error("SubagentStart hook error:", err);
    return { result: "continue" };
  }
}

// src/patterns/adversarial.ts
async function onSubagentStart10(input) {
  const advId = process.env.ADV_ID;
  if (!advId) {
    return { result: "continue" };
  }
  if (!isValidId(advId)) {
    return { result: "continue" };
  }
  const role = process.env.AGENT_ROLE || "unknown";
  const round = process.env.ADVERSARIAL_ROUND || "1";
  const maxRounds = process.env.ADVERSARIAL_MAX_ROUNDS || "3";
  console.error(`[adversarial] ${role} starting round ${round}/${maxRounds} for debate ${advId}`);
  let message = "";
  if (role === "advocate") {
    message = `You are the ADVOCATE in round ${round} of ${maxRounds}.`;
    message += " Present arguments in favor of the position.";
    message += " Be persuasive, thorough, and address critiques from previous rounds.";
  } else if (role === "adversary") {
    message = `You are the ADVERSARY in round ${round} of ${maxRounds}.`;
    message += " Critique and attack the advocate's arguments.";
    message += " Find flaws, weaknesses, and counterarguments.";
  } else if (role === "judge") {
    message = `You are the JUDGE evaluating the complete debate.`;
    message += " Review both positions objectively and decide which is stronger.";
    message += " Provide your verdict with clear reasoning.";
  }
  return {
    result: "continue",
    message
  };
}

// src/patterns/pipeline.ts
async function onSubagentStart11(input) {
  const pipelineId = process.env.PIPELINE_ID;
  if (!pipelineId) {
    return { result: "continue" };
  }
  if (!isValidId(pipelineId)) {
    return { result: "continue" };
  }
  const stageIndex = parseInt(process.env.PIPELINE_STAGE_INDEX || "0", 10);
  const totalStages = parseInt(process.env.PIPELINE_TOTAL_STAGES || "1", 10);
  console.error(`[pipeline] Stage ${stageIndex} of ${totalStages} starting for pipeline ${pipelineId}`);
  let message = `You are Stage ${stageIndex + 1} of ${totalStages} in a pipeline.`;
  if (stageIndex === 0) {
    message += " This is the first stage. Process the initial input and pass your output to the next stage.";
  } else if (stageIndex === totalStages - 1) {
    message += " This is the final stage. Process the upstream outputs and produce the final result.";
  } else {
    message += " Process the upstream outputs and pass your results to the next stage.";
  }
  return {
    result: "continue",
    message
  };
}

// src/subagent-start.ts
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
  const pattern = detectPattern() || "task";
  const agentId = input.agent_id || input.session_id;
  if (agentId) {
    const result = registerAgentPg(
      agentId,
      input.session_id,
      pattern,
      process.pid
    );
    if (!result.success) {
      console.error(`[subagent-start] Failed to register agent: ${result.error}`);
    }
  }
  let output;
  switch (pattern) {
    case "swarm":
      output = await onSubagentStart(input);
      break;
    case "jury":
      output = await onSubagentStart2(input);
      break;
    case "pipeline":
      output = await onSubagentStart11(input);
      break;
    case "generator_critic":
      output = await onSubagentStart4(input);
      break;
    case "hierarchical":
      output = await onSubagentStart3(input);
      break;
    case "map_reduce":
      output = await onSubagentStart7(input);
      break;
    case "blackboard":
      output = await onSubagentStart5(input);
      break;
    case "circuit_breaker":
      output = await onSubagentStart6(input);
      break;
    case "chain_of_responsibility":
      output = await onSubagentStart8(input);
      break;
    case "adversarial":
      output = await onSubagentStart10(input);
      break;
    case "event_driven":
      output = await onSubagentStart9(input);
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
