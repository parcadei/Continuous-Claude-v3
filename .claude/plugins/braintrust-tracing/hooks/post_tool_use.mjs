#!/usr/bin/env node
/**
 * PostToolUse Hook - Creates a tool span as child of current Turn
 * Cross-platform Node.js implementation
 */

import {
  debug, log, tracingEnabled, checkRequirements,
  getSessionState, setSessionState, insertSpan,
  generateUuid, getTimestamp, getUnixTime,
  readStdin, parseJson
} from './common.mjs';
import { basename } from 'path';

async function main() {
  debug('PostToolUse hook triggered');

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
  debug(`PostToolUse input: ${inputStr.slice(0, 500)}`);

  // Extract tool info
  const toolName = input.tool_name || input.tool;
  const toolInput = input.tool_input || {};
  const toolOutput = input.tool_response || input.output || {};
  const sessionId = input.session_id;

  // Skip if no tool name
  if (!toolName) {
    debug('No tool name, skipping');
    return;
  }
  if (!sessionId) {
    debug('No session ID, skipping');
    return;
  }

  // Extract agent type from Task tool
  let agentType = '';
  if (toolName === 'Task') {
    agentType = toolInput.subagent_type || '';
    debug(`Task agent_type: ${agentType}`);
  }

  // Extract skill name from Skill tool
  let skillName = '';
  if (toolName === 'Skill') {
    skillName = toolInput.skill || '';
    debug(`Skill name: ${skillName}`);
  }

  // Get session info
  const rootSpanId = getSessionState(sessionId, 'root_span_id');
  const projectId = getSessionState(sessionId, 'project_id');
  const turnSpanId = getSessionState(sessionId, 'current_turn_span_id');

  // If no turn span exists, tools are orphaned - skip
  if (!turnSpanId || !projectId) {
    debug(`No current turn for session ${sessionId}, skipping tool trace`);
    return;
  }

  // Increment tool count for this turn
  let toolCount = parseInt(getSessionState(sessionId, 'current_turn_tool_count') || '0', 10);
  toolCount += 1;
  setSessionState(sessionId, 'current_turn_tool_count', String(toolCount));

  // Generate span ID
  const spanId = generateUuid();
  const timestamp = getTimestamp();
  const toolTime = getUnixTime();

  // Determine span name based on tool
  let spanName;
  switch (toolName) {
    case 'Read':
    case 'Write':
    case 'Edit':
    case 'MultiEdit': {
      const filePath = toolInput.file_path || toolInput.path || '';
      spanName = filePath ? `${toolName}: ${basename(filePath)}` : toolName;
      break;
    }
    case 'Bash':
    case 'Terminal': {
      const cmd = (toolInput.command || '').slice(0, 50);
      spanName = `Terminal: ${cmd || 'command'}`;
      break;
    }
    default:
      if (toolName.startsWith('mcp__')) {
        spanName = toolName.replace(/^mcp__/, 'MCP: ').replace(/__/g, ' - ');
      } else {
        spanName = toolName;
      }
  }

  // Build the event - tool is child of Turn
  const metadata = { tool_name: toolName };
  if (agentType) metadata.agent_type = agentType;
  if (skillName) metadata.skill_name = skillName;

  const event = {
    id: spanId,
    span_id: spanId,
    root_span_id: rootSpanId,
    span_parents: [turnSpanId],
    created: timestamp,
    input: toolInput,
    output: toolOutput,
    metrics: {
      start: toolTime,
      end: toolTime,
    },
    metadata,
    span_attributes: {
      name: spanName,
      type: 'tool',
    },
  };

  const rowId = await insertSpan(projectId, event);
  if (!rowId) {
    log('ERROR', 'Failed to create tool span');
    return;
  }

  log('INFO', `Tool: ${spanName} (turn=${turnSpanId})`);
}

main().catch((err) => {
  log('ERROR', `PostToolUse hook error: ${err.message}`);
});
