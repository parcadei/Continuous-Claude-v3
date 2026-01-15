// src/pre-compact-continuity.ts
import * as fs2 from "fs";
import * as path from "path";

// src/transcript-parser.ts
import * as fs from "fs";
function parseTranscript(transcriptPath) {
  const summary = {
    lastTodos: [],
    recentToolCalls: [],
    lastAssistantMessage: "",
    filesModified: [],
    errorsEncountered: []
  };
  if (!fs.existsSync(transcriptPath)) {
    return summary;
  }
  const content = fs.readFileSync(transcriptPath, "utf-8");
  const lines = content.split("\n").filter((line) => line.trim());
  const allToolCalls = [];
  const modifiedFiles = /* @__PURE__ */ new Set();
  const errors = [];
  let lastTodoState = [];
  let lastAssistant = "";
  for (const line of lines) {
    try {
      const entry = JSON.parse(line);
      if (entry.role === "assistant" && typeof entry.content === "string") {
        lastAssistant = entry.content;
      } else if (entry.type === "assistant" && typeof entry.content === "string") {
        lastAssistant = entry.content;
      }
      if (entry.tool_name || entry.type === "tool_use") {
        const toolName = entry.tool_name || entry.name;
        if (toolName) {
          const toolCall = {
            name: toolName,
            timestamp: entry.timestamp,
            input: entry.tool_input,
            success: true
            // Will be updated by result
          };
          if (toolName === "TodoWrite" || toolName.toLowerCase().includes("todowrite")) {
            const input = entry.tool_input;
            if (input?.todos) {
              lastTodoState = input.todos.map((t, idx) => ({
                id: t.id || `todo-${idx}`,
                content: t.content || "",
                status: t.status || "pending"
              }));
            }
          }
          if (toolName === "Edit" || toolName === "Write" || toolName.toLowerCase().includes("edit") || toolName.toLowerCase().includes("write")) {
            const input = entry.tool_input;
            const filePath = input?.file_path || input?.path;
            if (filePath && typeof filePath === "string") {
              modifiedFiles.add(filePath);
            }
          }
          if (toolName === "Bash" || toolName.toLowerCase().includes("bash")) {
            const input = entry.tool_input;
            if (input?.command) {
              toolCall.input = { command: input.command };
            }
          }
          allToolCalls.push(toolCall);
        }
      }
      if (entry.type === "tool_result" || entry.tool_result !== void 0) {
        const result = entry.tool_result;
        if (result) {
          const exitCode = result.exit_code ?? result.exitCode;
          if (exitCode !== void 0 && exitCode !== 0) {
            if (allToolCalls.length > 0) {
              allToolCalls[allToolCalls.length - 1].success = false;
            }
            const errorMsg = result.stderr || result.error || "Command failed";
            const lastTool = allToolCalls[allToolCalls.length - 1];
            const command = lastTool?.input?.command || "unknown command";
            errors.push(`${command}: ${errorMsg.substring(0, 200)}`);
          }
        }
        if (entry.error) {
          errors.push(entry.error.substring(0, 200));
          if (allToolCalls.length > 0) {
            allToolCalls[allToolCalls.length - 1].success = false;
          }
        }
      }
    } catch {
      continue;
    }
  }
  summary.lastTodos = lastTodoState;
  summary.recentToolCalls = allToolCalls.slice(-5);
  summary.lastAssistantMessage = lastAssistant.substring(0, 500);
  summary.filesModified = Array.from(modifiedFiles);
  summary.errorsEncountered = errors.slice(-5);
  return summary;
}
function generateAutoHandoff(summary, sessionName) {
  const timestamp = (/* @__PURE__ */ new Date()).toISOString();
  const dateOnly = timestamp.split("T")[0];
  const lines = [];
  const inProgress = summary.lastTodos.filter((t) => t.status === "in_progress");
  const pending = summary.lastTodos.filter((t) => t.status === "pending");
  const completed = summary.lastTodos.filter((t) => t.status === "completed");
  const currentTask = inProgress[0]?.content || pending[0]?.content || "Continue from auto-compact";
  const goalSummary = completed.length > 0 ? `Completed ${completed.length} task(s) before auto-compact` : "Session auto-compacted";
  lines.push("---");
  lines.push(`session: ${sessionName}`);
  lines.push(`date: ${dateOnly}`);
  lines.push("status: partial");
  lines.push("outcome: PARTIAL_PLUS");
  lines.push("---");
  lines.push("");
  lines.push(`goal: ${goalSummary}`);
  lines.push(`now: ${currentTask}`);
  lines.push("test: # No test command captured");
  lines.push("");
  lines.push("done_this_session:");
  if (completed.length > 0) {
    completed.forEach((t) => {
      lines.push(`  - task: "${t.content.replace(/"/g, '\\"')}"`);
      lines.push("    files: []");
    });
  } else {
    lines.push('  - task: "Session started"');
    lines.push("    files: []");
  }
  lines.push("");
  lines.push("blockers:");
  if (summary.errorsEncountered.length > 0) {
    summary.errorsEncountered.slice(0, 3).forEach((e) => {
      const safeError = e.replace(/"/g, '\\"').substring(0, 100);
      lines.push(`  - "${safeError}"`);
    });
  } else {
    lines.push("  []");
  }
  lines.push("");
  lines.push("questions:");
  if (pending.length > 0) {
    pending.slice(0, 3).forEach((t) => {
      lines.push(`  - "Resume: ${t.content.replace(/"/g, '\\"')}"`);
    });
  } else {
    lines.push("  []");
  }
  lines.push("");
  lines.push("decisions:");
  lines.push('  - auto_compact: "Context limit reached, auto-compacted"');
  lines.push("");
  lines.push("findings:");
  lines.push(`  - tool_calls: "${summary.recentToolCalls.length} recent tool calls"`);
  lines.push(`  - files_modified: "${summary.filesModified.length} files changed"`);
  lines.push("");
  lines.push("worked:");
  const successfulTools = summary.recentToolCalls.filter((t) => t.success);
  if (successfulTools.length > 0) {
    lines.push(`  - "${successfulTools.map((t) => t.name).join(", ")} completed successfully"`);
  } else {
    lines.push("  []");
  }
  lines.push("");
  lines.push("failed:");
  const failedTools = summary.recentToolCalls.filter((t) => !t.success);
  if (failedTools.length > 0) {
    lines.push(`  - "${failedTools.map((t) => t.name).join(", ")} encountered errors"`);
  } else {
    lines.push("  []");
  }
  lines.push("");
  lines.push("next:");
  if (inProgress.length > 0) {
    lines.push(`  - "Continue: ${inProgress[0].content.replace(/"/g, '\\"')}"`);
  }
  if (pending.length > 0) {
    pending.slice(0, 2).forEach((t) => {
      lines.push(`  - "${t.content.replace(/"/g, '\\"')}"`);
    });
  }
  if (inProgress.length === 0 && pending.length === 0) {
    lines.push('  - "Review session state and continue"');
  }
  lines.push("");
  lines.push("files:");
  lines.push("  created: []");
  lines.push("  modified:");
  if (summary.filesModified.length > 0) {
    summary.filesModified.slice(0, 10).forEach((f) => {
      lines.push(`    - "${f}"`);
    });
  } else {
    lines.push("    []");
  }
  return lines.join("\n");
}
var isMainModule = import.meta.url === `file://${process.argv[1]}`;
if (isMainModule) {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.log("Usage: npx tsx transcript-parser.ts <transcript-path> [session-name]");
    process.exit(1);
  }
  const transcriptPath = args[0];
  const sessionName = args[1] || "test-session";
  console.log(`Parsing transcript: ${transcriptPath}`);
  const summary = parseTranscript(transcriptPath);
  console.log("\n--- Summary ---");
  console.log(JSON.stringify(summary, null, 2));
  console.log("\n--- Auto-Handoff ---");
  console.log(generateAutoHandoff(summary, sessionName));
}

// src/shared/learning-extractor.ts
import { spawnSync } from "child_process";

// src/shared/opc-path.ts
import { existsSync as existsSync2 } from "fs";
import { join } from "path";
function getOpcDir() {
  const envOpcDir = process.env.CLAUDE_OPC_DIR;
  if (envOpcDir && existsSync2(envOpcDir)) {
    return envOpcDir;
  }
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const localOpc = join(projectDir, "opc");
  if (existsSync2(localOpc)) {
    return localOpc;
  }
  const homeDir = process.env.HOME || process.env.USERPROFILE || "";
  if (homeDir) {
    const globalClaude = join(homeDir, ".claude");
    const globalScripts = join(globalClaude, "scripts", "core");
    if (existsSync2(globalScripts)) {
      return globalClaude;
    }
  }
  return null;
}

// src/shared/learning-extractor.ts
function storeCheckpoint(checkpoint, sessionId, agentId) {
  const opcDir = getOpcDir();
  if (!opcDir) return null;
  const args = [
    "run",
    "python",
    "scripts/core/checkpoint.py",
    "create",
    "--session-id",
    sessionId,
    "--phase",
    checkpoint.phase
  ];
  if (agentId) {
    args.push("--agent-id", agentId);
  }
  if (checkpoint.contextUsage !== void 0) {
    args.push("--context-usage", checkpoint.contextUsage.toString());
  }
  if (checkpoint.filesModified && checkpoint.filesModified.length > 0) {
    args.push("--files-json", JSON.stringify(checkpoint.filesModified));
  }
  if (checkpoint.unknowns && checkpoint.unknowns.length > 0) {
    args.push("--unknowns-json", JSON.stringify(checkpoint.unknowns));
  }
  if (checkpoint.handoffPath) {
    args.push("--handoff-path", checkpoint.handoffPath);
  }
  const result = spawnSync("uv", args, {
    encoding: "utf-8",
    cwd: opcDir,
    env: {
      ...process.env,
      PYTHONPATH: opcDir
    },
    timeout: 1e4
  });
  if (result.status === 0 && result.stdout) {
    const match = result.stdout.match(/Created checkpoint: ([a-f0-9-]+)/i);
    return match ? match[1] : null;
  }
  if (result.stderr) {
    console.error(`[checkpoint] storeCheckpoint failed: ${result.stderr}`);
  }
  return null;
}

// src/pre-compact-continuity.ts
async function main() {
  const input = JSON.parse(await readStdin());
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const ledgerDir = path.join(projectDir, "thoughts", "ledgers");
  const ledgerFiles = fs2.readdirSync(ledgerDir).filter((f) => f.startsWith("CONTINUITY_CLAUDE-") && f.endsWith(".md"));
  if (ledgerFiles.length === 0) {
    const output = {
      continue: true,
      systemMessage: "[PreCompact] No ledger found. Create one? /continuity_ledger"
    };
    console.log(JSON.stringify(output));
    return;
  }
  const mostRecent = ledgerFiles.sort((a, b) => {
    const statA = fs2.statSync(path.join(ledgerDir, a));
    const statB = fs2.statSync(path.join(ledgerDir, b));
    return statB.mtime.getTime() - statA.mtime.getTime();
  })[0];
  const ledgerPath = path.join(ledgerDir, mostRecent);
  if (input.trigger === "auto") {
    const sessionName = mostRecent.replace("CONTINUITY_CLAUDE-", "").replace(".md", "");
    let handoffFile = "";
    if (input.transcript_path && fs2.existsSync(input.transcript_path)) {
      const summary = parseTranscript(input.transcript_path);
      const handoffContent = generateAutoHandoff(summary, sessionName);
      const handoffDir = path.join(projectDir, "thoughts", "shared", "handoffs", sessionName);
      fs2.mkdirSync(handoffDir, { recursive: true });
      const timestamp = (/* @__PURE__ */ new Date()).toISOString().replace(/[:.]/g, "-").slice(0, 19);
      handoffFile = `auto-handoff-${timestamp}.yaml`;
      const handoffPath2 = path.join(handoffDir, handoffFile);
      fs2.writeFileSync(handoffPath2, handoffContent);
      const briefSummary = generateAutoSummary(projectDir, input.session_id);
      if (briefSummary) {
        appendToLedger(ledgerPath, briefSummary);
      }
    } else {
      const briefSummary = generateAutoSummary(projectDir, input.session_id);
      if (briefSummary) {
        appendToLedger(ledgerPath, briefSummary);
      }
    }
    const editedFiles = getEditedFiles(projectDir, input.session_id);
    const handoffPath = handoffFile ? `thoughts/shared/handoffs/${sessionName}/${handoffFile}` : void 0;
    const checkpointId = storeCheckpoint(
      {
        phase: "pre-compact",
        contextUsage: 0.95,
        // Compacting means we're near limit
        filesModified: editedFiles,
        handoffPath
      },
      input.session_id
    );
    const checkpointStatus = checkpointId ? "+ checkpoint saved" : "(checkpoint failed)";
    const message = handoffFile ? `[PreCompact:auto] Created YAML handoff: thoughts/shared/handoffs/${sessionName}/${handoffFile} ${checkpointStatus}` : `[PreCompact:auto] Session summary auto-appended to ${mostRecent} ${checkpointStatus}`;
    const output = {
      continue: true,
      systemMessage: message
    };
    console.log(JSON.stringify(output));
  } else {
    const output = {
      continue: true,
      systemMessage: `[PreCompact] Consider updating ledger before compacting: /continuity_ledger
Ledger: ${mostRecent}`
    };
    console.log(JSON.stringify(output));
  }
}
function getEditedFiles(projectDir, sessionId) {
  const cacheDir = path.join(projectDir, ".claude", "tsc-cache", sessionId || "default");
  const editedFilesPath = path.join(cacheDir, "edited-files.log");
  if (!fs2.existsSync(editedFilesPath)) {
    return [];
  }
  const content = fs2.readFileSync(editedFilesPath, "utf-8");
  const normalizedProjectDir = projectDir.replace(/\\/g, "/");
  return [...new Set(
    content.split("\n").filter((line) => line.trim()).map((line) => {
      const parts = line.split(":");
      if (parts.length < 3) return "";
      const filepath = parts.slice(1, -1).join(":");
      const normalized = filepath.replace(/\\/g, "/");
      return normalized.startsWith(normalizedProjectDir + "/") ? normalized.slice(normalizedProjectDir.length + 1) : normalized;
    }).filter((f) => f)
  )];
}
function generateAutoSummary(projectDir, sessionId) {
  const timestamp = (/* @__PURE__ */ new Date()).toISOString();
  const lines = [];
  const editedFiles = getEditedFiles(projectDir, sessionId);
  const gitClaudeDir = path.join(projectDir, ".git", "claude", "branches");
  let buildAttempts = { passed: 0, failed: 0 };
  if (fs2.existsSync(gitClaudeDir)) {
    try {
      const branches = fs2.readdirSync(gitClaudeDir);
      for (const branch of branches) {
        const attemptsFile = path.join(gitClaudeDir, branch, "attempts.jsonl");
        if (fs2.existsSync(attemptsFile)) {
          const content = fs2.readFileSync(attemptsFile, "utf-8");
          content.split("\n").filter((l) => l.trim()).forEach((line) => {
            try {
              const attempt = JSON.parse(line);
              if (attempt.type === "build_pass") buildAttempts.passed++;
              if (attempt.type === "build_fail") buildAttempts.failed++;
            } catch {
            }
          });
        }
      }
    } catch {
    }
  }
  if (editedFiles.length === 0 && buildAttempts.passed === 0 && buildAttempts.failed === 0) {
    return null;
  }
  lines.push(`
## Session Auto-Summary (${timestamp})`);
  if (editedFiles.length > 0) {
    lines.push(`- Files changed: ${editedFiles.slice(0, 10).join(", ")}${editedFiles.length > 10 ? ` (+${editedFiles.length - 10} more)` : ""}`);
  }
  if (buildAttempts.passed > 0 || buildAttempts.failed > 0) {
    lines.push(`- Build/test: ${buildAttempts.passed} passed, ${buildAttempts.failed} failed`);
  }
  return lines.join("\n");
}
function appendToLedger(ledgerPath, summary) {
  try {
    let content = fs2.readFileSync(ledgerPath, "utf-8");
    const stateMatch = content.match(/## State\n/);
    if (stateMatch) {
      const nowMatch = content.match(/(\n-\s*Now:)/);
      if (nowMatch && nowMatch.index) {
        content = content.slice(0, nowMatch.index) + summary + content.slice(nowMatch.index);
      } else {
        const nextSection = content.indexOf("\n## ", content.indexOf("## State") + 1);
        if (nextSection > 0) {
          content = content.slice(0, nextSection) + summary + "\n" + content.slice(nextSection);
        } else {
          content += summary;
        }
      }
    } else {
      content += summary;
    }
    fs2.writeFileSync(ledgerPath, content);
  } catch (err) {
  }
}
async function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.on("data", (chunk) => data += chunk);
    process.stdin.on("end", () => resolve(data));
  });
}
main().catch(console.error);
