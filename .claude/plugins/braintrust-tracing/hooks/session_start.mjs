#!/usr/bin/env node
/**
 * SessionStart Hook - Creates the root trace span when a Claude Code session begins
 * Cross-platform Node.js implementation
 */

import {
  debug, log, tracingEnabled, checkRequirements,
  getSessionState, setSessionState, getProjectId, insertSpan,
  generateUuid, getTimestamp, getHostname, getUsername, getOs,
  readStdin, parseJson, config
} from './common.mjs';
import { basename } from 'path';

async function main() {
  debug('SessionStart hook triggered');

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
  debug(`SessionStart input: ${inputStr.slice(0, 500)}`);

  // Extract session ID from input
  let sessionId = input.session_id;
  if (!sessionId) {
    sessionId = generateUuid();
    debug(`Generated session ID: ${sessionId}`);
  }

  // Get project ID
  const projectId = await getProjectId(config.PROJECT);
  if (!projectId) {
    log('ERROR', 'Failed to get project');
    return;
  }
  debug(`Using project: ${config.PROJECT} (id: ${projectId})`);

  // Check if we already have a root span for this session
  const existingRoot = getSessionState(sessionId, 'root_span_id');
  if (existingRoot) {
    debug(`Session already has root span: ${existingRoot}`);
    return;
  }

  // Create root span for the session
  const rootSpanId = sessionId;
  const timestamp = getTimestamp();

  // Extract workspace info if available
  const workspace = input.cwd || process.cwd();
  const workspaceName = basename(workspace) || 'Claude Code';

  // Get system info
  const hostnameVal = getHostname();
  const username = getUsername();
  const os = getOs();

  const event = {
    id: rootSpanId,
    span_id: rootSpanId,
    root_span_id: rootSpanId,
    created: timestamp,
    input: `Session: ${workspaceName}`,
    metadata: {
      session_id: sessionId,
      workspace: workspace,
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

  const rowId = await insertSpan(projectId, event);
  if (!rowId) {
    log('ERROR', 'Failed to create session root');
    return;
  }

  // Save session state
  setSessionState(sessionId, 'root_span_id', rootSpanId);
  setSessionState(sessionId, 'project_id', projectId);
  setSessionState(sessionId, 'turn_count', '0');
  setSessionState(sessionId, 'tool_count', '0');
  setSessionState(sessionId, 'started', timestamp);

  log('INFO', `Created session root: ${sessionId} workspace=${workspaceName}`);
}

main().catch((err) => {
  log('ERROR', `SessionStart hook error: ${err.message}`);
});
