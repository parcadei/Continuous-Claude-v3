#!/usr/bin/env node
/**
 * Session End Extract Hook (L3 Defense Layer)
 *
 * Final sweep memory extraction when a session ends.
 * Complements PreCompact (L0), UserConfirm (L1), and SmarterEveryDay (L2).
 *
 * Hook: SessionEnd
 * Condition: Session has enough turns (>= 10)
 *
 * Enhancements:
 * - Reads extraction-state.json to skip already-extracted content
 * - Uses incremental_extract.py for deduplication
 */

import { execSync, spawn, spawnSync } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

interface SessionEndInput {
  session_id: string;
  type?: string;
  transcript_path?: string;
}

interface ExtractionState {
  session_id: string;
  last_extracted_line: number;
  recent_hashes: string[];
  last_extraction_time: string;
}

const MIN_TURNS = 10;
const EXTRACTION_TIMEOUT = 60000; // 60 seconds

function getOpcDir(): string {
  return process.env.CLAUDE_OPC_DIR || path.join(process.env.HOME || process.env.USERPROFILE || '', 'continuous-claude', 'opc');
}

function getStateFilePath(projectDir: string): string {
  return path.join(projectDir, '.claude', 'extraction-state.json');
}

function loadExtractionState(stateFile: string): ExtractionState | null {
  if (!fs.existsSync(stateFile)) return null;
  try {
    return JSON.parse(fs.readFileSync(stateFile, 'utf-8'));
  } catch {
    return null;
  }
}

function shouldExtract(sessionId: string, projectDir: string): boolean {
  const opcDir = getOpcDir();
  const lazyMemoryPath = path.join(opcDir, 'scripts', 'core', 'lazy_memory.py');

  if (!fs.existsSync(lazyMemoryPath)) {
    console.error('lazy_memory.py not found');
    return false;
  }

  try {
    const result = execSync(
      `cd "${opcDir}" && uv run python scripts/core/lazy_memory.py check --session-id "${sessionId}" --project "${projectDir}" --min-turns ${MIN_TURNS} --json`,
      { encoding: 'utf-8', timeout: 10000, stdio: ['pipe', 'pipe', 'pipe'] }
    );

    const data = JSON.parse(result.trim());
    return data.should_extract === true;
  } catch (err) {
    // If check fails, assume we should try extraction anyway
    return true;
  }
}

function extractWithDedup(sessionId: string, projectDir: string, transcriptPath?: string): void {
  const opcDir = getOpcDir();
  const stateFile = getStateFilePath(projectDir);
  const state = loadExtractionState(stateFile);

  // If we have transcript and incremental_extract.py, use dedup-aware extraction
  const incrementalScript = path.join(opcDir, 'scripts', 'core', 'incremental_extract.py');
  if (transcriptPath && fs.existsSync(transcriptPath) && fs.existsSync(incrementalScript)) {
    const startLine = state?.last_extracted_line || 0;

    console.error(`[SessionEnd:L3] Final sweep from line ${startLine} with dedup`);

    // Run incremental extraction for final sweep
    const result = spawnSync('uv', [
      'run', 'python', 'scripts/core/incremental_extract.py',
      '--transcript', transcriptPath,
      '--session-id', sessionId,
      '--start-line', startLine.toString(),
      '--state-file', stateFile,
      '--project-dir', projectDir,
      '--max-learnings', '15',  // More generous at session end
      '--json'
    ], {
      cwd: opcDir,
      encoding: 'utf-8',
      env: { ...process.env, PYTHONPATH: opcDir },
      timeout: 30000
    });

    if (result.status === 0) {
      try {
        const data = JSON.parse(result.stdout.trim());
        console.error(`[SessionEnd:L3] Extracted ${data.learnings_stored}, deduped ${data.learnings_deduped}`);
      } catch {
        console.error('[SessionEnd:L3] Extraction complete');
      }
      return;
    }
  }

  // Fallback to legacy extraction
  extractLearningsLegacy(sessionId, projectDir);
}

function extractLearningsLegacy(sessionId: string, projectDir: string): void {
  const opcDir = getOpcDir();
  const lazyMemoryPath = path.join(opcDir, 'scripts', 'core', 'lazy_memory.py');

  if (!fs.existsSync(lazyMemoryPath)) {
    console.error('lazy_memory.py not found, skipping extraction');
    return;
  }

  // Run extraction in background (don't block session end)
  const child = spawn(
    'uv',
    ['run', 'python', 'scripts/core/lazy_memory.py', 'extract',
     '--session-id', sessionId,
     '--project', projectDir,
     '--max-learnings', '10'],
    {
      cwd: opcDir,
      detached: true,
      stdio: 'ignore',
    }
  );

  // Unref to allow parent to exit
  child.unref();

  console.error(`✓ Memory extraction started for session ${sessionId.slice(0, 8)}...`);
}

async function main() {
  const input = await readStdin();
  if (!input.trim()) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  let data: SessionEndInput;
  try {
    data = JSON.parse(input);
  } catch {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  const sessionId = data.session_id;
  if (!sessionId) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();

  // Check if session has enough content
  if (!shouldExtract(sessionId, projectDir)) {
    console.error(`ℹ Session too short for extraction (< ${MIN_TURNS} turns)`);
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  // Trigger extraction with deduplication
  extractWithDedup(sessionId, projectDir, data.transcript_path);

  console.log(JSON.stringify({ result: 'continue' }));
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
  console.error('session-end-extract error:', err);
  console.log(JSON.stringify({ result: 'continue' }));
});
