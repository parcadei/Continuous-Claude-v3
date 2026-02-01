// src/session-start-continuity.ts
import * as fs from "fs";
import * as path from "path";
import { execSync } from "child_process";
var STALE_THRESHOLD_DAYS = 7;
var STALE_THRESHOLD_MS = STALE_THRESHOLD_DAYS * 24 * 60 * 60 * 1e3;
function buildHandoffDirName(sessionName, sessionId) {
  const uuidShort = sessionId.replace(/-/g, "").slice(0, 8);
  return `${sessionName}-${uuidShort}`;
}
function parseHandoffDirName(dirName) {
  const match = dirName.match(/^(.+)-([0-9a-f]{8})$/i);
  if (match) {
    return { sessionName: match[1], uuidShort: match[2].toLowerCase() };
  }
  return { sessionName: dirName, uuidShort: null };
}
function findSessionHandoffWithUUID(sessionName, sessionId) {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const handoffsBase = path.join(projectDir, "thoughts", "shared", "handoffs");
  if (!fs.existsSync(handoffsBase)) return null;
  const uuidShort = sessionId.replace(/-/g, "").slice(0, 8).toLowerCase();
  const exactDir = path.join(handoffsBase, `${sessionName}-${uuidShort}`);
  if (fs.existsSync(exactDir)) {
    return findMostRecentMdFile(exactDir);
  }
  const legacyDir = path.join(handoffsBase, sessionName);
  if (fs.existsSync(legacyDir) && fs.statSync(legacyDir).isDirectory()) {
    const result = findMostRecentMdFile(legacyDir);
    if (result) return result;
  }
  const allDirs = fs.readdirSync(handoffsBase).filter((d) => {
    const stat = fs.statSync(path.join(handoffsBase, d));
    if (!stat.isDirectory()) return false;
    const { sessionName: parsedName } = parseHandoffDirName(d);
    return parsedName === sessionName;
  });
  allDirs.sort((a, b) => {
    const statA = fs.statSync(path.join(handoffsBase, a));
    const statB = fs.statSync(path.join(handoffsBase, b));
    return statB.mtime.getTime() - statA.mtime.getTime();
  });
  for (const dir of allDirs) {
    const result = findMostRecentMdFile(path.join(handoffsBase, dir));
    if (result) return result;
  }
  return null;
}
function isHandoffFile(filename) {
  return filename.endsWith(".md") || filename.endsWith(".yaml") || filename.endsWith(".yml");
}
function findMostRecentMdFile(dirPath) {
  if (!fs.existsSync(dirPath)) return null;
  const handoffFiles = fs.readdirSync(dirPath).filter((f) => isHandoffFile(f)).sort((a, b) => {
    const statA = fs.statSync(path.join(dirPath, a));
    const statB = fs.statSync(path.join(dirPath, b));
    return statB.mtime.getTime() - statA.mtime.getTime();
  });
  return handoffFiles.length > 0 ? path.join(dirPath, handoffFiles[0]) : null;
}
function extractYamlFields(content) {
  const goalMatch = content.match(/^goal:\s*(.+)$/m);
  const nowMatch = content.match(/^now:\s*(.+)$/m);
  if (!goalMatch && !nowMatch) return null;
  return {
    goal: goalMatch ? goalMatch[1].trim().replace(/^["']|["']$/g, "") : "",
    now: nowMatch ? nowMatch[1].trim().replace(/^["']|["']$/g, "") : ""
  };
}
function extractLedgerSection(handoffContent) {
  const match = handoffContent.match(/(?:^|\n)## Ledger\n([\s\S]*?)(?=\n---\n|\n## [^#]|$)/);
  return match ? `## Ledger
${match[1].trim()}` : null;
}
function findSessionHandoff(sessionName) {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const handoffDir = path.join(projectDir, "thoughts", "shared", "handoffs", sessionName);
  if (!fs.existsSync(handoffDir)) return null;
  const handoffFiles = fs.readdirSync(handoffDir).filter((f) => isHandoffFile(f)).sort((a, b) => {
    const statA = fs.statSync(path.join(handoffDir, a));
    const statB = fs.statSync(path.join(handoffDir, b));
    return statB.mtime.getTime() - statA.mtime.getTime();
  });
  return handoffFiles.length > 0 ? path.join(handoffDir, handoffFiles[0]) : null;
}
function pruneLedger(ledgerPath) {
  let content = fs.readFileSync(ledgerPath, "utf-8");
  const originalLength = content.length;
  content = content.replace(/\n### Session Ended \([^)]+\)\n- Reason: \w+\n/g, "");
  const agentReportsMatch = content.match(/## Agent Reports\n([\s\S]*?)(?=\n## |$)/);
  if (agentReportsMatch) {
    const agentReportsSection = agentReportsMatch[0];
    const reports = agentReportsSection.match(/### [^\n]+ \(\d{4}-\d{2}-\d{2}[^)]*\)[\s\S]*?(?=\n### |\n## |$)/g);
    if (reports && reports.length > 10) {
      const keptReports = reports.slice(-10);
      const newAgentReportsSection = "## Agent Reports\n" + keptReports.join("");
      content = content.replace(agentReportsSection, newAgentReportsSection);
    }
  }
  if (content.length !== originalLength) {
    fs.writeFileSync(ledgerPath, content);
    console.error(`Pruned ledger: ${originalLength} \u2192 ${content.length} bytes`);
  }
}
function getLatestHandoff(handoffDir) {
  if (!fs.existsSync(handoffDir)) return null;
  const handoffFiles = fs.readdirSync(handoffDir).filter((f) => (f.startsWith("task-") || f.startsWith("auto-handoff-")) && isHandoffFile(f)).sort((a, b) => {
    const statA = fs.statSync(path.join(handoffDir, a));
    const statB = fs.statSync(path.join(handoffDir, b));
    return statB.mtime.getTime() - statA.mtime.getTime();
  });
  if (handoffFiles.length === 0) return null;
  const latestFile = handoffFiles[0];
  const content = fs.readFileSync(path.join(handoffDir, latestFile), "utf-8");
  const isAutoHandoff = latestFile.startsWith("auto-handoff-");
  let taskNumber;
  let status;
  let summary;
  if (isAutoHandoff) {
    const typeMatch = content.match(/type:\s*auto-handoff/i);
    status = typeMatch ? "auto-handoff" : "unknown";
    const timestampMatch = latestFile.match(/auto-handoff-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})/);
    taskNumber = timestampMatch ? timestampMatch[1] : "auto";
    const inProgressMatch = content.match(/## In Progress\n([\s\S]*?)(?=\n## |$)/);
    summary = inProgressMatch ? inProgressMatch[1].trim().split("\n").slice(0, 3).join("; ").substring(0, 150) : "Auto-handoff from pre-compact";
  } else {
    const taskMatch = latestFile.match(/task-(\d+)/);
    taskNumber = taskMatch ? taskMatch[1] : "??";
    const statusMatch = content.match(/status:\s*(success|partial|blocked)/i);
    status = statusMatch ? statusMatch[1] : "unknown";
    const summaryMatch = content.match(/## What Was Done\n([\s\S]*?)(?=\n## |$)/);
    summary = summaryMatch ? summaryMatch[1].trim().split("\n").slice(0, 2).join("; ").substring(0, 150) : "No summary available";
  }
  return {
    filename: latestFile,
    taskNumber,
    status,
    summary,
    isAutoHandoff
  };
}
async function buildUnifiedContext(projectDir) {
  const sections = [];
  const roadmapPath = path.join(projectDir, "ROADMAP.md");
  if (fs.existsSync(roadmapPath)) {
    try {
      const roadmap = fs.readFileSync(roadmapPath, "utf-8");
      const currentMatch = roadmap.match(/## Current Focus\n([\s\S]*?)(?=\n## |$)/);
      if (currentMatch) {
        sections.push(`## ROADMAP - Current Focus
${currentMatch[1].trim().substring(0, 500)}`);
      }
      const sessionMatch = roadmap.match(/### (\d{4}-\d{2}-\d{2}): ([^\n]+)\n([\s\S]*?)(?=\n### |\n## |$)/);
      if (sessionMatch) {
        const sessionContent = sessionMatch[3].substring(0, 400);
        sections.push(`## Recent Planning: ${sessionMatch[2]}
${sessionContent}`);
      }
    } catch (error) {
      console.error(`Warning: Error reading ROADMAP.md for unified context: ${error}`);
    }
  }
  const treePath = path.join(projectDir, ".claude", "knowledge-tree.json");
  if (fs.existsSync(treePath)) {
    try {
      const treeContent = fs.readFileSync(treePath, "utf-8");
      const tree = JSON.parse(treeContent);
      if (tree.navigation?.common_tasks) {
        const taskNav = Object.entries(tree.navigation.common_tasks).slice(0, 5).map(([task, paths]) => `- ${task}: ${paths.slice(0, 2).join(", ")}`).join("\n");
        if (taskNav) {
          sections.push(`## Quick Navigation
${taskNav}`);
        }
      }
      if (tree.navigation?.entry_points) {
        const entries = Object.entries(tree.navigation.entry_points).slice(0, 3).map(([name, p]) => `- ${name}: ${p}`).join("\n");
        if (entries) {
          sections.push(`## Entry Points
${entries}`);
        }
      }
    } catch (error) {
    }
  }
  const currentGoalMatch = sections[0]?.match(/\*\*([^*]+)\*\*/);
  const currentGoal = currentGoalMatch ? currentGoalMatch[1] : "";
  if (currentGoal) {
    const opcDir = process.env.CLAUDE_OPC_DIR || path.join(process.env.USERPROFILE || "", ".claude");
    try {
      const escapedGoal = currentGoal.replace(/"/g, "").substring(0, 100);
      const isWindows = process.platform === "win32";
      const cmd = isWindows ? `cd /d "${opcDir}" && set PYTHONPATH=. && uv run python scripts/core/recall_learnings.py --query "${escapedGoal}" --k 3 --text-only` : `cd "${opcDir}" && PYTHONPATH=. uv run python scripts/core/recall_learnings.py --query "${escapedGoal}" --k 3 --text-only`;
      const result = execSync(cmd, {
        encoding: "utf-8",
        timeout: 5e3,
        stdio: ["pipe", "pipe", "pipe"],
        shell: isWindows ? "cmd.exe" : true
      });
      if (result && !result.includes("No results") && result.trim().length > 20) {
        sections.push(`## Relevant Memories
${result.substring(0, 600)}`);
      }
    } catch (error) {
    }
  }
  return sections.join("\n\n---\n\n");
}
function getUnmarkedHandoffs() {
  try {
    const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
    const dbPath = path.join(projectDir, ".claude", "cache", "artifact-index", "context.db");
    if (!fs.existsSync(dbPath)) {
      return [];
    }
    const result = execSync(
      `sqlite3 "${dbPath}" "SELECT id, session_name, task_number, task_summary FROM handoffs WHERE outcome = 'UNKNOWN' ORDER BY indexed_at DESC LIMIT 5"`,
      { encoding: "utf-8", timeout: 3e3 }
    );
    if (!result.trim()) {
      return [];
    }
    return result.trim().split("\n").map((line) => {
      const [id, session_name, task_number, task_summary] = line.split("|");
      return { id, session_name, task_number: task_number || null, task_summary: task_summary || "" };
    });
  } catch (error) {
    return [];
  }
}
async function main() {
  let input;
  try {
    const stdin = await readStdin();
    input = stdin ? JSON.parse(stdin) : { session_id: "unknown", source: "cli" };
  } catch (e) {
    input = { session_id: "unknown", source: "cli" };
  }
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const sessionType = input.source || input.type;
  let message = "";
  let additionalContext = "";
  let usedHandoffLedger = false;
  const handoffsDir = path.join(projectDir, "thoughts", "shared", "handoffs");
  if (fs.existsSync(handoffsDir)) {
    try {
      const sessionDirs = fs.readdirSync(handoffsDir).filter((d) => {
        const stat = fs.statSync(path.join(handoffsDir, d));
        return stat.isDirectory();
      });
      let mostRecentLedger = null;
      for (const sessionName of sessionDirs) {
        const handoffPath = findSessionHandoff(sessionName);
        if (handoffPath) {
          const content = fs.readFileSync(handoffPath, "utf-8");
          const isYaml = handoffPath.endsWith(".yaml") || handoffPath.endsWith(".yml");
          let goalSummary = "No goal found";
          let currentFocus = "Unknown";
          let ledgerContent = "";
          if (isYaml) {
            const yamlFields = extractYamlFields(content);
            if (yamlFields) {
              goalSummary = yamlFields.goal || "No goal found";
              currentFocus = yamlFields.now || "Unknown";
              ledgerContent = content;
            }
          } else {
            const ledgerSection = extractLedgerSection(content);
            if (ledgerSection) {
              const goalMatch = ledgerSection.match(/\*\*Goal:\*\*\s*([^\n]+)/);
              const nowMatch = ledgerSection.match(/### Now\n\[?-?>?\]?\s*([^\n]+)/);
              goalSummary = goalMatch ? goalMatch[1].trim().substring(0, 100) : "No goal found";
              currentFocus = nowMatch ? nowMatch[1].trim() : "Unknown";
              ledgerContent = ledgerSection;
            }
          }
          if (ledgerContent || isYaml && (goalSummary !== "No goal found" || currentFocus !== "Unknown")) {
            const mtime = fs.statSync(handoffPath).mtime.getTime();
            const fileAge = Date.now() - mtime;
            if (sessionType === "startup" && fileAge > STALE_THRESHOLD_MS) {
              console.error(`Skipping stale handoff: ${sessionName} (${Math.floor(fileAge / (24 * 60 * 60 * 1e3))} days old)`);
              continue;
            }
            const statusMatch = content.match(/^status:\s*(\w+)/m);
            if (statusMatch && statusMatch[1] === "completed") {
              console.error(`Skipping completed handoff: ${sessionName}`);
              continue;
            }
            if (!mostRecentLedger || mtime > mostRecentLedger.mtime) {
              mostRecentLedger = {
                content: ledgerContent || content,
                sessionName,
                handoffPath,
                mtime,
                goalSummary: goalSummary.substring(0, 100),
                currentFocus
              };
            }
          }
        }
      }
      const roadmapPath = path.join(projectDir, "ROADMAP.md");
      let roadmapCurrentFocus = "";
      let roadmapContext = "";
      if (fs.existsSync(roadmapPath)) {
        try {
          const roadmapContent = fs.readFileSync(roadmapPath, "utf-8");
          const currentMatch = roadmapContent.match(/## Current Focus\n([\s\S]*?)(?=\n## |$)/);
          if (currentMatch) {
            const currentSection = currentMatch[1].trim();
            const firstLine = currentSection.split("\n")[0];
            roadmapCurrentFocus = firstLine.replace(/\*\*/g, "").trim();
            roadmapContext = `## ROADMAP - Current Focus
${currentSection}`;
          }
        } catch (error) {
          console.error(`Warning: Error reading ROADMAP.md: ${error}`);
        }
      }
      if (mostRecentLedger) {
        usedHandoffLedger = true;
        const { sessionName, goalSummary, currentFocus, content: ledgerSection, handoffPath } = mostRecentLedger;
        const handoffFilename = path.basename(handoffPath);
        if (sessionType === "startup") {
          if (roadmapCurrentFocus) {
            message = `\u{1F4CD} Current: ${roadmapCurrentFocus} | \u{1F4CB} Handoff: ${sessionName} (run /resume_handoff)`;
          } else {
            message = `\u{1F4CB} Handoff Ledger: ${sessionName} \u2192 ${currentFocus} (run /resume_handoff to continue)`;
          }
        } else {
          console.error(`\u2713 Handoff Ledger loaded: ${sessionName} \u2192 ${currentFocus}`);
          message = `[${sessionType}] Loaded from handoff: ${handoffFilename} | Goal: ${goalSummary} | Focus: ${currentFocus}`;
          if (sessionType === "clear" || sessionType === "compact") {
            if (roadmapContext) {
              additionalContext = `${roadmapContext}

---

`;
            }
            additionalContext += `Handoff Ledger loaded from ${handoffFilename}:

${ledgerSection}`;
            const unmarkedHandoffs = getUnmarkedHandoffs();
            if (unmarkedHandoffs.length > 0) {
              additionalContext += `

---

## Unmarked Session Outcomes

`;
              additionalContext += `The following handoffs have no outcome marked. Consider marking them to improve future session recommendations:

`;
              for (const h of unmarkedHandoffs) {
                const taskLabel = h.task_number ? `task-${h.task_number}` : "handoff";
                const summaryPreview = h.task_summary ? h.task_summary.substring(0, 60) + "..." : "(no summary)";
                additionalContext += `- **${h.session_name}/${taskLabel}** (ID: \`${h.id.substring(0, 8)}\`): ${summaryPreview}
`;
              }
              additionalContext += `
To mark an outcome:
\`\`\`bash
cd ~/.claude && uv run python scripts/core/artifact_mark.py --handoff <ID> --outcome SUCCEEDED|PARTIAL_PLUS|PARTIAL_MINUS|FAILED
\`\`\`
`;
            }
            additionalContext += `

---

Full handoff available at: ${handoffPath}
`;
          }
        }
      }
      if (!mostRecentLedger && roadmapCurrentFocus) {
        usedHandoffLedger = true;
        if (sessionType === "startup") {
          message = `\u{1F4CD} Current: ${roadmapCurrentFocus}`;
        } else {
          message = `[${sessionType}] ROADMAP Focus: ${roadmapCurrentFocus}`;
          if (sessionType === "clear" || sessionType === "compact") {
            additionalContext = roadmapContext;
          }
        }
      }
      if (sessionType === "startup" || sessionType === "clear" || sessionType === "compact") {
        try {
          const unifiedContext = await buildUnifiedContext(projectDir);
          if (unifiedContext && unifiedContext.trim().length > 50) {
            if (additionalContext) {
              additionalContext = unifiedContext + "\n\n---\n\n" + additionalContext;
            } else {
              additionalContext = unifiedContext;
            }
          }
        } catch (error) {
          console.error(`Warning: Could not build unified context: ${error}`);
        }
      }
    } catch (error) {
      console.error(`Warning: Error scanning handoffs: ${error}`);
    }
  }
  if (!usedHandoffLedger) {
    const ledgerDir = path.join(projectDir, "thoughts", "ledgers");
    if (!fs.existsSync(ledgerDir)) {
      console.log(JSON.stringify({ result: "continue" }));
      return;
    }
    const ledgerFiles = fs.readdirSync(ledgerDir).filter((f) => f.startsWith("CONTINUITY_CLAUDE-") && f.endsWith(".md")).sort((a, b) => {
      const statA = fs.statSync(path.join(ledgerDir, a));
      const statB = fs.statSync(path.join(ledgerDir, b));
      return statB.mtime.getTime() - statA.mtime.getTime();
    });
    if (ledgerFiles.length > 0) {
      console.error("DEPRECATED: Using legacy ledger file. Migrate to handoff format with /create_handoff");
      const mostRecent = ledgerFiles[0];
      const ledgerPath = path.join(ledgerDir, mostRecent);
      pruneLedger(ledgerPath);
      const ledgerContent = fs.readFileSync(ledgerPath, "utf-8");
      const goalMatch = ledgerContent.match(/## Goal\n([\s\S]*?)(?=\n## |$)/);
      const nowMatch = ledgerContent.match(/- Now: ([^\n]+)/);
      const goalSummary = goalMatch ? goalMatch[1].trim().split("\n")[0].substring(0, 100) : "No goal found";
      const currentFocus = nowMatch ? nowMatch[1].trim() : "Unknown";
      const sessionName = mostRecent.replace("CONTINUITY_CLAUDE-", "").replace(".md", "");
      const handoffDir = path.join(projectDir, "thoughts", "shared", "handoffs", sessionName);
      const latestHandoff = getLatestHandoff(handoffDir);
      if (sessionType === "startup") {
        let startupMsg = `\u{1F4CB} Ledger available: ${sessionName} \u2192 ${currentFocus}`;
        if (latestHandoff) {
          if (latestHandoff.isAutoHandoff) {
            startupMsg += ` | Last handoff: auto (${latestHandoff.status})`;
          } else {
            startupMsg += ` | Last handoff: task-${latestHandoff.taskNumber} (${latestHandoff.status})`;
          }
        }
        startupMsg += " (run /resume_handoff to continue)";
        message = startupMsg;
      } else {
        console.error(`\u2713 Ledger loaded: ${sessionName} \u2192 ${currentFocus}`);
        message = `[${sessionType}] Loaded: ${mostRecent} | Goal: ${goalSummary} | Focus: ${currentFocus}`;
        if (sessionType === "clear" || sessionType === "compact") {
          additionalContext = `Continuity ledger loaded from ${mostRecent}:

${ledgerContent}`;
          const unmarkedHandoffs = getUnmarkedHandoffs();
          if (unmarkedHandoffs.length > 0) {
            additionalContext += `

---

## Unmarked Session Outcomes

`;
            additionalContext += `The following handoffs have no outcome marked. Consider marking them to improve future session recommendations:

`;
            for (const h of unmarkedHandoffs) {
              const taskLabel = h.task_number ? `task-${h.task_number}` : "handoff";
              const summaryPreview = h.task_summary ? h.task_summary.substring(0, 60) + "..." : "(no summary)";
              additionalContext += `- **${h.session_name}/${taskLabel}** (ID: \`${h.id.substring(0, 8)}\`): ${summaryPreview}
`;
            }
            additionalContext += `
To mark an outcome:
\`\`\`bash
cd ~/.claude && uv run python scripts/core/artifact_mark.py --handoff <ID> --outcome SUCCEEDED|PARTIAL_PLUS|PARTIAL_MINUS|FAILED
\`\`\`
`;
          }
          if (latestHandoff) {
            const handoffPath = path.join(handoffDir, latestHandoff.filename);
            const handoffContent = fs.readFileSync(handoffPath, "utf-8");
            const handoffLabel = latestHandoff.isAutoHandoff ? "Latest auto-handoff" : "Latest task handoff";
            additionalContext += `

---

${handoffLabel} (${latestHandoff.filename}):
`;
            additionalContext += `Status: ${latestHandoff.status}${latestHandoff.isAutoHandoff ? "" : ` | Task: ${latestHandoff.taskNumber}`}

`;
            const truncatedHandoff = handoffContent.length > 2e3 ? handoffContent.substring(0, 2e3) + "\n\n[... truncated, read full file if needed]" : handoffContent;
            additionalContext += truncatedHandoff;
            const allHandoffs = fs.readdirSync(handoffDir).filter((f) => (f.startsWith("task-") || f.startsWith("auto-handoff-")) && isHandoffFile(f)).sort((a, b) => {
              const statA = fs.statSync(path.join(handoffDir, a));
              const statB = fs.statSync(path.join(handoffDir, b));
              return statB.mtime.getTime() - statA.mtime.getTime();
            });
            if (allHandoffs.length > 1) {
              additionalContext += `

---

All handoffs in ${handoffDir}:
`;
              allHandoffs.forEach((f) => {
                additionalContext += `- ${f}
`;
              });
            }
          }
        }
      }
    } else {
      if (sessionType !== "startup") {
        console.error(`\u26A0 No ledger found. Run /continuity_ledger to track session state.`);
        message = `[${sessionType}] No ledger found. Consider running /continuity_ledger to track session state.`;
      }
    }
  }
  const memoryIndexPath = path.join(projectDir, ".claude", "memory", "index.json");
  if (fs.existsSync(memoryIndexPath)) {
    try {
      const indexContent = fs.readFileSync(memoryIndexPath, "utf-8");
      const index = JSON.parse(indexContent);
      const sessionCount = Object.keys(index.sessions || {}).length;
      const topicCount = Object.keys(index.topic_index || {}).length;
      if (sessionCount > 0 || topicCount > 0) {
        const memorySummary = `

---

## Local Project Memory

Sessions indexed: ${sessionCount} | Topics: ${topicCount}
Query with: \`uv run python ~/.claude/scripts/core/core/project_memory.py query "<topic>" --project-dir "${projectDir}"\``;
        if (additionalContext) {
          additionalContext += memorySummary;
        } else if (sessionType === "clear" || sessionType === "compact") {
          additionalContext = memorySummary;
        }
      }
    } catch {
    }
  }
  const output = { result: "continue" };
  if (message) {
    output.message = message;
    output.systemMessage = message;
  }
  if (additionalContext) {
    output.hookSpecificOutput = {
      hookEventName: "SessionStart",
      additionalContext
    };
  }
  console.log(JSON.stringify(output));
}
async function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.on("data", (chunk) => data += chunk);
    process.stdin.on("end", () => resolve(data));
  });
}
main().catch((err) => {
  console.error(err);
  console.log(JSON.stringify({ result: "continue" }));
});
export {
  buildHandoffDirName,
  extractLedgerSection,
  extractYamlFields,
  findSessionHandoff,
  findSessionHandoffWithUUID,
  parseHandoffDirName
};
