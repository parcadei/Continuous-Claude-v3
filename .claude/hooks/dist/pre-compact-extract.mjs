#!/usr/bin/env node

// src/pre-compact-extract.ts
import { spawnSync } from "child_process";
import * as fs from "fs";
import * as path from "path";
function getOpcDir() {
  return process.env.CLAUDE_OPC_DIR || path.join(process.env.HOME || process.env.USERPROFILE || "", "continuous-claude", "opc");
}
function getStateFilePath(projectDir) {
  return path.join(projectDir, ".claude", "extraction-state.json");
}
function loadState(stateFile) {
  if (!fs.existsSync(stateFile)) {
    return { last_extracted_line: 0, recent_hashes: [] };
  }
  try {
    const data = JSON.parse(fs.readFileSync(stateFile, "utf-8"));
    return {
      last_extracted_line: data.last_extracted_line || 0,
      recent_hashes: data.recent_hashes || []
    };
  } catch {
    return { last_extracted_line: 0, recent_hashes: [] };
  }
}
function runIncrementalExtraction(transcriptPath, sessionId, startLine, stateFile, projectDir) {
  const opcDir = getOpcDir();
  const extractScript = path.join(opcDir, "scripts", "core", "incremental_extract.py");
  if (!fs.existsSync(extractScript)) {
    console.error(`incremental_extract.py not found at ${extractScript}`);
    return null;
  }
  const args = [
    "run",
    "python",
    "scripts/core/incremental_extract.py",
    "--transcript",
    transcriptPath,
    "--session-id",
    sessionId,
    "--start-line",
    startLine.toString(),
    "--state-file",
    stateFile,
    "--project-dir",
    projectDir,
    "--max-learnings",
    "5",
    // Keep extraction quick
    "--json"
  ];
  const result = spawnSync("uv", args, {
    encoding: "utf-8",
    cwd: opcDir,
    env: {
      ...process.env,
      PYTHONPATH: opcDir
    },
    timeout: 15e3
    // 15 second timeout
  });
  if (result.status !== 0) {
    console.error(`Extraction failed: ${result.stderr}`);
    return null;
  }
  try {
    return JSON.parse(result.stdout.trim());
  } catch {
    console.error(`Failed to parse extraction result: ${result.stdout}`);
    return null;
  }
}
async function main() {
  const input = await readStdin();
  if (!input.trim()) {
    console.log(JSON.stringify({ continue: true }));
    return;
  }
  let data;
  try {
    data = JSON.parse(input);
  } catch {
    console.log(JSON.stringify({ continue: true }));
    return;
  }
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const sessionId = data.session_id;
  const transcriptPath = data.transcript_path;
  if (data.trigger !== "auto") {
    const output2 = {
      continue: true,
      systemMessage: "[PreCompact] Manual compact - skipping auto-extraction"
    };
    console.log(JSON.stringify(output2));
    return;
  }
  if (!transcriptPath || !fs.existsSync(transcriptPath)) {
    const output2 = {
      continue: true,
      systemMessage: "[PreCompact] No transcript available for extraction"
    };
    console.log(JSON.stringify(output2));
    return;
  }
  const stateFile = getStateFilePath(projectDir);
  const state = loadState(stateFile);
  const result = runIncrementalExtraction(
    transcriptPath,
    sessionId,
    state.last_extracted_line,
    stateFile,
    projectDir
  );
  if (!result) {
    const output2 = {
      continue: true,
      systemMessage: "[PreCompact] Memory extraction unavailable"
    };
    console.log(JSON.stringify(output2));
    return;
  }
  const parts = [];
  if (result.learnings_stored > 0) {
    parts.push(`${result.learnings_stored} learnings captured`);
  }
  if (result.learnings_deduped > 0) {
    parts.push(`${result.learnings_deduped} skipped (duplicate)`);
  }
  if (result.errors && result.errors.length > 0) {
    parts.push(`${result.errors.length} errors`);
  }
  const message = parts.length > 0 ? `[PreCompact:L0] Memory extraction: ${parts.join(", ")}` : "[PreCompact:L0] No new learnings to extract";
  const output = {
    continue: true,
    systemMessage: message
  };
  console.log(JSON.stringify(output));
}
async function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf-8");
    process.stdin.on("data", (chunk) => data += chunk);
    process.stdin.on("end", () => resolve(data));
  });
}
main().catch((err) => {
  console.error("pre-compact-extract error:", err);
  console.log(JSON.stringify({ continue: true }));
});
