#!/usr/bin/env node
/**
 * Cross-platform hook launcher
 *
 * Detects the OS and runs either .sh (Unix) or .ps1 (Windows) version of a hook.
 *
 * Usage: node run-hook.mjs <hook-name>
 * Example: node run-hook.mjs persist-project-dir
 *
 * This allows settings.json to use a single command that works on both platforms:
 *   "command": "node $HOME/.claude/hooks/run-hook.mjs persist-project-dir"
 */

import { spawn } from 'child_process';
import { existsSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const isWindows = process.platform === 'win32';

async function main() {
  const hookName = process.argv[2];

  if (!hookName) {
    console.error('Usage: node run-hook.mjs <hook-name>');
    process.exit(1);
  }

  // Read stdin for hook input
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  const input = Buffer.concat(chunks).toString('utf-8');

  // Determine which script to run
  let scriptPath, command, args;

  if (isWindows) {
    // Try PowerShell first
    scriptPath = join(__dirname, `${hookName}.ps1`);
    if (existsSync(scriptPath)) {
      command = 'powershell';
      args = ['-ExecutionPolicy', 'Bypass', '-File', scriptPath];
    } else {
      // Fall back to .mjs if available
      scriptPath = join(__dirname, 'dist', `${hookName}.mjs`);
      if (existsSync(scriptPath)) {
        command = 'node';
        args = [scriptPath];
      }
    }
  } else {
    // Unix: try bash first
    scriptPath = join(__dirname, `${hookName}.sh`);
    if (existsSync(scriptPath)) {
      command = 'bash';
      args = [scriptPath];
    } else {
      // Fall back to .mjs
      scriptPath = join(__dirname, 'dist', `${hookName}.mjs`);
      if (existsSync(scriptPath)) {
        command = 'node';
        args = [scriptPath];
      }
    }
  }

  if (!command) {
    console.error(`No hook script found for: ${hookName}`);
    console.log('{"result":"continue"}');
    process.exit(0);
  }

  // Spawn the script and pipe stdin
  const child = spawn(command, args, {
    stdio: ['pipe', 'inherit', 'inherit'],
    cwd: process.cwd(),
    env: process.env,
  });

  // Pass input to child
  if (input) {
    child.stdin.write(input);
  }
  child.stdin.end();

  // Wait for completion
  child.on('close', (code) => {
    process.exit(code || 0);
  });

  child.on('error', (err) => {
    console.error(`Failed to run hook: ${err.message}`);
    console.log('{"result":"continue"}');
    process.exit(0);
  });
}

main().catch((err) => {
  console.error(`Hook launcher error: ${err.message}`);
  console.log('{"result":"continue"}');
  process.exit(0);
});
