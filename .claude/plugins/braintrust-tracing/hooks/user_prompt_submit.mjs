#!/usr/bin/env node
/**
 * UserPromptSubmit Hook - Creates a Turn container span when user submits a prompt
 * Cross-platform Node.js implementation
 */

import {
  debug, log, tracingEnabled, checkRequirements,
  getSessionState, setSessionState, getProjectId, insertSpan,
  generateUuid, getTimestamp, getUnixTime, getHostname, getUsername, getOs,
  readStdin, parseJson, config
} from './common.mjs';
import { basename } from 'path';

async function main() {
  debug('UserPromptSubmit hook triggered');

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
  debug(`UserPromptSubmit input: ${inputStr.slice(0, 500)}`);

  // Extract session ID and prompt
  const sessionId = input.session_id;
  const prompt = input.prompt || '';

  if (!sessionId) {
    debug('No session ID');
    return;
  }

  // Get session info
  let rootSpanId = getSessionState(sessionId, 'root_span_id');
  let projectId = getSessionState(sessionId, 'project_id');

  // If no session root exists yet, create it
  if (!rootSpanId || !projectId) {
    projectId = await getProjectId(config.PROJECT);
    if (!projectId) {
      log('ERROR', 'Failed to get project');
      return;
    }
    rootSpanId = sessionId;

    // Get workspace name from cwd
    const cwd = input.cwd || process.cwd();
    const workspaceName = basename(cwd) || 'workspace';

    const timestamp = getTimestamp();
    const hostnameVal = getHostname();
    const username = getUsername();
    const os = getOs();

    const rootEvent = {
      id: rootSpanId,
      span_id: rootSpanId,
      root_span_id: rootSpanId,
      created: timestamp,
      input: `Session: ${workspaceName}`,
      metadata: {
        session_id: sessionId,
        workspace: workspaceName,
        hostname: hostnameVal,
        username: username,
        os: os,
        source: 'claude-code',
      },
      span_attributes: {
        name: `Claude Code: ${workspaceName}`,
        type: 'task',
      },
    };

    await insertSpan(projectId, rootEvent);
    setSessionState(sessionId, 'root_span_id', rootSpanId);
    setSessionState(sessionId, 'project_id', projectId);
    log('INFO', `Created session root: ${sessionId}`);
  }

  // Reconciliation: finalize any previous turn that wasn't closed (e.g., Esc interrupt)
  const prevTurnSpanId = getSessionState(sessionId, 'current_turn_span_id');
  if (prevTurnSpanId) {
    log('WARN', `Previous turn ${prevTurnSpanId} still open - finalizing now (likely Esc interrupt)`);
    const endTime = getUnixTime();
    const turnUpdate = {
      id: prevTurnSpanId,
      _is_merge: true,
      metrics: { end: endTime },
    };
    await insertSpan(projectId, turnUpdate).catch(() => {
      log('WARN', 'Failed to finalize previous turn');
    });
    setSessionState(sessionId, 'current_turn_span_id', '');
  }

  // Increment turn count and create Turn span
  let turnCount = parseInt(getSessionState(sessionId, 'turn_count') || '0', 10);
  turnCount += 1;

  const turnSpanId = generateUuid();
  const timestamp = getTimestamp();
  const startTime = getUnixTime();

  // Truncate prompt for display (first 100 chars)
  const promptPreview = prompt.length > 100 ? prompt.slice(0, 100) + '...' : prompt;

  // Create Turn container span
  const turnEvent = {
    id: turnSpanId,
    span_id: turnSpanId,
    root_span_id: rootSpanId,
    span_parents: [rootSpanId],
    created: timestamp,
    input: prompt,
    metrics: { start: startTime },
    span_attributes: {
      name: `Turn ${turnCount}`,
      type: 'task',
    },
  };

  const rowId = await insertSpan(projectId, turnEvent);
  if (!rowId) {
    log('ERROR', 'Failed to create turn span');
    return;
  }

  // Save turn state
  setSessionState(sessionId, 'turn_count', String(turnCount));
  setSessionState(sessionId, 'current_turn_span_id', turnSpanId);
  setSessionState(sessionId, 'current_turn_start', String(startTime));
  setSessionState(sessionId, 'current_turn_tool_count', '0');

  log('INFO', `Turn ${turnCount} started: ${turnSpanId}`);
}

main().catch((err) => {
  log('ERROR', `UserPromptSubmit hook error: ${err.message}`);
});
