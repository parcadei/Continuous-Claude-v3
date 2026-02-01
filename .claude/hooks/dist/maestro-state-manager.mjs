#!/usr/bin/env node

// src/maestro-state-manager.ts
import { readFileSync, writeFileSync, existsSync, unlinkSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

// src/shared/output.ts
function outputContinue() {
  console.log(JSON.stringify({ result: "continue" }));
}

// src/maestro-state-manager.ts
var STATE_FILE = join(tmpdir(), "claude-maestro-state.json");
var STATE_TTL = 60 * 60 * 1e3;
function defaultState() {
  return {
    active: false,
    taskType: "unknown",
    reconComplete: false,
    interviewComplete: false,
    planApproved: false,
    activatedAt: 0
  };
}
function readState() {
  if (!existsSync(STATE_FILE)) {
    return defaultState();
  }
  try {
    const content = readFileSync(STATE_FILE, "utf-8");
    const state = JSON.parse(content);
    if (Date.now() - state.activatedAt > STATE_TTL) {
      return defaultState();
    }
    return state;
  } catch {
    return defaultState();
  }
}
function writeState(state) {
  try {
    writeFileSync(STATE_FILE, JSON.stringify(state), "utf-8");
  } catch {
  }
}
function clearState() {
  try {
    if (existsSync(STATE_FILE)) {
      unlinkSync(STATE_FILE);
    }
  } catch {
  }
}
function readStdin() {
  return readFileSync(0, "utf-8");
}
var ACTIVATION_PATTERNS = [
  /\b(yes,?\s*)?use\s+maestro\b/i,
  /\borchestrate\s+(this|it)\b/i,
  /\bstart\s+maestro\b/i,
  /\bmaestro\s+mode\b/i,
  /^\/maestro$/i
];
var RECON_COMPLETE_PATTERNS = [
  /\brecon\s+complete\b/i,
  /\bexploration\s+complete\b/i,
  /\bscouting\s+(is\s+)?complete\b/i,
  /\bdone\s+(with\s+)?(recon|exploration|scouting)\b/i
];
var INTERVIEW_COMPLETE_PATTERNS = [
  /\binterview\s+complete\b/i,
  /\bdiscovery\s+complete\b/i,
  /\bdone\s+(with\s+)?(interview|questions)\b/i
];
var IMPLEMENTATION_PATTERNS = [
  /\b(build|create|implement|add|develop|make|write)\b/i,
  /\b(feature|component|service|api|endpoint|module)\b/i,
  /\b(fix|debug|refactor|update|change)\b/i
];
var RESEARCH_PATTERNS = [
  /\b(research|understand|learn|explore|how\s+does|what\s+is)\b/i,
  /\b(best\s+practices|documentation|docs|patterns)\b/i
];
var PLAN_APPROVAL_PATTERNS = [
  /^(yes|approve|approved|proceed|go\s*ahead|looks\s*good|do\s*it|lgtm)\.?$/i,
  /\bapprove\s+(the\s+)?plan\b/i,
  /\bplan\s+approved\b/i,
  /\bproceed\s+with\s+(the\s+)?plan\b/i
];
var CANCEL_PATTERNS = [
  /\bcancel\s+maestro\b/i,
  /\bstop\s+orchestrat/i,
  /\bexit\s+maestro\b/i,
  /\bdisable\s+maestro\b/i
];
function matchesAny(text, patterns) {
  return patterns.some((p) => p.test(text));
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
    const prompt = input.prompt.trim();
    const state = readState();
    if (matchesAny(prompt, CANCEL_PATTERNS)) {
      clearState();
      console.log(`
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u{1F3BC} MAESTRO DEACTIVATED
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
Maestro orchestration mode disabled.
Returning to normal operation.
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
`);
      outputContinue();
      return;
    }
    if (!state.active && matchesAny(prompt, ACTIVATION_PATTERNS)) {
      const isResearch = matchesAny(prompt, RESEARCH_PATTERNS) && !matchesAny(prompt, IMPLEMENTATION_PATTERNS);
      const taskType = isResearch ? "research" : "implementation";
      writeState({
        active: true,
        taskType,
        reconComplete: isResearch,
        // Research tasks skip recon
        interviewComplete: false,
        planApproved: false,
        activatedAt: Date.now()
      });
      if (isResearch) {
        console.log(`
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u{1F3BC} MAESTRO ACTIVATED (Research Mode)
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

Task Type: **RESEARCH** (external docs, best practices)

**WORKFLOW:**
1. \u23F3 Discovery Interview (CURRENT)
2. \u23F3 Propose Plan
3. \u23F3 Await Approval
4. \u23F3 Execute

**YOUR FIRST ACTION:**
Use AskUserQuestion to clarify:
- What specifically to research?
- What format for findings?
- Any constraints or preferences?

Task tool BLOCKED until interview complete.
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
`);
      } else {
        console.log(`
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u{1F3BC} MAESTRO ACTIVATED (Implementation Mode)
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

Task Type: **IMPLEMENTATION** (coding, building, fixing)

**WORKFLOW:**
1. \u23F3 Codebase Recon (CURRENT) \u2190 scout allowed
2. \u23F3 Discovery Interview
3. \u23F3 Propose Plan
4. \u23F3 Await Approval
5. \u23F3 Execute

**YOUR FIRST ACTION:**
Spawn 1-2 scout agents to understand codebase:
- Existing patterns relevant to task
- File structure and conventions
- Related code that might be affected

Only scout agents allowed. Other agents BLOCKED.
Say "recon complete" when done exploring.
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
`);
      }
      outputContinue();
      return;
    }
    if (state.active) {
      if (!state.reconComplete && matchesAny(prompt, RECON_COMPLETE_PATTERNS)) {
        state.reconComplete = true;
        writeState(state);
        console.log(`
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u{1F3BC} MAESTRO: Recon Complete
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

**WORKFLOW PROGRESS:**
1. \u2705 Codebase Recon
2. \u23F3 Discovery Interview (CURRENT)
3. \u23F3 Propose Plan
4. \u23F3 Await Approval
5. \u23F3 Execute

**YOUR NEXT ACTION:**
Use AskUserQuestion with INFORMED questions based on recon:
- "I found X pattern, should we follow it?"
- "Existing code uses Y approach, continue or change?"
- "This will affect N files, confirm scope?"

Task tool BLOCKED until interview complete.
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
`);
        outputContinue();
        return;
      }
      if (state.reconComplete && !state.interviewComplete && matchesAny(prompt, INTERVIEW_COMPLETE_PATTERNS)) {
        state.interviewComplete = true;
        writeState(state);
        const step = state.taskType === "research" ? 1 : 2;
        console.log(`
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u{1F3BC} MAESTRO: Interview Complete
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

**WORKFLOW PROGRESS:**
${state.taskType === "implementation" ? "1. \u2705 Codebase Recon\n2. \u2705 Discovery Interview" : "1. \u2705 Discovery Interview"}
${state.taskType === "implementation" ? "3" : "2"}. \u23F3 Propose Plan (CURRENT)
${state.taskType === "implementation" ? "4" : "3"}. \u23F3 Await Approval
${state.taskType === "implementation" ? "5" : "4"}. \u23F3 Execute

**YOUR NEXT ACTION:**
Present orchestration plan to user.
Task tool still BLOCKED until plan approved.
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
`);
        outputContinue();
        return;
      }
      if (state.interviewComplete && !state.planApproved && matchesAny(prompt, PLAN_APPROVAL_PATTERNS)) {
        state.planApproved = true;
        writeState(state);
        console.log(`
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u{1F3BC} MAESTRO: Plan Approved
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

**WORKFLOW PROGRESS:**
1. \u2705 Discovery Interview
2. \u2705 Propose Plan
3. \u2705 Await Approval
4. \u23F3 Execute (CURRENT)

**Task tool is now UNBLOCKED.**
You may spawn agents to execute the plan.
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
`);
        outputContinue();
        return;
      }
      if (!state.interviewComplete) {
        const looksLikeAnswers = /\b(build|fix|research|refactor|single|module|system|full|code|plan|understanding|all)\b/i.test(prompt) && prompt.length < 200;
        if (looksLikeAnswers) {
          state.interviewComplete = true;
          writeState(state);
          console.log(`
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u{1F3BC} MAESTRO: Answers Received
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

Discovery answers received.

**YOUR NEXT ACTION:**
1. Classify task type based on answers
2. Present orchestration plan
3. Wait for approval

Task tool still BLOCKED until plan approved.
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
`);
          outputContinue();
          return;
        }
      }
    }
    outputContinue();
  } catch (err) {
    outputContinue();
  }
}
main();
