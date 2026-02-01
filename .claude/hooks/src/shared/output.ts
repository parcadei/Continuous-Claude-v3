/**
 * Shared output helpers for Claude Code hooks.
 *
 * All hooks MUST output valid JSON. Use these helpers to ensure
 * consistent output format and avoid "hook error" messages.
 */

export function outputContinue(): void {
  console.log(JSON.stringify({ result: "continue" }));
}

export function outputWithMessage(message: string): void {
  console.log(JSON.stringify({ result: "continue", message }));
}

export function outputBlock(message: string): void {
  console.log(JSON.stringify({ result: "block", message }));
}
