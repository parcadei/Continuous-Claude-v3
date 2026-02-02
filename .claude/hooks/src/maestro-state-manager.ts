#!/usr/bin/env node
/**
 * Maestro State Manager Hook
 *
 * Manages Maestro workflow state based on user prompts.
 * Runs on UserPromptSubmit.
 *
 * State transitions:
 * - "yes use maestro" / "orchestrate" → activates maestro mode
 * - User answers discovery questions → marks interview complete
 * - "approve" / "yes" / "proceed" (after plan shown) → marks plan approved
 * - "cancel maestro" / "stop orchestrating" → clears maestro state
 */

import { readFileSync, writeFileSync, existsSync, unlinkSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { outputContinue } from './shared/output.js';
import { getSessionStatePath, getStatePathWithMigration, cleanupOldStateFiles } from './shared/session-isolation.js';

interface HookInput {
  session_id?: string;
  prompt?: string;
}

interface MaestroState {
  active: boolean;
  taskType: 'implementation' | 'research' | 'unknown';
  reconComplete: boolean;  // For implementation: scout codebase first
  interviewComplete: boolean;
  planApproved: boolean;
  activatedAt: number;
  lastActivity?: number;   // For heartbeat mechanism
  sessionId?: string;      // Track which session owns this state
}

// Use session-specific state files to prevent cross-terminal collision
const STATE_BASE_NAME = 'maestro-state';
const STATE_TTL = 4 * 60 * 60 * 1000; // Extended to 4 hours

function getStateFile(sessionId?: string): string {
  return getStatePathWithMigration(STATE_BASE_NAME, sessionId);
}

function defaultState(): MaestroState {
  return {
    active: false,
    taskType: 'unknown',
    reconComplete: false,
    interviewComplete: false,
    planApproved: false,
    activatedAt: 0
  };
}

function readState(sessionId?: string): MaestroState {
  const stateFile = getStateFile(sessionId);
  if (!existsSync(stateFile)) {
    return defaultState();
  }
  try {
    const content = readFileSync(stateFile, 'utf-8');
    const state = JSON.parse(content) as MaestroState;

    // Check TTL based on lastActivity (heartbeat) or activatedAt
    const lastTime = state.lastActivity || state.activatedAt;
    if (Date.now() - lastTime > STATE_TTL) {
      return defaultState();
    }
    return state;
  } catch (err) {
    // Log corruption but return default (fail safe)
    console.error(`[Maestro] State file error: ${err}`);
    return defaultState();
  }
}

function writeState(state: MaestroState, sessionId?: string): void {
  const stateFile = getStateFile(sessionId);
  try {
    state.lastActivity = Date.now();
    state.sessionId = sessionId;
    writeFileSync(stateFile, JSON.stringify(state, null, 2), 'utf-8');
  } catch {
    // Ignore write errors
  }
}

function clearState(sessionId?: string): void {
  const stateFile = getStateFile(sessionId);
  try {
    if (existsSync(stateFile)) {
      unlinkSync(stateFile);
    }
  } catch {
    // Ignore
  }
}

function readStdin(): string {
  return readFileSync(0, 'utf-8');
}

// Patterns for state transitions
const ACTIVATION_PATTERNS = [
  /\b(yes,?\s*)?use\s+maestro\b/i,
  /\borchestrate\s+(this|it)\b/i,
  /\bstart\s+maestro\b/i,
  /\bmaestro\s+mode\b/i,
  /^\/maestro$/i,
];

const RECON_COMPLETE_PATTERNS = [
  /\brecon\s+complete\b/i,
  /\bexploration\s+complete\b/i,
  /\bscouting\s+(is\s+)?complete\b/i,
  /\bdone\s+(with\s+)?(recon|exploration|scouting)\b/i,
];

const INTERVIEW_COMPLETE_PATTERNS: PatternSet = {
  positive: [
    /^interview\s+complete[\s\.!]*$/i,
    /^discovery\s+complete[\s\.!]*$/i,
    /^done\s+(with\s+)?(interview|questions)[\s\.!]*$/i,
    /\bthe\s+interview\s+is\s+complete\b/i,
  ],
  negative: [
    /\?/,
    /\bnot\b/i,
    /\bmore\s+questions\b/i,
    /\bstill\b/i,
    /\bwhen\b/i,
    /\blet\s+me\s+know\b/i,
    /\bshould\b/i,
    /\bsignal\b/i,
  ]
};

// Patterns to detect task type from original request
const IMPLEMENTATION_PATTERNS = [
  /\b(build|create|implement|add|develop|make|write)\b/i,
  /\b(feature|component|service|api|endpoint|module)\b/i,
  /\b(fix|debug|refactor|update|change)\b/i,
];

const RESEARCH_PATTERNS = [
  /\b(research|understand|learn|explore|how\s+does|what\s+is)\b/i,
  /\b(best\s+practices|documentation|docs|patterns)\b/i,
];

const PLAN_APPROVAL_PATTERNS: PatternSet = {
  positive: [
    /^(yes|approve|approved|proceed|go\s*ahead|looks\s*good|do\s*it|lgtm)[\s,\.!]*$/i,
    /^yes,?\s*(proceed|go\s*ahead|do\s*it|let'?s?\s*(do|go))[\s\.!]*$/i,
    /\bapprove\s+(the\s+)?plan\b/i,
    /\bplan\s+approved\b/i,
    /\bproceed\s+with\s+(the\s+)?plan\b/i,
  ],
  negative: [
    /\bbut\b/i,
    /\bhowever\b/i,
    /\bwait\b/i,
    /\bhold\s+on\b/i,
    /\?/,
    /\bfirst\b/i,
    /\bbefore\b/i,
    /\bconcern/i,
    /\bquestion/i,
    /\bmaybe\b/i,
    /\bnot\s+yet\b/i,
  ]
};

const CANCEL_PATTERNS: PatternSet = {
  positive: [
    /\bcancel\s+maestro\b/i,
    /\bstop\s+orchestrat/i,
    /\bexit\s+maestro\b/i,
    /\bdisable\s+maestro\b/i,
  ],
  negative: [
    /\bdon'?t\b/i,
    /\bdo\s+not\b/i,
    /\bkeep\b/i,
    /\bwait\b/i,
    /\bnot\s+yet\b/i,
    /\bshould\s+i\b/i,
    /\bif\s+(this|it|we|I)\b/i,
    /\bI'?ll\b/i,
    /\?/,
  ]
};

interface PatternSet {
  positive: RegExp[];
  negative?: RegExp[];
}

function matchesAny(text: string, patterns: RegExp[]): boolean {
  return patterns.some(p => p.test(text));
}

function matchesPattern(text: string, patternSet: PatternSet | RegExp[]): boolean {
  if (Array.isArray(patternSet)) {
    return matchesAny(text, patternSet);
  }
  if (patternSet.negative && matchesAny(text, patternSet.negative)) {
    return false;
  }
  return matchesAny(text, patternSet.positive);
}

async function main() {
  try {
    // Periodic cleanup of old state files (1 in 100 calls)
    if (Math.random() < 0.01) {
      cleanupOldStateFiles(STATE_BASE_NAME);
    }

    const rawInput = readStdin();
    if (!rawInput.trim()) {
      outputContinue();
      return;
    }

    let input: HookInput;
    try {
      input = JSON.parse(rawInput);
    } catch {
      outputContinue();
      return;
    }

    if (!input.prompt || typeof input.prompt !== 'string') {
      outputContinue();
      return;
    }

    const sessionId = input.session_id;
    const prompt = input.prompt.trim();
    const state = readState(sessionId);

    // Check for cancel
    if (matchesPattern(prompt, CANCEL_PATTERNS)) {
      clearState(sessionId);
      console.log(`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎼 MAESTRO DEACTIVATED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Maestro orchestration mode disabled.
Returning to normal operation.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);
      outputContinue();
      return;
    }

    // Check for activation
    if (!state.active && matchesAny(prompt, ACTIVATION_PATTERNS)) {
      // Detect task type from the conversation context
      // For now, default to implementation (which includes recon phase)
      // Research tasks skip recon
      const isResearch = matchesAny(prompt, RESEARCH_PATTERNS) && !matchesAny(prompt, IMPLEMENTATION_PATTERNS);
      const taskType = isResearch ? 'research' : 'implementation';

      writeState({
        active: true,
        taskType,
        reconComplete: isResearch, // Research tasks skip recon
        interviewComplete: false,
        planApproved: false,
        activatedAt: Date.now()
      }, sessionId);

      if (isResearch) {
        console.log(`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎼 MAESTRO ACTIVATED (Research Mode)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Task Type: **RESEARCH** (external docs, best practices)

**WORKFLOW:**
1. ⏳ Discovery Interview (CURRENT)
2. ⏳ Propose Plan
3. ⏳ Await Approval
4. ⏳ Execute

**YOUR FIRST ACTION:**
Use AskUserQuestion to clarify:
- What specifically to research?
- What format for findings?
- Any constraints or preferences?

Task tool BLOCKED until interview complete.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);
      } else {
        console.log(`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎼 MAESTRO ACTIVATED (Implementation Mode)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Task Type: **IMPLEMENTATION** (coding, building, fixing)

**WORKFLOW:**
1. ⏳ Codebase Recon (CURRENT) ← scout allowed
2. ⏳ Discovery Interview
3. ⏳ Propose Plan
4. ⏳ Await Approval
5. ⏳ Execute

**YOUR FIRST ACTION:**
Spawn 1-2 scout agents to understand codebase:
- Existing patterns relevant to task
- File structure and conventions
- Related code that might be affected

Only scout agents allowed. Other agents BLOCKED.
Say "recon complete" when done exploring.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);
      }
      outputContinue();
      return;
    }

    // If maestro is active, check for state transitions
    if (state.active) {
      // Check for recon completion (implementation tasks only)
      if (!state.reconComplete && matchesAny(prompt, RECON_COMPLETE_PATTERNS)) {
        state.reconComplete = true;
        writeState(state, sessionId);
        console.log(`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎼 MAESTRO: Recon Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**WORKFLOW PROGRESS:**
1. ✅ Codebase Recon
2. ⏳ Discovery Interview (CURRENT)
3. ⏳ Propose Plan
4. ⏳ Await Approval
5. ⏳ Execute

**YOUR NEXT ACTION:**
Use AskUserQuestion with INFORMED questions based on recon:
- "I found X pattern, should we follow it?"
- "Existing code uses Y approach, continue or change?"
- "This will affect N files, confirm scope?"

Task tool BLOCKED until interview complete.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);
        outputContinue();
        return;
      }

      // Check for interview completion
      if (state.reconComplete && !state.interviewComplete && matchesPattern(prompt, INTERVIEW_COMPLETE_PATTERNS)) {
        state.interviewComplete = true;
        writeState(state, sessionId);
        const step = state.taskType === 'research' ? 1 : 2;
        console.log(`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎼 MAESTRO: Interview Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**WORKFLOW PROGRESS:**
${state.taskType === 'implementation' ? '1. ✅ Codebase Recon\n2. ✅ Discovery Interview' : '1. ✅ Discovery Interview'}
${state.taskType === 'implementation' ? '3' : '2'}. ⏳ Propose Plan (CURRENT)
${state.taskType === 'implementation' ? '4' : '3'}. ⏳ Await Approval
${state.taskType === 'implementation' ? '5' : '4'}. ⏳ Execute

**YOUR NEXT ACTION:**
Present orchestration plan to user.
Task tool still BLOCKED until plan approved.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);
        outputContinue();
        return;
      }

      // Check for plan approval (only if interview complete)
      if (state.interviewComplete && !state.planApproved && matchesPattern(prompt, PLAN_APPROVAL_PATTERNS)) {
        state.planApproved = true;
        writeState(state, sessionId);
        console.log(`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎼 MAESTRO: Plan Approved
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**WORKFLOW PROGRESS:**
1. ✅ Discovery Interview
2. ✅ Propose Plan
3. ✅ Await Approval
4. ⏳ Execute (CURRENT)

**Task tool is now UNBLOCKED.**
You may spawn agents to execute the plan.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);
        outputContinue();
        return;
      }

      // If maestro active but interview not complete, remind about workflow
      if (!state.interviewComplete) {
        // Check if this looks like user answering questions (contains selections/answers)
        const looksLikeAnswers = /\b(build|fix|research|refactor|single|module|system|full|code|plan|understanding|all)\b/i.test(prompt)
          && prompt.length < 200;

        if (looksLikeAnswers) {
          // User is answering questions - mark interview potentially complete
          state.interviewComplete = true;
          writeState(state);
          console.log(`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎼 MAESTRO: Answers Received
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Discovery answers received.

**YOUR NEXT ACTION:**
1. Classify task type based on answers
2. Present orchestration plan
3. Wait for approval

Task tool still BLOCKED until plan approved.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`);
          outputContinue();
          return;
        }
      }
    }

    // No state transition - output continue
    outputContinue();
  } catch (err) {
    // Fail silently
    outputContinue();
  }
}

main();
