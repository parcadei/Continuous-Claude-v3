#!/usr/bin/env node
/**
 * Stop Hook - Finalizes the current Turn span
 * Cross-platform Node.js implementation
 *
 * Note: The bash version does complex transcript parsing to create LLM spans.
 * This simplified version just finalizes the Turn span. Full LLM span creation
 * would require significant additional logic to parse the transcript file.
 */

import {
  debug, log, tracingEnabled, checkRequirements,
  getSessionState, setSessionState, insertSpan, getUnixTime,
  readStdin, parseJson
} from './common.mjs';
import { basename } from 'path';

async function main() {
  log('INFO', '=== STOP HOOK CALLED ===');

  if (!tracingEnabled()) {
    log('WARN', 'Tracing disabled');
    return;
  }

  if (!checkRequirements()) {
    return;
  }

  // Read input from stdin
  const inputStr = await readStdin();
  const input = parseJson(inputStr);
  debug(`Stop input: ${inputStr.slice(0, 500)}`);

  // Get session ID
  let sessionId = input.session_id;
  if (!sessionId && input.transcript_path) {
    sessionId = basename(input.transcript_path, '.jsonl');
  }

  if (!sessionId) {
    debug('No session ID');
    return;
  }

  // Get session state
  const rootSpanId = getSessionState(sessionId, 'root_span_id');
  const projectId = getSessionState(sessionId, 'project_id');
  const turnSpanId = getSessionState(sessionId, 'current_turn_span_id');
  const turnStart = getSessionState(sessionId, 'current_turn_start');

  if (!turnSpanId || !projectId) {
    log('WARN', `No current turn to finalize (TURN_SPAN_ID='${turnSpanId}', PROJECT_ID='${projectId}')`);
    return;
  }

  log('INFO', `Stop hook processing turn: ${turnSpanId} (session=${sessionId})`);

  // Update Turn span with end time using merge write
  const endTime = getUnixTime();

  const turnUpdate = {
    id: turnSpanId,
    _is_merge: true,
    metrics: { end: endTime },
  };

  log('DEBUG', `Attempting turn finalization: turn=${turnSpanId} project=${projectId}`);

  try {
    const result = await insertSpan(projectId, turnUpdate);
    if (result) {
      log('DEBUG', `Turn finalization insert succeeded: ${result}`);
    } else {
      log('ERROR', 'Turn finalization insert failed');
    }
  } catch (err) {
    log('ERROR', `Turn finalization error: ${err.message}`);
  }

  // Update state
  setSessionState(sessionId, 'current_turn_span_id', '');

  log('INFO', `Turn finalized (end=${endTime})`);
}

main().catch((err) => {
  log('ERROR', `Stop hook error: ${err.message}`);
});
