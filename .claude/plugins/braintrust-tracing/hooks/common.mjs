/**
 * Common utilities for Braintrust Claude Code tracing hooks (Cross-platform)
 *
 * Node.js replacement for common.sh - works on Windows, Mac, and Linux.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync, readdirSync, statSync, unlinkSync } from 'fs';
import { join, dirname } from 'path';
import { homedir, hostname, userInfo, platform } from 'os';
import { randomUUID } from 'crypto';

// Load environment from ~/.claude/.env if it exists
const envFile = join(homedir(), '.claude', '.env');
if (existsSync(envFile)) {
  const envContent = readFileSync(envFile, 'utf-8');
  for (const line of envContent.split('\n')) {
    const match = line.match(/^export\s+(\w+)=["']?(.+?)["']?$/);
    if (match) {
      process.env[match[1]] = match[2];
    } else {
      const simpleMatch = line.match(/^(\w+)=["']?(.+?)["']?$/);
      if (simpleMatch) {
        process.env[simpleMatch[1]] = simpleMatch[2];
      }
    }
  }
}

// Config
const LOG_FILE = join(homedir(), '.claude', 'state', 'braintrust_hook.log');
const STATE_DIR = join(homedir(), '.claude', 'state', 'braintrust_sessions');
const GLOBAL_STATE_FILE = join(homedir(), '.claude', 'state', 'braintrust_global.json');
const DEBUG = (process.env.BRAINTRUST_CC_DEBUG || 'false').toLowerCase() === 'true';
const API_KEY = process.env.BRAINTRUST_API_KEY || '';
const PROJECT = process.env.BRAINTRUST_CC_PROJECT || 'claude-code';
const API_URL = process.env.BRAINTRUST_API_URL || 'https://api.braintrust.dev';

// Ensure directories exist
mkdirSync(dirname(LOG_FILE), { recursive: true });
mkdirSync(STATE_DIR, { recursive: true });

// Logging
export function log(level, message) {
  const timestamp = new Date().toISOString().replace('T', ' ').slice(0, 19);
  const logLine = `${timestamp} [${level}] ${message}\n`;
  try {
    writeFileSync(LOG_FILE, logLine, { flag: 'a' });
  } catch {
    // Ignore log errors
  }
}

export function debug(message) {
  if (DEBUG) {
    log('DEBUG', message);
  }
}

// Check if tracing is enabled
export function tracingEnabled() {
  return (process.env.TRACE_TO_BRAINTRUST || '').toLowerCase() === 'true';
}

// Validate requirements
export function checkRequirements() {
  if (!API_KEY) {
    log('ERROR', 'BRAINTRUST_API_KEY not set');
    return false;
  }
  return true;
}

// State file helpers
function getSessionFile(sessionId) {
  return join(STATE_DIR, `${sessionId}.json`);
}

function loadStateFile(filePath) {
  if (existsSync(filePath)) {
    try {
      const content = readFileSync(filePath, 'utf-8');
      return JSON.parse(content);
    } catch {
      debug(`Corrupt state file: ${filePath}`);
      return {};
    }
  }
  return {};
}

function saveStateFile(filePath, content) {
  try {
    JSON.parse(JSON.stringify(content)); // Validate JSON
    const tempFile = `${filePath}.tmp.${process.pid}`;
    writeFileSync(tempFile, JSON.stringify(content, null, 2));
    // Atomic rename (mostly works on Windows too)
    try {
      unlinkSync(filePath);
    } catch {
      // File might not exist
    }
    writeFileSync(filePath, JSON.stringify(content, null, 2));
    try {
      unlinkSync(tempFile);
    } catch {
      // Cleanup temp
    }
    return true;
  } catch (err) {
    log('ERROR', `Failed to save state file: ${err.message}`);
    return false;
  }
}

// Global state (for project_id cache)
export function loadGlobalState() {
  return loadStateFile(GLOBAL_STATE_FILE);
}

export function saveGlobalState(state) {
  return saveStateFile(GLOBAL_STATE_FILE, state);
}

export function getStateValue(key) {
  const state = loadGlobalState();
  return state[key] || '';
}

export function setStateValue(key, value) {
  const state = loadGlobalState();
  state[key] = value;
  saveGlobalState(state);
}

// Per-session state
export function getSessionState(sessionId, key) {
  const state = loadStateFile(getSessionFile(sessionId));
  return state[key] || '';
}

export function setSessionState(sessionId, key, value) {
  const state = loadStateFile(getSessionFile(sessionId));
  state[key] = value;
  saveStateFile(getSessionFile(sessionId), state);
}

// Get or create project ID (cached globally)
export async function getProjectId(name = PROJECT) {
  // Check cache first
  const cachedId = getStateValue('project_id');
  if (cachedId) {
    return cachedId;
  }

  const encodedName = encodeURIComponent(name);

  try {
    // Try to get existing project
    const response = await fetch(`${API_URL}/v1/project?project_name=${encodedName}`, {
      headers: { 'Authorization': `Bearer ${API_KEY}` },
    });

    if (response.ok) {
      const data = await response.json();
      if (data.id) {
        setStateValue('project_id', data.id);
        return data.id;
      }
    }

    // Create project
    debug(`Creating project: ${name}`);
    const createResponse = await fetch(`${API_URL}/v1/project`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name }),
    });

    if (createResponse.ok) {
      const createData = await createResponse.json();
      if (createData.id) {
        setStateValue('project_id', createData.id);
        return createData.id;
      }
    }
  } catch (err) {
    log('ERROR', `Failed to get/create project: ${err.message}`);
  }

  return null;
}

// Insert a span to Braintrust
export async function insertSpan(projectId, eventJson) {
  debug(`Inserting span: ${JSON.stringify(eventJson)}`);

  if (!API_KEY) {
    log('ERROR', 'API_KEY is empty - check BRAINTRUST_API_KEY env var');
    return null;
  }

  try {
    const response = await fetch(`${API_URL}/v1/project_logs/${projectId}/insert`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ events: [eventJson] }),
    });

    if (!response.ok) {
      const text = await response.text();
      log('ERROR', `Insert failed (HTTP ${response.status}): ${text}`);
      return null;
    }

    const data = await response.json();
    const rowId = data.row_ids?.[0];

    if (rowId) {
      return rowId;
    } else {
      log('WARN', `Insert returned empty row_ids: ${JSON.stringify(data)}`);
      return null;
    }
  } catch (err) {
    log('ERROR', `Insert span error: ${err.message}`);
    return null;
  }
}

// Generate a UUID
export function generateUuid() {
  return randomUUID();
}

// Get current ISO timestamp
export function getTimestamp() {
  return new Date().toISOString();
}

// Get Unix timestamp (seconds)
export function getUnixTime() {
  return Math.floor(Date.now() / 1000);
}

// Get system info for metadata
export function getHostname() {
  try {
    return hostname();
  } catch {
    return 'unknown';
  }
}

export function getUsername() {
  try {
    return userInfo().username;
  } catch {
    return 'unknown';
  }
}

export function getOs() {
  return platform();
}

// Cleanup old session state files (older than 7 days)
export function cleanupOldSessions() {
  try {
    const files = readdirSync(STATE_DIR);
    const now = Date.now();
    const sevenDays = 7 * 24 * 60 * 60 * 1000;

    for (const file of files) {
      if (file.endsWith('.json')) {
        const filePath = join(STATE_DIR, file);
        const stat = statSync(filePath);
        if (now - stat.mtimeMs > sevenDays) {
          unlinkSync(filePath);
        }
      }
    }
  } catch {
    // Ignore cleanup errors
  }
}

// Read stdin as string
export async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString('utf-8');
}

// Parse JSON safely
export function parseJson(str, defaultValue = {}) {
  try {
    return JSON.parse(str);
  } catch {
    return defaultValue;
  }
}

// Export config for other modules
export const config = {
  LOG_FILE,
  STATE_DIR,
  GLOBAL_STATE_FILE,
  DEBUG,
  API_KEY,
  PROJECT,
  API_URL,
};
