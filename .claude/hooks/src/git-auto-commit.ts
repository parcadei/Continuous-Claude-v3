#!/usr/bin/env node
/**
 * Git Auto-Commit Hook
 *
 * Triggers on PostToolUse:Write|Edit to auto-commit changes to ~/.claude
 * Uses file-based debounce (10 min cooldown) to batch changes.
 *
 * Flow:
 * 1. Check if edited file is in ~/.claude and tracked by git
 * 2. Check debounce (10 min since last commit)
 * 3. If ready, stage tracked changes and commit
 * 4. Post-commit hook handles sync to continuous-claude
 */

import { readFileSync, writeFileSync, existsSync, statSync } from 'fs';
import { execSync } from 'child_process';
import { join, resolve } from 'path';
import { homedir } from 'os';

interface HookInput {
  tool_name: string;
  tool_input: {
    file_path?: string;
  };
}

interface GitError {
  type: 'GIT_NOT_FOUND' | 'NOT_GIT_REPO' | 'PERMISSION_DENIED' | 'COMMIT_FAILED';
  message: string;
  suggestedAction?: string;
}

const CLAUDE_DIR = join(homedir(), '.claude');

function checkGitAvailable(): GitError | null {
  try {
    execSync('git --version', { stdio: 'pipe' });
    return null;
  } catch {
    return {
      type: 'GIT_NOT_FOUND',
      message: 'Git not found in PATH',
      suggestedAction: 'Install git: https://git-scm.com/downloads'
    };
  }
}

function checkIsGitRepo(): GitError | null {
  try {
    execSync('git rev-parse --git-dir', { cwd: CLAUDE_DIR, stdio: 'pipe' });
    return null;
  } catch {
    return {
      type: 'NOT_GIT_REPO',
      message: `${CLAUDE_DIR} is not a git repository`,
      suggestedAction: 'Run: cd ~/.claude && git init'
    };
  }
}
const DEBOUNCE_FILE = join(CLAUDE_DIR, '.last-git-sync');
const DEBOUNCE_MS = 10 * 60 * 1000; // 10 minutes

function isInClaudeDir(filePath: string): boolean {
  // Normalize paths for Windows compatibility (forward slashes)
  const normalizedFile = resolve(filePath).replace(/\\/g, '/');
  const normalizedClaudeDir = CLAUDE_DIR.replace(/\\/g, '/');
  return normalizedFile.startsWith(normalizedClaudeDir);
}

function isTrackedByGit(filePath: string): boolean {
  try {
    // Check if file would be tracked (not in .gitignore)
    execSync(`git check-ignore -q "${filePath}"`, {
      cwd: CLAUDE_DIR,
      stdio: 'pipe',
    });
    // If check-ignore succeeds (exit 0), file IS ignored
    return false;
  } catch {
    // If check-ignore fails (exit 1), file is NOT ignored = tracked
    return true;
  }
}

function shouldCommit(): boolean {
  if (!existsSync(DEBOUNCE_FILE)) {
    return true;
  }

  try {
    const stats = statSync(DEBOUNCE_FILE);
    const elapsed = Date.now() - stats.mtimeMs;
    return elapsed >= DEBOUNCE_MS;
  } catch {
    return true;
  }
}

function hasChanges(): boolean {
  try {
    const status = execSync('git status --porcelain', {
      cwd: CLAUDE_DIR,
      encoding: 'utf-8',
    });
    return status.trim().length > 0;
  } catch {
    return false;
  }
}

function getChangeSummary(): string {
  try {
    const status = execSync('git status --porcelain', {
      cwd: CLAUDE_DIR,
      encoding: 'utf-8',
    });

    const lines = status.trim().split('\n').filter(Boolean);
    const changes: string[] = [];

    for (const line of lines.slice(0, 5)) {
      const file = line.slice(3).trim();
      changes.push(file);
    }

    if (lines.length > 5) {
      changes.push(`+${lines.length - 5} more`);
    }

    return changes.join(', ');
  } catch {
    return 'changes';
  }
}

function doCommit(): boolean {
  try {
    // Stage all changes (respects .gitignore)
    execSync('git add -A', { cwd: CLAUDE_DIR, stdio: 'pipe' });

    // Check if there's anything staged
    const staged = execSync('git diff --cached --name-only', {
      cwd: CLAUDE_DIR,
      encoding: 'utf-8',
    });

    if (!staged.trim()) {
      return false;
    }

    const summary = getChangeSummary();
    const timestamp = new Date().toISOString().replace('T', ' ').slice(0, 19);
    const message = `Auto: ${timestamp} - ${summary}`;

    execSync(`git commit -m "${message}"`, {
      cwd: CLAUDE_DIR,
      stdio: 'pipe',
    });

    // Update debounce timestamp
    writeFileSync(DEBOUNCE_FILE, new Date().toISOString());

    return true;
  } catch (err) {
    console.error('Git commit failed:', err);
    return false;
  }
}

async function main(): Promise<void> {
  // Pre-flight checks
  const gitError = checkGitAvailable();
  if (gitError) {
    console.log(JSON.stringify({
      result: 'continue',
      message: `[git-auto-commit] ${gitError.message}. ${gitError.suggestedAction || ''}`
    }));
    return;
  }

  const repoError = checkIsGitRepo();
  if (repoError) {
    console.log(JSON.stringify({
      result: 'continue',
      message: `[git-auto-commit] ${repoError.message}. ${repoError.suggestedAction || ''}`
    }));
    return;
  }

  // Read hook input
  let input: HookInput;
  try {
    input = JSON.parse(readFileSync(0, 'utf-8'));
  } catch {
    console.log('{}');
    return;
  }

  // Only handle Write and Edit
  if (!['Write', 'Edit'].includes(input.tool_name)) {
    console.log('{}');
    return;
  }

  const filePath = input.tool_input?.file_path;
  if (!filePath) {
    console.log('{}');
    return;
  }

  // Check if file is in ~/.claude and tracked
  if (!isInClaudeDir(filePath) || !isTrackedByGit(filePath)) {
    console.log('{}');
    return;
  }

  // Check debounce
  if (!shouldCommit()) {
    console.log('{}');
    return;
  }

  // Check if there are actually changes
  if (!hasChanges()) {
    console.log('{}');
    return;
  }

  // Attempt commit
  const committed = doCommit();

  if (committed) {
    // Output info for logging (but don't block)
    console.log(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PostToolUse',
        additionalContext: '[Git] Auto-committed ~/.claude changes',
      },
    }));
  } else {
    console.log('{}');
  }
}

main().catch((err) => {
  console.log(JSON.stringify({
    result: 'continue',
    message: `[git-auto-commit error] ${err.message || 'Unknown error'}`
  }));
});
