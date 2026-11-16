/**
 * Pre-tool-use hook for blackboard polling.
 *
 * Polls the blackboard cache and injects relevant entries as a system reminder.
 * This enables agent-to-agent communication without breaking Claude's expectations.
 *
 * Flow:
 * 1. Check if agent has pattern_id in environment
 * 2. Read last poll timestamp from state
 * 3. Poll blackboard for new entries since last poll
 * 4. Format as system reminder and inject
 * 5. Update last poll timestamp
 */

import * as fs from "fs";
import * as path from "path";

interface PreToolUseInput {
  session_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
}

interface HookOutput {
  result: "continue" | "block";
  message?: string;
}

interface BlackboardEntry {
  id: string;
  project_id: string;
  scope: string;
  type: string;
  from_agent: string;
  to_agent?: string;
  pattern_id?: string;
  formal?: string;
  prose?: string;
  data: Record<string, unknown>;
  artifacts: string[];
  priority: string;
  timestamp: string;
  ttl_seconds?: number;
  parent_id?: string;
}

// Configuration
const BLACKBOARD_CACHE_DIR =
  process.env.BLACKBOARD_CACHE_DIR || "/tmp/claude-blackboard";
const POLL_STATE_DIR =
  process.env.POLL_STATE_DIR || "/tmp/claude-blackboard/poll-state";
const MAX_ENTRIES_IN_REMINDER = 5;

// Get agent context from environment
function getAgentContext(): {
  agentId: string | null;
  patternId: string | null;
  projectId: string | null;
} {
  return {
    agentId: process.env.CLAUDE_AGENT_ID || null,
    patternId: process.env.CLAUDE_PATTERN_ID || null,
    projectId: process.env.CLAUDE_PROJECT_ID || null,
  };
}

// Read last poll timestamp
function getLastPollTimestamp(sessionId: string): string | null {
  const stateFile = path.join(POLL_STATE_DIR, `${sessionId}.json`);
  try {
    if (fs.existsSync(stateFile)) {
      const state = JSON.parse(fs.readFileSync(stateFile, "utf-8"));
      return state.last_poll_timestamp || null;
    }
  } catch {
    // Ignore errors, treat as no previous poll
  }
  return null;
}

// Save last poll timestamp
function saveLastPollTimestamp(
  sessionId: string,
  timestamp: string
): void {
  fs.mkdirSync(POLL_STATE_DIR, { recursive: true });
  const stateFile = path.join(POLL_STATE_DIR, `${sessionId}.json`);
  fs.writeFileSync(
    stateFile,
    JSON.stringify({ last_poll_timestamp: timestamp }, null, 2)
  );
}

// Read blackboard cache
function readBlackboardCache(projectId: string): BlackboardEntry[] {
  const cacheFile = path.join(BLACKBOARD_CACHE_DIR, `${projectId}.json`);
  try {
    if (fs.existsSync(cacheFile)) {
      return JSON.parse(fs.readFileSync(cacheFile, "utf-8"));
    }
  } catch {
    // Ignore errors
  }
  return [];
}

// Filter entries for this agent
function filterEntries(
  entries: BlackboardEntry[],
  agentId: string | null,
  patternId: string | null,
  sinceTimestamp: string | null
): BlackboardEntry[] {
  const now = Date.now();

  return entries.filter((e) => {
    // Filter expired entries
    if (e.ttl_seconds) {
      const entryTime = new Date(e.timestamp).getTime();
      const age = (now - entryTime) / 1000;
      if (age > e.ttl_seconds) {
        return false;
      }
    }

    // Filter by timestamp
    if (sinceTimestamp && e.timestamp <= sinceTimestamp) {
      return false;
    }

    // Filter by pattern (for SHARED scope)
    if (patternId && e.pattern_id && e.pattern_id !== patternId) {
      return false;
    }

    // Filter by agent
    if (agentId) {
      // AGENT scope: only if from/to this agent
      if (e.scope === "agent") {
        if (e.from_agent !== agentId && e.to_agent !== agentId) {
          return false;
        }
      }
      // SHARED/TEMPORAL: only if broadcast or addressed to this agent
      else if (e.to_agent && e.to_agent !== agentId) {
        return false;
      }
    }

    return true;
  });
}

// Format entry as compact system reminder
function formatEntry(entry: BlackboardEntry): string {
  const parts = [`[${entry.type.toUpperCase()}]`];

  if (entry.from_agent) {
    parts.push(`from:${entry.from_agent}`);
  }
  if (entry.to_agent) {
    parts.push(`to:${entry.to_agent}`);
  }

  // Prefer formal, fall back to prose
  if (entry.formal) {
    parts.push(`| ${entry.formal}`);
  } else if (entry.prose) {
    parts.push(`| ${entry.prose}`);
  }

  // Add structured data if present
  if (entry.data && Object.keys(entry.data).length > 0) {
    parts.push(`| data=${JSON.stringify(entry.data)}`);
  }

  if (entry.artifacts && entry.artifacts.length > 0) {
    parts.push(`| files=${entry.artifacts.join(",")}`);
  }

  return parts.join(" ");
}

// Format entries as system reminder block
function formatSystemReminder(entries: BlackboardEntry[]): string {
  if (entries.length === 0) {
    return "";
  }

  // Sort by priority (critical first) then timestamp
  const priorityOrder: Record<string, number> = {
    critical: 0,
    high: 1,
    normal: 2,
    low: 3,
  };

  const sorted = [...entries].sort((a, b) => {
    const pa = priorityOrder[a.priority] ?? 2;
    const pb = priorityOrder[b.priority] ?? 2;
    if (pa !== pb) return pa - pb;
    return a.timestamp.localeCompare(b.timestamp);
  });

  const limited = sorted.slice(0, MAX_ENTRIES_IN_REMINDER);

  const lines = ["<blackboard>"];
  for (const entry of limited) {
    lines.push(formatEntry(entry));
  }
  if (sorted.length > MAX_ENTRIES_IN_REMINDER) {
    lines.push(`... and ${sorted.length - MAX_ENTRIES_IN_REMINDER} more entries`);
  }
  lines.push("</blackboard>");

  return lines.join("\n");
}

// Read stdin
async function readStdin(): Promise<string> {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => {
      resolve(data);
    });
  });
}

async function main() {
  const input: PreToolUseInput = JSON.parse(await readStdin());
  const output: HookOutput = { result: "continue" };

  // Get agent context
  const { agentId, patternId, projectId } = getAgentContext();

  // Skip if no project context
  if (!projectId) {
    console.log(JSON.stringify(output));
    return;
  }

  // Get last poll timestamp
  const sinceTimestamp = getLastPollTimestamp(input.session_id);

  // Read and filter blackboard
  const entries = readBlackboardCache(projectId);
  const filtered = filterEntries(entries, agentId, patternId, sinceTimestamp);

  // Format as system reminder
  if (filtered.length > 0) {
    const reminder = formatSystemReminder(filtered);
    output.message = `Blackboard update:\n${reminder}`;

    // Update last poll timestamp
    const maxTimestamp = filtered.reduce(
      (max, e) => (e.timestamp > max ? e.timestamp : max),
      ""
    );
    if (maxTimestamp) {
      saveLastPollTimestamp(input.session_id, maxTimestamp);
    }
  }

  console.log(JSON.stringify(output));
}

main().catch((err) => {
  console.error("Hook error:", err);
  // Don't block on errors
  console.log(JSON.stringify({ result: "continue" }));
});
