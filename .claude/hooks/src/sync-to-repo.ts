#!/usr/bin/env node
/**
 * sync-to-repo.ts
 *
 * PostToolUse hook that auto-syncs ~/.claude changes to continuous-claude repo.
 * Triggers when hooks, skills, rules, scripts, or agents are modified.
 *
 * Registered for: PostToolUse:Write|Edit
 * Triggers on: ~/.claude/{hooks,skills,rules,scripts,agents}/**
 */

import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

const BASH_LOCATIONS = [
  process.env.GIT_BASH_PATH,
  'C:\\Program Files\\Git\\bin\\bash.exe',
  'C:\\Program Files (x86)\\Git\\bin\\bash.exe',
  process.env.PROGRAMFILES ? process.env.PROGRAMFILES + '\\Git\\bin\\bash.exe' : null,
  process.env.LOCALAPPDATA ? process.env.LOCALAPPDATA + '\\Programs\\Git\\bin\\bash.exe' : null,
];

function findBash(): string | null {
  for (const loc of BASH_LOCATIONS) {
    if (loc && fs.existsSync(loc)) return loc;
  }
  return null;
}

interface HookInput {
  tool_name: string;
  tool_input: {
    file_path?: string;
    path?: string;
  };
  tool_output?: string;
}

interface HookOutput {
  continue: boolean;
  message?: string;
}

const CLAUDE_DIR = process.env.HOME
  ? path.join(process.env.HOME, '.claude')
  : path.join(process.env.USERPROFILE || '', '.claude');

const REPO_DIR = process.env.USERPROFILE
  ? path.join(process.env.USERPROFILE, 'continuous-claude')
  : path.join(process.env.HOME || '', 'continuous-claude');

const SYNC_SCRIPT = path.join(REPO_DIR, 'scripts', 'sync-claude.sh');

// Patterns that trigger sync
const SYNC_PATTERNS = [
  /[\\\/]hooks[\\\/]src[\\\/]/,
  /[\\\/]hooks[\\\/]dist[\\\/]/,
  /[\\\/]hooks[\\\/][^\\\/]+\.(sh|py|ts|mjs)$/,
  /[\\\/]skills[\\\/]/,
  /[\\\/]rules[\\\/]/,
  /[\\\/]agents[\\\/]/,
  /[\\\/]scripts[\\\/]/,
];

// Files to never sync
const NEVER_SYNC = [
  'CLAUDE.md',
  'RULES.md',
  'settings.json',
  '.env',
  'knowledge-tree.json',
];

function shouldSync(filePath: string): boolean {
  if (!filePath) return false;

  // Must be in ~/.claude
  const normalized = filePath.replace(/\\/g, '/');
  if (!normalized.includes('.claude/')) return false;

  // Check if it's a never-sync file
  const basename = path.basename(filePath);
  if (NEVER_SYNC.includes(basename)) return false;

  // Check if it matches sync patterns
  return SYNC_PATTERNS.some(pattern => pattern.test(filePath));
}

function runSync(): { success: boolean; message: string } {
  if (!fs.existsSync(SYNC_SCRIPT)) {
    return {
      success: false,
      message: `Sync script not found at ${SYNC_SCRIPT}`
    };
  }

  try {
    // Run sync in Git Bash on Windows, or bash on Unix
    const isWindows = process.platform === 'win32';
    let bashCmd: string;

    if (isWindows) {
      const bashPath = findBash();
      if (!bashPath) {
        return {
          success: false,
          message: 'Git Bash not found. Set GIT_BASH_PATH env var or install Git for Windows.',
        };
      }
      bashCmd = `"${bashPath}" -c "source '${SYNC_SCRIPT.replace(/\\/g, '/')}' --to-repo"`;
    } else {
      bashCmd = `bash "${SYNC_SCRIPT}" --to-repo`;
    }

    const output = execSync(bashCmd, {
      cwd: REPO_DIR,
      encoding: 'utf8',
      timeout: 30000,
      windowsHide: true,
    });

    // Extract synced count from output
    const syncMatch = output.match(/Synced: (\d+) files/);
    const syncCount = syncMatch ? syncMatch[1] : '?';

    return {
      success: true,
      message: `Auto-synced ${syncCount} files to continuous-claude repo`,
    };
  } catch (error: any) {
    return {
      success: false,
      message: `Sync failed: ${error.message}`,
    };
  }
}

async function hook(input: HookInput): Promise<HookOutput> {
  const filePath = input.tool_input?.file_path || input.tool_input?.path;

  if (!shouldSync(filePath || '')) {
    return { continue: true };
  }

  // Debounce: check if we synced recently (within 10 seconds)
  const stateFile = path.join(CLAUDE_DIR, '.last-repo-sync');
  const now = Date.now();

  if (fs.existsSync(stateFile)) {
    const lastSync = parseInt(fs.readFileSync(stateFile, 'utf8'), 10);
    if (now - lastSync < 10000) {
      return { continue: true }; // Too recent, skip
    }
  }

  // Run sync
  const result = runSync();

  if (result.success) {
    // Update last sync time
    fs.writeFileSync(stateFile, now.toString());
  }

  return {
    continue: true,
    message: result.message,
  };
}

// Main entry point
const input: HookInput = JSON.parse(
  fs.readFileSync(process.stdin.fd, 'utf8')
);

hook(input)
  .then(output => {
    console.log(JSON.stringify(output));
  })
  .catch(error => {
    console.log(JSON.stringify({
      continue: true,
      message: `sync-to-repo hook error: ${error.message}`
    }));
  });
