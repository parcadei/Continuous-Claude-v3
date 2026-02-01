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

interface HookInput {
  prompt?: string;
}

interface MaestroState {
  active: boolean;
  taskType: 'implementation' | 'research' | 'unknown';
  reconComplete: boolean;  // For implementation: scout codebase first
  interviewComplete: boolean;
  planApproved: boolean;
  activatedAt: number;
}

const STATE_FILE = join(tmpdir(), 'claude-maestro-state.json');
const STATE_TTL = 60 * 60 * 1000; // 1 hour

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

function readState(): MaestroState {
  if (!existsSync(STATE_FILE)) {
    return defaultState();
  }
  try {
    const content = readFileSync(STATE_FILE, 'utf-8');
    const state = JSON.parse(content) as MaestroState;
    if (Date.now() - state.activatedAt > STATE_TTL) {
      return defaultState();
    }
    return state;
  } catch {
    return defaultState();
  }
}

function writeState(state: MaestroState): void {
  try {
    writeFileSync(STATE_FILE, JSON.stringify(state), 'utf-8');
  } catch {
    // Ignore write errors
  }
}

function clearState(): void {
  try {
    if (existsSync(STATE_FILE)) {
      unlinkSync(STATE_FILE);
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

const INTERVIEW_COMPLETE_PATTERNS = [
  /\binterview\s+complete\b/i,
  /\bdiscovery\s+complete\b/i,
  /\bdone\s+(with\s+)?(interview|questions)\b/i,
];

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

const PLAN_APPROVAL_PATTERNS = [
  /^(yes|approve|approved|proceed|go\s*ahead|looks\s*good|do\s*it|lgtm)\.?$/i,
  /\bapprove\s+(the\s+)?plan\b/i,
  /\bplan\s+approved\b/i,
  /\bproceed\s+with\s+(the\s+)?plan\b/i,
];

const CANCEL_PATTERNS = [
  /\bcancel\s+maestro\b/i,
  /\bstop\s+orchestrat/i,
  /\bexit\s+maestro\b/i,
  /\bdisable\s+maestro\b/i,
];

function matchesAny(text: string, patterns: RegExp[]): boolean {
  return patterns.some(p => p.test(text));
}

async function main() {
  try {
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

    const prompt = input.prompt.trim();
    const state = readState();

    // Check for cancel
    if (matchesAny(prompt, CANCEL_PATTERNS)) {
      clearState();
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
      });

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
        writeState(state);
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
      if (state.reconComplete && !state.interviewComplete && matchesAny(prompt, INTERVIEW_COMPLETE_PATTERNS)) {
        state.interviewComplete = true;
        writeState(state);
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
      if (state.interviewComplete && !state.planApproved && matchesAny(prompt, PLAN_APPROVAL_PATTERNS)) {
        state.planApproved = true;
        writeState(state);
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
