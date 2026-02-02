#!/usr/bin/env node
/**
 * Agent Verification Hook
 *
 * Verifies agent claims after Task tool completes.
 * When an agent claims to have completed work, verify the claims
 * and inject warnings if evidence is missing.
 *
 * Hook: PostToolUse:Task
 *
 * Verification types:
 * - kraken/spark claiming file creation → verify files exist
 * - arbiter claiming tests pass → check for test output markers
 * - Implementation agents claiming "done" → warn if no file changes mentioned
 *
 * Note: This is informational only (warnings), not blocking.
 * PostToolUse cannot block, only inject context.
 */

import { readFileSync, existsSync } from 'fs';

interface PostToolUseInput {
  session_id: string;
  tool_name: string;
  tool_input: {
    subagent_type?: string;
    prompt?: string;
    description?: string;
  };
  tool_response: unknown;
}

interface VerificationResult {
  verified: boolean;
  warnings: string[];
}

// Agents that typically create/modify files
const IMPLEMENTATION_AGENTS = ['kraken', 'spark', 'scribe', 'herald'];

// Agents that run tests
const TEST_AGENTS = ['arbiter', 'atlas', 'principal-sdet'];

// Patterns indicating file creation claims
const FILE_CREATION_PATTERNS = [
  /\bcreated?\s+(file|the\s+file)?\s*[`'"]?([^\s`'"]+\.(ts|js|tsx|jsx|py|go|rs|java|rb|css|html|json|yaml|yml|md))[`'"]?/gi,
  /\bwrote\s+(to\s+)?(file\s+)?[`'"]?([^\s`'"]+\.[a-z]+)[`'"]?/gi,
  /\badded\s+(file\s+)?[`'"]?([^\s`'"]+\.[a-z]+)[`'"]?/gi,
  /\bimplemented\s+in\s+[`'"]?([^\s`'"]+\.[a-z]+)[`'"]?/gi,
];

// Patterns indicating test execution claims
const TEST_PASS_PATTERNS = [
  /\ball\s+(\d+\s+)?tests?\s+pass/i,
  /\btests?\s+(are\s+)?passing/i,
  /\b(\d+)\s+tests?\s+passed/i,
  /\btest\s+suite\s+passed/i,
  /\bgreen\s+tests?/i,
  /\b100%\s+pass/i,
];

// Patterns indicating tests were actually run
const TEST_EXECUTION_EVIDENCE = [
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
  /\b\d+\s+(passed|failed|skipped)/i,
];

// Patterns indicating completion claims
const COMPLETION_PATTERNS = [
  /\b(task|implementation|work)\s+(is\s+)?complete/i,
  /\bsuccessfully\s+(implemented|completed|finished)/i,
  /\ball\s+(changes\s+)?done\b/i,
  /\bfinished\s+(implementing|the\s+task)/i,
];

function readStdin(): string {
  return readFileSync(0, 'utf-8');
}

function outputWithMessage(message?: string): void {
  if (message) {
    console.log(JSON.stringify({ message }));
  } else {
    console.log(JSON.stringify({}));
  }
}

function responseToString(response: unknown): string {
  if (typeof response === 'string') return response;
  if (response === null || response === undefined) return '';
  try {
    return JSON.stringify(response, null, 2);
  } catch {
    return String(response);
  }
}

function extractClaimedFiles(text: string): string[] {
  const files: string[] = [];

  for (const pattern of FILE_CREATION_PATTERNS) {
    // Reset lastIndex for global patterns
    pattern.lastIndex = 0;
    let match;
    while ((match = pattern.exec(text)) !== null) {
      // Different patterns capture file in different groups
      const file = match[3] || match[2] || match[1];
      if (file && !files.includes(file)) {
        files.push(file);
      }
    }
  }

  return files;
}

function verifyImplementationAgent(response: string): VerificationResult {
  const warnings: string[] = [];

  // Check if agent claims completion
  const claimsComplete = COMPLETION_PATTERNS.some(p => p.test(response));

  if (claimsComplete) {
    // Check if any files were mentioned as created
    const claimedFiles = extractClaimedFiles(response);

    if (claimedFiles.length === 0) {
      // Agent claims done but didn't mention specific files
      warnings.push('Agent claims completion but no specific files were mentioned as created/modified');
    } else {
      // Check if claimed files exist (best effort - they might be relative paths)
      const missingFiles: string[] = [];
      for (const file of claimedFiles) {
        // Only check absolute-looking paths or paths in current dir
        if (file.startsWith('/') || file.startsWith('C:') || !file.includes('/')) {
          if (!existsSync(file)) {
            missingFiles.push(file);
          }
        }
      }

      if (missingFiles.length > 0) {
        warnings.push(`Agent claimed to create files that don't exist: ${missingFiles.join(', ')}`);
      }
    }
  }

  return { verified: warnings.length === 0, warnings };
}

function verifyTestAgent(response: string): VerificationResult {
  const warnings: string[] = [];

  // Check if agent claims tests pass
  const claimsTestsPass = TEST_PASS_PATTERNS.some(p => p.test(response));

  if (claimsTestsPass) {
    // Check for evidence that tests were actually run
    const hasExecutionEvidence = TEST_EXECUTION_EVIDENCE.some(p => p.test(response));

    if (!hasExecutionEvidence) {
      warnings.push('Agent claims tests pass but no test execution output/evidence found in response');
    }
  }

  return { verified: warnings.length === 0, warnings };
}

function verifyAgent(agentType: string, response: string): VerificationResult {
  const lowerAgent = agentType.toLowerCase();

  if (IMPLEMENTATION_AGENTS.includes(lowerAgent)) {
    return verifyImplementationAgent(response);
  }

  if (TEST_AGENTS.includes(lowerAgent)) {
    return verifyTestAgent(response);
  }

  // For other agents, no specific verification
  return { verified: true, warnings: [] };
}

async function main() {
  try {
    const rawInput = readStdin();
    if (!rawInput.trim()) {
      outputWithMessage();
      return;
    }

    let input: PostToolUseInput;
    try {
      input = JSON.parse(rawInput);
    } catch {
      outputWithMessage();
      return;
    }

    // Only process Task tool results
    if (input.tool_name !== 'Task') {
      outputWithMessage();
      return;
    }

    const agentType = input.tool_input.subagent_type || 'unknown';
    const responseStr = responseToString(input.tool_response);

    // Verify agent claims
    const result = verifyAgent(agentType, responseStr);

    if (!result.verified && result.warnings.length > 0) {
      const warningMessage = `
⚠️ AGENT VERIFICATION WARNING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Agent: ${agentType}
${result.warnings.map(w => `• ${w}`).join('\n')}

Consider verifying the agent's claims before proceeding.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`;

      console.error(`[AgentVerification] ${result.warnings.join('; ')}`);
      outputWithMessage(warningMessage);
      return;
    }

    outputWithMessage();

  } catch (err) {
    // Fail silently - don't disrupt the session
    console.error(`[AgentVerification] Hook error: ${err}`);
    outputWithMessage();
  }
}

main();
