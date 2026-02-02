#!/usr/bin/env node
/**
 * Pre-Compact Memory Extract Hook
 *
 * L0 Defense Layer: Extracts thinking blocks BEFORE context compression.
 * This prevents early session insights from being lost to compaction.
 *
 * Hook: PreCompact
 * Trigger: Before Claude compacts context (manual or auto)
 *
 * Key Insight: PreCompact has JSONL transcript access, so we can extract
 * thinking blocks that are about to be "forgotten" before they're summarized away.
 *
 * State tracked in: .claude/extraction-state.json
 */

import { spawnSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

interface PreCompactInput {
  trigger: 'manual' | 'auto';
  session_id: string;
  transcript_path: string;
  custom_instructions?: string;
}

interface HookOutput {
  continue: boolean;
  systemMessage?: string;
}

interface ExtractionResult {
  learnings_stored: number;
  learnings_skipped: number;
  learnings_deduped: number;
  new_last_line: number;
  hashes: string[];
  errors: string[];
}

function getOpcDir(): string {
  return process.env.CLAUDE_OPC_DIR ||
    path.join(process.env.HOME || process.env.USERPROFILE || '', 'continuous-claude', 'opc');
}

function getStateFilePath(projectDir: string): string {
  return path.join(projectDir, '.claude', 'extraction-state.json');
}

function loadState(stateFile: string): { last_extracted_line: number; recent_hashes: string[] } {
  if (!fs.existsSync(stateFile)) {
    return { last_extracted_line: 0, recent_hashes: [] };
  }

  try {
    const data = JSON.parse(fs.readFileSync(stateFile, 'utf-8'));
    return {
      last_extracted_line: data.last_extracted_line || 0,
      recent_hashes: data.recent_hashes || []
    };
  } catch {
    return { last_extracted_line: 0, recent_hashes: [] };
  }
}

function runIncrementalExtraction(
  transcriptPath: string,
  sessionId: string,
  startLine: number,
  stateFile: string,
  projectDir: string
): ExtractionResult | null {
  const opcDir = getOpcDir();
  const extractScript = path.join(opcDir, 'scripts', 'core', 'incremental_extract.py');

  if (!fs.existsSync(extractScript)) {
    console.error(`incremental_extract.py not found at ${extractScript}`);
    return null;
  }

  const args = [
    'run', 'python', 'scripts/core/incremental_extract.py',
    '--transcript', transcriptPath,
    '--session-id', sessionId,
    '--start-line', startLine.toString(),
    '--state-file', stateFile,
    '--project-dir', projectDir,
    '--max-learnings', '5',  // Keep extraction quick
    '--json'
  ];

  const result = spawnSync('uv', args, {
    encoding: 'utf-8',
    cwd: opcDir,
    env: {
      ...process.env,
      PYTHONPATH: opcDir
    },
    timeout: 15000  // 15 second timeout
  });

  if (result.status !== 0) {
    console.error(`Extraction failed: ${result.stderr}`);
    return null;
  }

  try {
    return JSON.parse(result.stdout.trim());
  } catch {
    console.error(`Failed to parse extraction result: ${result.stdout}`);
    return null;
  }
}

async function main() {
  const input = await readStdin();
  if (!input.trim()) {
    console.log(JSON.stringify({ continue: true }));
    return;
  }

  let data: PreCompactInput;
  try {
    data = JSON.parse(input);
  } catch {
    console.log(JSON.stringify({ continue: true }));
    return;
  }

  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const sessionId = data.session_id;
  const transcriptPath = data.transcript_path;

  // Only extract on auto-compact (not manual - user might want to control that)
  if (data.trigger !== 'auto') {
    const output: HookOutput = {
      continue: true,
      systemMessage: '[PreCompact] Manual compact - skipping auto-extraction'
    };
    console.log(JSON.stringify(output));
    return;
  }

  // Need transcript path for extraction
  if (!transcriptPath || !fs.existsSync(transcriptPath)) {
    const output: HookOutput = {
      continue: true,
      systemMessage: '[PreCompact] No transcript available for extraction'
    };
    console.log(JSON.stringify(output));
    return;
  }

  // Load state to get start line
  const stateFile = getStateFilePath(projectDir);
  const state = loadState(stateFile);

  // Run incremental extraction
  const result = runIncrementalExtraction(
    transcriptPath,
    sessionId,
    state.last_extracted_line,
    stateFile,
    projectDir
  );

  if (!result) {
    const output: HookOutput = {
      continue: true,
      systemMessage: '[PreCompact] Memory extraction unavailable'
    };
    console.log(JSON.stringify(output));
    return;
  }

  // Build status message
  const parts: string[] = [];
  if (result.learnings_stored > 0) {
    parts.push(`${result.learnings_stored} learnings captured`);
  }
  if (result.learnings_deduped > 0) {
    parts.push(`${result.learnings_deduped} skipped (duplicate)`);
  }
  if (result.errors && result.errors.length > 0) {
    parts.push(`${result.errors.length} errors`);
  }

  const message = parts.length > 0
    ? `[PreCompact:L0] Memory extraction: ${parts.join(', ')}`
    : '[PreCompact:L0] No new learnings to extract';

  const output: HookOutput = {
    continue: true,
    systemMessage: message
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
  console.error('pre-compact-extract error:', err);
  console.log(JSON.stringify({ continue: true }));
});
