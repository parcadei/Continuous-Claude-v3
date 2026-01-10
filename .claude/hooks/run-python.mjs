#!/usr/bin/env node
/**
 * Cross-platform Python runner for Claude Code hooks.
 * Finds the correct Python executable, preferring the OPC venv.
 *
 * Usage: node run-python.mjs <script.py> [args...]
 */
import { spawn, execSync, spawnSync } from 'child_process';
import { existsSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

// Try to find the OPC venv Python first (has all required packages)
const venvPaths = [
  // Project-specific venv (if CLAUDE_PROJECT_DIR is set)
  process.env.CLAUDE_PROJECT_DIR && join(process.env.CLAUDE_PROJECT_DIR, 'opc', '.venv', 'bin', 'python'),
  // Global OPC installation
  join(homedir(), 'Projects', 'Continuous-Claude-v3', 'opc', '.venv', 'bin', 'python'),
  // Windows variants
  process.env.CLAUDE_PROJECT_DIR && join(process.env.CLAUDE_PROJECT_DIR, 'opc', '.venv', 'Scripts', 'python.exe'),
  join(homedir(), 'Projects', 'Continuous-Claude-v3', 'opc', '.venv', 'Scripts', 'python.exe'),
].filter(Boolean);

// Then fall back to system Python
const pythonCandidates = [...venvPaths, 'python3', 'python', 'py'];
let python = null;

for (const cmd of pythonCandidates) {
  try {
    // For full paths, check if file exists first
    if (cmd.includes('/') || cmd.includes('\\')) {
      if (existsSync(cmd)) {
        python = cmd;
        break;
      }
    } else {
      execSync(`${cmd} --version`, { stdio: 'ignore' });
      python = cmd;
      break;
    }
  } catch {}
}

if (!python) {
  console.error('Error: Python not found. Install Python 3 and ensure it is on PATH.');
  process.exit(1);
}

const [,, ...args] = process.argv;
const child = spawn(python, args, { stdio: 'inherit' });
child.on('exit', code => process.exit(code ?? 1));
