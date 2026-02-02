#!/usr/bin/env node

// src/agent-verification.ts
import { readFileSync, existsSync } from "fs";
var IMPLEMENTATION_AGENTS = ["kraken", "spark", "scribe", "herald"];
var TEST_AGENTS = ["arbiter", "atlas", "principal-sdet"];
var FILE_CREATION_PATTERNS = [
  /\bcreated?\s+(file|the\s+file)?\s*[`'"]?([^\s`'"]+\.(ts|js|tsx|jsx|py|go|rs|java|rb|css|html|json|yaml|yml|md))[`'"]?/gi,
  /\bwrote\s+(to\s+)?(file\s+)?[`'"]?([^\s`'"]+\.[a-z]+)[`'"]?/gi,
  /\badded\s+(file\s+)?[`'"]?([^\s`'"]+\.[a-z]+)[`'"]?/gi,
  /\bimplemented\s+in\s+[`'"]?([^\s`'"]+\.[a-z]+)[`'"]?/gi
];
var TEST_PASS_PATTERNS = [
  /\ball\s+(\d+\s+)?tests?\s+pass/i,
  /\btests?\s+(are\s+)?passing/i,
  /\b(\d+)\s+tests?\s+passed/i,
  /\btest\s+suite\s+passed/i,
  /\bgreen\s+tests?/i,
  /\b100%\s+pass/i
];
var TEST_EXECUTION_EVIDENCE = [
  /\bPASSED\b/,
  /\bFAILED\b/,
  /\bERROR\b/,
  /\bran\s+\d+\s+tests?/i,
  /\btest\s+session\s+started/i,
  /\bpytest\b/i,
  /\bjest\b/i,
  /\bvitest\b/i,
  /\bmocha\b/i,
  /\bnpm\s+(run\s+)?test/i,
  /\bgo\s+test\b/i,
  /\bcargo\s+test\b/i,
  /\b\d+\s+(passed|failed|skipped)/i
];
var COMPLETION_PATTERNS = [
  /\b(task|implementation|work)\s+(is\s+)?complete/i,
  /\bsuccessfully\s+(implemented|completed|finished)/i,
  /\ball\s+(changes\s+)?done\b/i,
  /\bfinished\s+(implementing|the\s+task)/i
];
function readStdin() {
  return readFileSync(0, "utf-8");
}
function outputWithMessage(message) {
  if (message) {
    console.log(JSON.stringify({ message }));
  } else {
    console.log(JSON.stringify({}));
  }
}
function responseToString(response) {
  if (typeof response === "string") return response;
  if (response === null || response === void 0) return "";
  try {
    return JSON.stringify(response, null, 2);
  } catch {
    return String(response);
  }
}
function extractClaimedFiles(text) {
  const files = [];
  for (const pattern of FILE_CREATION_PATTERNS) {
    pattern.lastIndex = 0;
    let match;
    while ((match = pattern.exec(text)) !== null) {
      const file = match[3] || match[2] || match[1];
      if (file && !files.includes(file)) {
        files.push(file);
      }
    }
  }
  return files;
}
function verifyImplementationAgent(response) {
  const warnings = [];
  const claimsComplete = COMPLETION_PATTERNS.some((p) => p.test(response));
  if (claimsComplete) {
    const claimedFiles = extractClaimedFiles(response);
    if (claimedFiles.length === 0) {
      warnings.push("Agent claims completion but no specific files were mentioned as created/modified");
    } else {
      const missingFiles = [];
      for (const file of claimedFiles) {
        if (file.startsWith("/") || file.startsWith("C:") || !file.includes("/")) {
          if (!existsSync(file)) {
            missingFiles.push(file);
          }
        }
      }
      if (missingFiles.length > 0) {
        warnings.push(`Agent claimed to create files that don't exist: ${missingFiles.join(", ")}`);
      }
    }
  }
  return { verified: warnings.length === 0, warnings };
}
function verifyTestAgent(response) {
  const warnings = [];
  const claimsTestsPass = TEST_PASS_PATTERNS.some((p) => p.test(response));
  if (claimsTestsPass) {
    const hasExecutionEvidence = TEST_EXECUTION_EVIDENCE.some((p) => p.test(response));
    if (!hasExecutionEvidence) {
      warnings.push("Agent claims tests pass but no test execution output/evidence found in response");
    }
  }
  return { verified: warnings.length === 0, warnings };
}
function verifyAgent(agentType, response) {
  const lowerAgent = agentType.toLowerCase();
  if (IMPLEMENTATION_AGENTS.includes(lowerAgent)) {
    return verifyImplementationAgent(response);
  }
  if (TEST_AGENTS.includes(lowerAgent)) {
    return verifyTestAgent(response);
  }
  return { verified: true, warnings: [] };
}
async function main() {
  try {
    const rawInput = readStdin();
    if (!rawInput.trim()) {
      outputWithMessage();
      return;
    }
    let input;
    try {
      input = JSON.parse(rawInput);
    } catch {
      outputWithMessage();
      return;
    }
    if (input.tool_name !== "Task") {
      outputWithMessage();
      return;
    }
    const agentType = input.tool_input.subagent_type || "unknown";
    const responseStr = responseToString(input.tool_response);
    const result = verifyAgent(agentType, responseStr);
    if (!result.verified && result.warnings.length > 0) {
      const warningMessage = `
\u26A0\uFE0F AGENT VERIFICATION WARNING
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
Agent: ${agentType}
${result.warnings.map((w) => `\u2022 ${w}`).join("\n")}

Consider verifying the agent's claims before proceeding.
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501`;
      console.error(`[AgentVerification] ${result.warnings.join("; ")}`);
      outputWithMessage(warningMessage);
      return;
    }
    outputWithMessage();
  } catch (err) {
    console.error(`[AgentVerification] Hook error: ${err}`);
    outputWithMessage();
  }
}
main();
