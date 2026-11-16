#!/usr/bin/env node
/**
 * Erotetic Clarification Hook - REAL IEL Implementation
 *
 * This hook:
 * 1. Detects implementation tasks via pattern matching
 * 2. Extracts propositions from the prompt
 * 3. Calls z3_erotetic.py to compute E(X,Q)
 * 4. Returns ACTUAL unknowns for Claude to ask about
 */
import { readFileSync } from 'fs';
import { execSync } from 'child_process';
import {
    isImplementationTask,
    PROPOSITION_PATTERNS,
} from './shared/workflow-erotetic.js';

interface HookInput {
    prompt: string;
    session_id?: string;
    cwd?: string;
    skillName?: string;  // Skill name from skill-router (Phase 1 flywheel)
}

interface HookOutput {
    result: 'continue' | 'block';
    message?: string;
}

interface EvocationResult {
    isEmpty: boolean;
    unknowns: string[];
    count: number;
}

interface SkillCheckResult {
    status: 'complete' | 'incomplete' | 'error';
    unknowns: string[];
    knownParams: Record<string, string>;
    skillName: string;
}

/**
 * Detect skill name from input context.
 * Priority: explicit skillName field > skill-router context
 */
function detectSkillName(input: HookInput): string | null {
    // Explicit skill name from skill-router or caller
    if (input.skillName) {
        return input.skillName;
    }
    return null;
}

/**
 * Call skill-specific erotetic check CLI.
 * Returns parsed result or null on error.
 */
function callSkillCheckCLI(skillName: string, prompt: string, cwd: string): SkillCheckResult | null {
    try {
        const result = execSync(
            `uv run python scripts/erotetic_skill_check.py --skill '${skillName}' --prompt '${prompt.replace(/'/g, "'\\''")}'`,
            {
                cwd,
                encoding: 'utf-8',
                timeout: 5000,
                stdio: ['pipe', 'pipe', 'pipe']
            }
        );

        return JSON.parse(result.trim()) as SkillCheckResult;
    } catch (err) {
        // Return null on error - will fall back to generic evocation
        return null;
    }
}

/**
 * Extract propositions from the prompt using pattern matching.
 * Returns a dict where found values are strings, missing values are "UNKNOWN".
 */
function extractPropositions(prompt: string): Record<string, string> {
    const propositions: Record<string, string> = {};

    for (const [propName, pattern] of Object.entries(PROPOSITION_PATTERNS)) {
        const match = prompt.match(pattern);
        if (match) {
            propositions[propName] = match[0].toLowerCase();
        } else {
            propositions[propName] = "UNKNOWN";
        }
    }

    return propositions;
}

/**
 * Call z3_erotetic.py to compute E(X,Q).
 * Returns the evocation result or null on error.
 */
function computeEvocation(propositions: Record<string, string>, cwd: string): EvocationResult | null {
    try {
        const propsJson = JSON.stringify(propositions);

        // Use CLI wrapper for cleaner execution
        const result = execSync(
            `uv run python scripts/z3_erotetic_cli.py --props '${propsJson}'`,
            {
                cwd,
                encoding: 'utf-8',
                timeout: 5000,
                stdio: ['pipe', 'pipe', 'pipe']
            }
        );

        return JSON.parse(result.trim()) as EvocationResult;
    } catch (err) {
        // Return null on error - hook will fall back to heuristic message
        return null;
    }
}

/**
 * Generate the erotetic clarification message with ACTUAL E(X,Q) results.
 */
function getEroteticMessage(
    propositions: Record<string, string>,
    evocation: EvocationResult | null
): string {
    if (!evocation) {
        // Fallback if Z3 computation failed
        return `
EROTETIC CLARIFICATION PROTOCOL (Z3 unavailable - using heuristics)

This is an implementation task. Before proceeding, use AskUserQuestion to clarify:
- Framework/language choice
- Authentication method
- Database selection
- Hosting platform

Only proceed when all key decisions are resolved.
`.trim();
    }

    if (evocation.isEmpty) {
        // All propositions are known - no clarification needed
        return `
EROTETIC CHECK PASSED - E(X,Q) = {} (empty)

All propositions resolved from context:
${Object.entries(propositions)
    .filter(([_, v]) => v !== "UNKNOWN")
    .map(([k, v]) => `  - ${k}: ${v}`)
    .join('\n')}

Proceed with implementation.
`.trim();
    }

    // E(X,Q) is not empty - clarification needed
    return `
EROTETIC CLARIFICATION REQUIRED - E(X,Q) = {${evocation.unknowns.join(', ')}}

Formal evocation check found ${evocation.count} unresolved proposition(s):

UNKNOWNS (must clarify):
${evocation.unknowns.map(u => `  ❓ ${u}`).join('\n')}

KNOWN (from context):
${Object.entries(propositions)
    .filter(([_, v]) => v !== "UNKNOWN")
    .map(([k, v]) => `  ✓ ${k}: ${v}`)
    .join('\n') || '  (none extracted)'}

ACTION: Use AskUserQuestion to resolve the ${evocation.count} unknown(s) above.
Loop until E(X,Q) = {} (empty), then proceed with implementation.
`.trim();
}

async function main() {
    try {
        const input = readFileSync(0, 'utf-8');

        let data: HookInput;
        try {
            data = JSON.parse(input);
        } catch {
            console.log(JSON.stringify({ result: 'continue' }));
            return;
        }

        const prompt = data.prompt || '';
        const cwd = data.cwd || process.env.CLAUDE_PROJECT_DIR || process.cwd();

        if (!isImplementationTask(prompt)) {
            console.log(JSON.stringify({ result: 'continue' }));
            return;
        }

        // Extract propositions from prompt
        const propositions = extractPropositions(prompt);

        // Compute E(X,Q) using Z3
        const evocation = computeEvocation(propositions, cwd);

        // Generate message with actual results
        const message = getEroteticMessage(propositions, evocation);

        const output: HookOutput = {
            result: 'continue',
            message
        };

        console.log(JSON.stringify(output));
        process.exit(0);
    } catch (err) {
        console.log(JSON.stringify({ result: 'continue' }));
        process.exit(0);
    }
}

main().catch(() => {
    console.log(JSON.stringify({ result: 'continue' }));
    process.exit(0);
});
