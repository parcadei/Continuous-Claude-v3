#!/usr/bin/env node

// src/guardrail-enforcer.ts
import { readFileSync, writeFileSync, existsSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

// src/shared/output.ts
function outputContinue() {
  console.log(JSON.stringify({ result: "continue" }));
}

// src/guardrail-enforcer.ts
var GUARDRAILS = [
  {
    name: "systematic-debugging",
    skill: "systematic-debugging",
    triggers: /\b(bug|error|fix|debug|broken|failing|crash|exception|stack\s*trace)\b/i,
    antiTriggers: /\b(commit\s+to|commit\s+the\s+approach|no\s+bugs?|without\s+errors?)\b/i,
    message: `\u{1F6D1} GUARDRAIL: Debugging methodology required

Before investigating bugs/errors, you MUST load the systematic-debugging skill.

**ACTION REQUIRED:**
1. Invoke the Skill tool: { "skill": "systematic-debugging" }
2. THEN respond to the user's debugging request

This ensures proper root cause analysis before fixes.
Do NOT attempt fixes without understanding the root cause first.`
  },
  {
    name: "databases",
    skill: "databases",
    triggers: /\b(database|sql|query|postgres|mysql|migration|schema|table|column|index)\b/i,
    antiTriggers: /\b(no\s+database|without\s+database|skip\s+database)\b/i,
    message: `\u{1F6D1} GUARDRAIL: Database skill required

Before database operations, you MUST load the databases skill.

**ACTION REQUIRED:**
1. Invoke the Skill tool: { "skill": "databases" }
2. THEN proceed with database work

This ensures query optimization and safety checks.
Do NOT write SQL without the database skill loaded.`
  },
  {
    name: "code-review",
    skill: "code-review",
    triggers: /\b(pr|pull\s*request|review|merge|approve|code\s*review)\b/i,
    antiTriggers: /\b(no\s+review|skip\s+review|review\s+later)\b/i,
    message: `\u{1F6D1} GUARDRAIL: Code review methodology required

Before PR/review work, you MUST load the code-review skill.

**ACTION REQUIRED:**
1. Invoke the Skill tool: { "skill": "code-review" }
2. THEN proceed with review work

This ensures thorough review methodology.
Do NOT approve PRs without proper verification.`
  }
];
function getSessionId() {
  return process.env.CLAUDE_SESSION_ID || String(process.ppid || process.pid);
}
function getSessionFilePath() {
  const sessionId = getSessionId().slice(0, 8);
  return join(tmpdir(), `claude-guardrails-${sessionId}.json`);
}
function readSessionState() {
  const filePath = getSessionFilePath();
  if (!existsSync(filePath)) {
    return { acknowledgedGuardrails: [], lastUpdated: Date.now() };
  }
  try {
    const content = readFileSync(filePath, "utf-8");
    const state = JSON.parse(content);
    const hourAgo = Date.now() - 60 * 60 * 1e3;
    if (state.lastUpdated < hourAgo) {
      return { acknowledgedGuardrails: [], lastUpdated: Date.now() };
    }
    return state;
  } catch {
    return { acknowledgedGuardrails: [], lastUpdated: Date.now() };
  }
}
function writeSessionState(state) {
  const filePath = getSessionFilePath();
  try {
    writeFileSync(filePath, JSON.stringify(state), "utf-8");
  } catch {
  }
}
function acknowledgeGuardrail(guardrailName) {
  const state = readSessionState();
  if (!state.acknowledgedGuardrails.includes(guardrailName)) {
    state.acknowledgedGuardrails.push(guardrailName);
    state.lastUpdated = Date.now();
    writeSessionState(state);
  }
}
function isGuardrailAcknowledged(guardrailName) {
  const state = readSessionState();
  return state.acknowledgedGuardrails.includes(guardrailName);
}
function readStdin() {
  return readFileSync(0, "utf-8");
}
function checkGuardrails(prompt) {
  const lowerPrompt = prompt.toLowerCase();
  for (const guardrail of GUARDRAILS) {
    if (guardrail.triggers.test(lowerPrompt)) {
      if (guardrail.antiTriggers && guardrail.antiTriggers.test(lowerPrompt)) {
        continue;
      }
      if (isGuardrailAcknowledged(guardrail.name)) {
        continue;
      }
      return guardrail;
    }
  }
  return null;
}
function makeBlockOutput(guardrail) {
  acknowledgeGuardrail(guardrail.name);
  return guardrail.message;
}
async function main() {
  try {
    const rawInput = readStdin();
    if (!rawInput.trim()) {
      outputContinue();
      return;
    }
    let input;
    try {
      input = JSON.parse(rawInput);
    } catch {
      outputContinue();
      return;
    }
    if (!input.prompt || typeof input.prompt !== "string") {
      outputContinue();
      return;
    }
    const triggeredGuardrail = checkGuardrails(input.prompt);
    if (triggeredGuardrail) {
      console.log(makeBlockOutput(triggeredGuardrail));
      return;
    }
    outputContinue();
  } catch (err) {
    console.error("guardrail-enforcer error:", err);
    outputContinue();
  }
}
main();
