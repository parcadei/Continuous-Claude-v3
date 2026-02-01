#!/usr/bin/env node
/**
 * Guardrail Enforcer Hook
 *
 * Enforces mandatory skill loading for critical actions.
 * These are HARD BLOCKS - Claude must load the skill before proceeding.
 *
 * Tier 1 Guardrails:
 * - systematic-debugging: Required before bug/error/fix work
 * - databases: Required before SQL/query/schema work
 * - code-review: Required before PR/review/merge work
 *
 * Session Tracking:
 * - Uses temp file to track which skills have been "acknowledged" this session
 * - First trigger blocks, subsequent prompts pass through
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { outputContinue } from './shared/output.js';

interface Guardrail {
  name: string;
  skill: string;
  triggers: RegExp;
  antiTriggers?: RegExp;
  message: string;
}

const GUARDRAILS: Guardrail[] = [
  {
    name: 'systematic-debugging',
    skill: 'systematic-debugging',
    triggers: /\b(bug|error|fix|debug|broken|failing|crash|exception|stack\s*trace)\b/i,
    antiTriggers: /\b(commit\s+to|commit\s+the\s+approach|no\s+bugs?|without\s+errors?)\b/i,
    message: `🛑 GUARDRAIL: Debugging methodology required

Before investigating bugs/errors, you MUST load the systematic-debugging skill.

**ACTION REQUIRED:**
1. Invoke the Skill tool: { "skill": "systematic-debugging" }
2. THEN respond to the user's debugging request

This ensures proper root cause analysis before fixes.
Do NOT attempt fixes without understanding the root cause first.`
  },
  {
    name: 'databases',
    skill: 'databases',
    triggers: /\b(database|sql|query|postgres|mysql|migration|schema|table|column|index)\b/i,
    antiTriggers: /\b(no\s+database|without\s+database|skip\s+database)\b/i,
    message: `🛑 GUARDRAIL: Database skill required

Before database operations, you MUST load the databases skill.

**ACTION REQUIRED:**
1. Invoke the Skill tool: { "skill": "databases" }
2. THEN proceed with database work

This ensures query optimization and safety checks.
Do NOT write SQL without the database skill loaded.`
  },
  {
    name: 'code-review',
    skill: 'code-review',
    triggers: /\b(pr|pull\s*request|review|merge|approve|code\s*review)\b/i,
    antiTriggers: /\b(no\s+review|skip\s+review|review\s+later)\b/i,
    message: `🛑 GUARDRAIL: Code review methodology required

Before PR/review work, you MUST load the code-review skill.

**ACTION REQUIRED:**
1. Invoke the Skill tool: { "skill": "code-review" }
2. THEN proceed with review work

This ensures thorough review methodology.
Do NOT approve PRs without proper verification.`
  }
];

interface HookInput {
  prompt?: string;
  session_id?: string;
  conversation_id?: string;
}

interface HookOutput {
  result: 'continue' | 'block';
  reason?: string;
}

interface SessionState {
  acknowledgedGuardrails: string[];
  lastUpdated: number;
}

function getSessionId(): string {
  return process.env.CLAUDE_SESSION_ID || String(process.ppid || process.pid);
}

function getSessionFilePath(): string {
  const sessionId = getSessionId().slice(0, 8);
  return join(tmpdir(), `claude-guardrails-${sessionId}.json`);
}

function readSessionState(): SessionState {
  const filePath = getSessionFilePath();
  if (!existsSync(filePath)) {
    return { acknowledgedGuardrails: [], lastUpdated: Date.now() };
  }

  try {
    const content = readFileSync(filePath, 'utf-8');
    const state = JSON.parse(content) as SessionState;
    const hourAgo = Date.now() - (60 * 60 * 1000);
    if (state.lastUpdated < hourAgo) {
      return { acknowledgedGuardrails: [], lastUpdated: Date.now() };
    }
    return state;
  } catch {
    return { acknowledgedGuardrails: [], lastUpdated: Date.now() };
  }
}

function writeSessionState(state: SessionState): void {
  const filePath = getSessionFilePath();
  try {
    writeFileSync(filePath, JSON.stringify(state), 'utf-8');
  } catch {
  }
}

function acknowledgeGuardrail(guardrailName: string): void {
  const state = readSessionState();
  if (!state.acknowledgedGuardrails.includes(guardrailName)) {
    state.acknowledgedGuardrails.push(guardrailName);
    state.lastUpdated = Date.now();
    writeSessionState(state);
  }
}

function isGuardrailAcknowledged(guardrailName: string): boolean {
  const state = readSessionState();
  return state.acknowledgedGuardrails.includes(guardrailName);
}

function readStdin(): string {
  return readFileSync(0, 'utf-8');
}

function checkGuardrails(prompt: string): Guardrail | null {
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

function makeBlockOutput(guardrail: Guardrail): string {
  acknowledgeGuardrail(guardrail.name);
  // UserPromptSubmit hooks can't truly block - they inject context
  // Output the message directly so Claude sees it as a system instruction
  return guardrail.message;
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

    const triggeredGuardrail = checkGuardrails(input.prompt);

    if (triggeredGuardrail) {
      // Output message directly - Claude sees this as injected context
      console.log(makeBlockOutput(triggeredGuardrail));
      return;
    }

    // No guardrail triggered - output continue
    outputContinue();
  } catch (err) {
    console.error('guardrail-enforcer error:', err);
    outputContinue();
  }
}

main();
