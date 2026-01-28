#!/usr/bin/env node
/**
 * SessionEnd Hook - Finalizes the trace when a Claude Code session ends
 * Cross-platform Node.js implementation
 */

import {
  debug, log, tracingEnabled, checkRequirements,
  getSessionState, setSessionState, insertSpan, getUnixTime,
  readStdin, parseJson, loadGlobalState
} from './common.mjs';

async function main() {
  debug('SessionEnd hook triggered');

  if (!tracingEnabled()) {
    debug('Tracing disabled');
    return;
  }

  if (!checkRequirements()) {
    return;
  }

  // Read input from stdin
  const inputStr = await readStdin();
  const input = parseJson(inputStr);
  debug(`SessionEnd input: ${inputStr.slice(0, 500)}`);

  // Extract session ID
  let sessionId = input.session_id;
  if (!sessionId) {
    // Try to get from global state
    const globalState = loadGlobalState();
    const sessions = globalState.sessions || {};
    const sessionIds = Object.keys(sessions);
    sessionId = sessionIds[sessionIds.length - 1];
  }

  if (!sessionId) {
    debug('No session ID, skipping');
    return;
  }

  // Get session info
  const rootSpanId = getSessionState(sessionId, 'root_span_id');
  const projectId = getSessionState(sessionId, 'project_id');
  const turnCount = getSessionState(sessionId, 'turn_count') || '0';
  const toolCount = getSessionState(sessionId, 'tool_count') || '0';
  const started = getSessionState(sessionId, 'started');

  if (!rootSpanId) {
    debug('No root span for session');
    return;
  }
  if (!projectId) {
    debug('No project ID for session');
    return;
  }

  // Reconciliation: finalize any open turn before ending session
  const currentTurnSpanId = getSessionState(sessionId, 'current_turn_span_id');
  if (currentTurnSpanId) {
    log('INFO', `Finalizing open turn ${currentTurnSpanId} at session end`);
    const endTime = getUnixTime();
    const turnUpdate = {
      id: currentTurnSpanId,
      _is_merge: true,
      metrics: { end: endTime },
    };
    try {
      await insertSpan(projectId, turnUpdate);
    } catch {
      log('WARN', 'Failed to finalize turn at session end');
    }
    setSessionState(sessionId, 'current_turn_span_id', '');
  }

  log('INFO', `Session ended: ${sessionId} (turns=${turnCount}, tools=${toolCount})`);

  // Note: Learning extraction is handled separately by the bash version.
  // To fully replicate, would need to call braintrust_analyze.py here.
}

main().catch((err) => {
  log('ERROR', `SessionEnd hook error: ${err.message}`);
});
