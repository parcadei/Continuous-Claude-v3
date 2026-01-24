#!/usr/bin/env node
/**
 * Session Start Init Check Hook
 *
 * Detects uninitialized projects and suggests /init-project.
 * Lightweight check - only runs on startup, not resume/clear/compact.
 *
 * Hook: SessionStart (startup only)
 */

import * as fs from 'fs';
import * as path from 'path';

interface SessionStartInput {
  type?: 'startup' | 'resume' | 'clear' | 'compact';
  source?: 'startup' | 'resume' | 'clear' | 'compact';
  session_id: string;
}

function isInitialized(projectDir: string): { tree: boolean; roadmap: boolean } {
  const treePath = path.join(projectDir, '.claude', 'knowledge-tree.json');
  const roadmapPath = path.join(projectDir, 'ROADMAP.md');

  return {
    tree: fs.existsSync(treePath),
    roadmap: fs.existsSync(roadmapPath)
  };
}

function hasCodeFiles(projectDir: string): boolean {
  const codeIndicators = [
    'package.json', 'pyproject.toml', 'Cargo.toml', 'go.mod',
    'requirements.txt', 'pom.xml', 'build.gradle', 'Gemfile',
    'README.md', 'readme.md', '.git'
  ];

  for (const indicator of codeIndicators) {
    if (fs.existsSync(path.join(projectDir, indicator))) {
      return true;
    }
  }

  return false;
}

async function main() {
  const input = await readStdin();
  if (!input.trim()) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  let data: SessionStartInput;
  try {
    data = JSON.parse(input);
  } catch {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  const sessionType = data.source || data.type || 'startup';

  if (sessionType !== 'startup') {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();

  if (projectDir.includes('.claude') || projectDir.includes('continuous-claude')) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  const status = isInitialized(projectDir);

  if (status.tree && status.roadmap) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  if (!hasCodeFiles(projectDir)) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  const missing: string[] = [];
  if (!status.tree) missing.push('knowledge-tree.json');
  if (!status.roadmap) missing.push('ROADMAP.md');

  const message = `📋 Project not initialized. Missing: ${missing.join(', ')}. Run /init-project for Continuous Claude setup.`;

  console.error(`ℹ ${message}`);

  const output = {
    result: 'continue',
    message: message
  };

  console.log(JSON.stringify(output));
}

async function readStdin(): Promise<string> {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.setEncoding('utf-8');
    process.stdin.on('data', chunk => data += chunk);
    process.stdin.on('end', () => resolve(data));
  });
}

main().catch(err => {
  console.error('session-start-init-check error:', err);
  console.log(JSON.stringify({ result: 'continue' }));
});
