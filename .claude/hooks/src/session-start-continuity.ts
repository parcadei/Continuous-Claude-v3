import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';

interface SessionStartInput {
  type?: 'startup' | 'resume' | 'clear' | 'compact';  // Legacy field
  source?: 'startup' | 'resume' | 'clear' | 'compact'; // Per docs
  session_id: string;
}

// ============================================
// UUID ISOLATION: Path construction & parsing
// ============================================

/**
 * Build handoff directory name with UUID suffix for isolation.
 * Format: {sessionName}-{first8CharsOfUUID}
 * Example: "auth-refactor-550e8400"
 */
export function buildHandoffDirName(sessionName: string, sessionId: string): string {
  const uuidShort = sessionId.replace(/-/g, '').slice(0, 8);
  return `${sessionName}-${uuidShort}`;
}

/**
 * Parse handoff directory name to extract session name and UUID suffix.
 * Returns { sessionName, uuidShort } where uuidShort is null for legacy dirs.
 */
export function parseHandoffDirName(dirName: string): { sessionName: string; uuidShort: string | null } {
  // Check if ends with -[8 hex chars]
  const match = dirName.match(/^(.+)-([0-9a-f]{8})$/i);
  if (match) {
    return { sessionName: match[1], uuidShort: match[2].toLowerCase() };
  }
  // Legacy format: no UUID suffix
  return { sessionName: dirName, uuidShort: null };
}

/**
 * Find handoff with UUID isolation support.
 * Priority:
 * 1. Exact UUID match: {sessionName}-{uuidShort}/
 * 2. Legacy path: {sessionName}/
 * 3. Any other UUID-suffixed dir for same session name (fallback)
 */
export function findSessionHandoffWithUUID(sessionName: string, sessionId: string): string | null {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const handoffsBase = path.join(projectDir, 'thoughts', 'shared', 'handoffs');

  if (!fs.existsSync(handoffsBase)) return null;

  const uuidShort = sessionId.replace(/-/g, '').slice(0, 8).toLowerCase();

  // Priority 1: Exact UUID match
  const exactDir = path.join(handoffsBase, `${sessionName}-${uuidShort}`);
  if (fs.existsSync(exactDir)) {
    return findMostRecentMdFile(exactDir);
  }

  // Priority 2: Legacy path (no UUID suffix)
  const legacyDir = path.join(handoffsBase, sessionName);
  if (fs.existsSync(legacyDir) && fs.statSync(legacyDir).isDirectory()) {
    const result = findMostRecentMdFile(legacyDir);
    if (result) return result;
  }

  // Priority 3: Any UUID-suffixed dir for same session name
  const allDirs = fs.readdirSync(handoffsBase).filter(d => {
    const stat = fs.statSync(path.join(handoffsBase, d));
    if (!stat.isDirectory()) return false;
    const { sessionName: parsedName } = parseHandoffDirName(d);
    return parsedName === sessionName;
  });

  // Sort by mtime (most recent first)
  allDirs.sort((a, b) => {
    const statA = fs.statSync(path.join(handoffsBase, a));
    const statB = fs.statSync(path.join(handoffsBase, b));
    return statB.mtime.getTime() - statA.mtime.getTime();
  });

  for (const dir of allDirs) {
    const result = findMostRecentMdFile(path.join(handoffsBase, dir));
    if (result) return result;
  }

  return null;
}

/**
 * Find most recent .md file in a directory by mtime.
 */
function findMostRecentMdFile(dirPath: string): string | null {
  if (!fs.existsSync(dirPath)) return null;

  const mdFiles = fs.readdirSync(dirPath)
    .filter(f => f.endsWith('.md'))
    .sort((a, b) => {
      const statA = fs.statSync(path.join(dirPath, a));
      const statB = fs.statSync(path.join(dirPath, b));
      return statB.mtime.getTime() - statA.mtime.getTime();
    });

  return mdFiles.length > 0 ? path.join(dirPath, mdFiles[0]) : null;
}

/**
 * Extract the Ledger section from handoff content.
 * Matches from "## Ledger" to the first "---" separator or next "## " heading (but not ### subsections).
 * Returns the full Ledger section with header, or null if not found.
 */
export function extractLedgerSection(handoffContent: string): string | null {
  // (?:^|\n) - match start of string or after newline
  // ## Ledger\n - the section header
  // ([\s\S]*?) - capture content (non-greedy)
  // (?=\n---\n|\n## [^#]|$) - stop at:
  //   - \n---\n: separator line
  //   - \n## [^#]: another ## heading (but not ### which starts with ##)
  //   - $: end of string
  const match = handoffContent.match(/(?:^|\n)## Ledger\n([\s\S]*?)(?=\n---\n|\n## [^#]|$)/);
  return match ? `## Ledger\n${match[1].trim()}` : null;
}

/**
 * Find the most recent handoff file for a given session.
 * Looks in thoughts/shared/handoffs/{sessionName}/ directory.
 * Returns absolute path to the most recent .md file by mtime, or null if not found.
 */
export function findSessionHandoff(sessionName: string): string | null {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const handoffDir = path.join(projectDir, 'thoughts', 'shared', 'handoffs', sessionName);

  if (!fs.existsSync(handoffDir)) return null;

  const handoffFiles = fs.readdirSync(handoffDir)
    .filter(f => f.endsWith('.md'))
    .sort((a, b) => {
      const statA = fs.statSync(path.join(handoffDir, a));
      const statB = fs.statSync(path.join(handoffDir, b));
      return statB.mtime.getTime() - statA.mtime.getTime();
    });

  return handoffFiles.length > 0 ? path.join(handoffDir, handoffFiles[0]) : null;
}

interface HandoffSummary {
  filename: string;
  taskNumber: string;
  status: string;
  summary: string;
  isAutoHandoff: boolean;
}

/**
 * Prune ledger to prevent bloat:
 * 1. Remove all "Session Ended" entries
 * 2. Keep only the last 10 agent reports
 */
function pruneLedger(ledgerPath: string): void {
  let content = fs.readFileSync(ledgerPath, 'utf-8');
  const originalLength = content.length;

  // 1. Remove all "Session Ended" entries
  content = content.replace(/\n### Session Ended \([^)]+\)\n- Reason: \w+\n/g, '');

  // 2. Keep only the last 10 agent reports
  const agentReportsMatch = content.match(/## Agent Reports\n([\s\S]*?)(?=\n## |$)/);
  if (agentReportsMatch) {
    const agentReportsSection = agentReportsMatch[0];
    const reports = agentReportsSection.match(/### [^\n]+ \(\d{4}-\d{2}-\d{2}[^)]*\)[\s\S]*?(?=\n### |\n## |$)/g);

    if (reports && reports.length > 10) {
      // Keep only the last 10 reports
      const keptReports = reports.slice(-10);
      const newAgentReportsSection = '## Agent Reports\n' + keptReports.join('');
      content = content.replace(agentReportsSection, newAgentReportsSection);
    }
  }

  // Only write if content changed
  if (content.length !== originalLength) {
    fs.writeFileSync(ledgerPath, content);
    console.error(`Pruned ledger: ${originalLength} → ${content.length} bytes`);
  }
}

function getLatestHandoff(handoffDir: string): HandoffSummary | null {
  if (!fs.existsSync(handoffDir)) return null;

  // Match both task-*.md and auto-handoff-*.md files
  const handoffFiles = fs.readdirSync(handoffDir)
    .filter(f => (f.startsWith('task-') || f.startsWith('auto-handoff-')) && f.endsWith('.md'))
    .sort((a, b) => {
      // Sort by modification time (most recent first)
      const statA = fs.statSync(path.join(handoffDir, a));
      const statB = fs.statSync(path.join(handoffDir, b));
      return statB.mtime.getTime() - statA.mtime.getTime();
    });

  if (handoffFiles.length === 0) return null;

  const latestFile = handoffFiles[0];
  const content = fs.readFileSync(path.join(handoffDir, latestFile), 'utf-8');
  const isAutoHandoff = latestFile.startsWith('auto-handoff-');

  // Extract key info from handoff based on type
  let taskNumber: string;
  let status: string;
  let summary: string;

  if (isAutoHandoff) {
    // Auto-handoff format: type: auto-handoff in frontmatter
    const typeMatch = content.match(/type:\s*auto-handoff/i);
    status = typeMatch ? 'auto-handoff' : 'unknown';

    // Extract timestamp from filename as "task number"
    const timestampMatch = latestFile.match(/auto-handoff-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})/);
    taskNumber = timestampMatch ? timestampMatch[1] : 'auto';

    // Get summary from In Progress section
    const inProgressMatch = content.match(/## In Progress\n([\s\S]*?)(?=\n## |$)/);
    summary = inProgressMatch
      ? inProgressMatch[1].trim().split('\n').slice(0, 3).join('; ').substring(0, 150)
      : 'Auto-handoff from pre-compact';
  } else {
    // Task handoff format: status: success/partial/blocked
    const taskMatch = latestFile.match(/task-(\d+)/);
    taskNumber = taskMatch ? taskMatch[1] : '??';

    const statusMatch = content.match(/status:\s*(success|partial|blocked)/i);
    status = statusMatch ? statusMatch[1] : 'unknown';

    const summaryMatch = content.match(/## What Was Done\n([\s\S]*?)(?=\n## |$)/);
    summary = summaryMatch
      ? summaryMatch[1].trim().split('\n').slice(0, 2).join('; ').substring(0, 150)
      : 'No summary available';
  }

  return {
    filename: latestFile,
    taskNumber,
    status,
    summary,
    isAutoHandoff
  };
}

// Artifact Index precedent query removed - redundant with:
// 1. Learnings now compounded into .claude/rules/ (permanent)
// 2. Ledger already provides session context
// 3. Hierarchical --learn uses handoff context at extraction time
// Kept: unmarked outcomes prompt (drives data quality)

interface UnmarkedHandoff {
  id: string;
  session_name: string;
  task_number: string | null;
  task_summary: string;
}

function getUnmarkedHandoffs(): UnmarkedHandoff[] {
  try {
    const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
    const dbPath = path.join(projectDir, '.claude', 'cache', 'artifact-index', 'context.db');

    if (!fs.existsSync(dbPath)) {
      return [];
    }

    const result = execSync(
      `sqlite3 "${dbPath}" "SELECT id, session_name, task_number, task_summary FROM handoffs WHERE outcome = 'UNKNOWN' ORDER BY indexed_at DESC LIMIT 5"`,
      { encoding: 'utf-8', timeout: 3000 }
    );

    if (!result.trim()) {
      return [];
    }

    return result.trim().split('\n').map(line => {
      const [id, session_name, task_number, task_summary] = line.split('|');
      return { id, session_name, task_number: task_number || null, task_summary: task_summary || '' };
    });
  } catch (error) {
    return [];
  }
}

async function main() {
  const input: SessionStartInput = JSON.parse(await readStdin());
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();

  // Support both 'source' (per docs) and 'type' (legacy) fields
  const sessionType = input.source || input.type;

  let message = '';
  let additionalContext = '';
  let usedHandoffLedger = false;

  // ============================================
  // NEW: Check handoffs for embedded Ledger sections FIRST
  // ============================================
  const handoffsDir = path.join(projectDir, 'thoughts', 'shared', 'handoffs');
  if (fs.existsSync(handoffsDir)) {
    try {
      const sessionDirs = fs.readdirSync(handoffsDir)
        .filter(d => {
          const stat = fs.statSync(path.join(handoffsDir, d));
          return stat.isDirectory();
        });

      // Find most recent handoff with Ledger section
      let mostRecentLedger: {
        content: string;
        sessionName: string;
        handoffPath: string;
        mtime: number;
        goalSummary: string;
        currentFocus: string;
      } | null = null;

      for (const sessionName of sessionDirs) {
        const handoffPath = findSessionHandoff(sessionName);
        if (handoffPath) {
          const content = fs.readFileSync(handoffPath, 'utf-8');
          const ledgerSection = extractLedgerSection(content);
          if (ledgerSection) {
            const mtime = fs.statSync(handoffPath).mtime.getTime();
            if (!mostRecentLedger || mtime > mostRecentLedger.mtime) {
              // Extract goal and focus from the Ledger section
              const goalMatch = ledgerSection.match(/\*\*Goal:\*\*\s*([^\n]+)/);
              const nowMatch = ledgerSection.match(/### Now\n\[?-?>?\]?\s*([^\n]+)/);

              mostRecentLedger = {
                content: ledgerSection,
                sessionName,
                handoffPath,
                mtime,
                goalSummary: goalMatch ? goalMatch[1].trim().substring(0, 100) : 'No goal found',
                currentFocus: nowMatch ? nowMatch[1].trim() : 'Unknown'
              };
            }
          }
        }
      }

      if (mostRecentLedger) {
        usedHandoffLedger = true;
        const { sessionName, goalSummary, currentFocus, content: ledgerSection, handoffPath } = mostRecentLedger;
        const handoffFilename = path.basename(handoffPath);

        if (sessionType === 'startup') {
          // Fresh startup: brief notification
          message = `📋 Handoff Ledger: ${sessionName} → ${currentFocus} (run /resume_handoff to continue)`;
        } else {
          // resume/clear/compact: load full Ledger section
          console.error(`✓ Handoff Ledger loaded: ${sessionName} → ${currentFocus}`);
          message = `[${sessionType}] Loaded from handoff: ${handoffFilename} | Goal: ${goalSummary} | Focus: ${currentFocus}`;

          if (sessionType === 'clear' || sessionType === 'compact') {
            additionalContext = `Handoff Ledger loaded from ${handoffFilename}:\n\n${ledgerSection}`;

            // Check for unmarked handoffs
            const unmarkedHandoffs = getUnmarkedHandoffs();
            if (unmarkedHandoffs.length > 0) {
              additionalContext += `\n\n---\n\n## Unmarked Session Outcomes\n\n`;
              additionalContext += `The following handoffs have no outcome marked. Consider marking them to improve future session recommendations:\n\n`;
              for (const h of unmarkedHandoffs) {
                const taskLabel = h.task_number ? `task-${h.task_number}` : 'handoff';
                const summaryPreview = h.task_summary ? h.task_summary.substring(0, 60) + '...' : '(no summary)';
                additionalContext += `- **${h.session_name}/${taskLabel}** (ID: \`${h.id.substring(0, 8)}\`): ${summaryPreview}\n`;
              }
              additionalContext += `\nTo mark an outcome:\n\`\`\`bash\nuv run python scripts/artifact_mark.py --handoff <ID> --outcome SUCCEEDED|PARTIAL_PLUS|PARTIAL_MINUS|FAILED\n\`\`\`\n`;
            }

            // Add full handoff path for reference
            additionalContext += `\n\n---\n\nFull handoff available at: ${handoffPath}\n`;
          }
        }
      }
    } catch (error) {
      // Gracefully handle errors scanning handoffs directory
      console.error(`Warning: Error scanning handoffs: ${error}`);
    }
  }

  // ============================================
  // FALLBACK: Legacy ledger files (if no handoff Ledger found)
  // ============================================
  if (!usedHandoffLedger) {
    const ledgerDir = path.join(projectDir, 'thoughts', 'ledgers');
    if (!fs.existsSync(ledgerDir)) {
      // No thoughts/ledgers directory - exit silently (normal for new projects)
      console.log(JSON.stringify({ result: 'continue' }));
      return;
    }
    const ledgerFiles = fs.readdirSync(ledgerDir)
      .filter(f => f.startsWith('CONTINUITY_CLAUDE-') && f.endsWith('.md'))
      .sort((a, b) => {
        const statA = fs.statSync(path.join(ledgerDir, a));
        const statB = fs.statSync(path.join(ledgerDir, b));
        return statB.mtime.getTime() - statA.mtime.getTime();
      });

    if (ledgerFiles.length > 0) {
      // DEPRECATED: Legacy ledger file path
      console.error('DEPRECATED: Using legacy ledger file. Migrate to handoff format with /create_handoff');

      const mostRecent = ledgerFiles[0];
      const ledgerPath = path.join(ledgerDir, mostRecent);

      // Prune ledger before reading to prevent bloat
      pruneLedger(ledgerPath);

      const ledgerContent = fs.readFileSync(ledgerPath, 'utf-8');

      // Extract key sections for summary
      const goalMatch = ledgerContent.match(/## Goal\n([\s\S]*?)(?=\n## |$)/);
      const nowMatch = ledgerContent.match(/- Now: ([^\n]+)/);

      const goalSummary = goalMatch
        ? goalMatch[1].trim().split('\n')[0].substring(0, 100)
        : 'No goal found';

      const currentFocus = nowMatch
        ? nowMatch[1].trim()
        : 'Unknown';

      const sessionName = mostRecent.replace('CONTINUITY_CLAUDE-', '').replace('.md', '');

      // Check for handoff directory
      const handoffDir = path.join(projectDir, 'thoughts', 'shared', 'handoffs', sessionName);
      const latestHandoff = getLatestHandoff(handoffDir);

      if (sessionType === 'startup') {
        // Fresh startup: just notify ledger exists, don't load full context
        let startupMsg = `📋 Ledger available: ${sessionName} → ${currentFocus}`;
        if (latestHandoff) {
          if (latestHandoff.isAutoHandoff) {
            startupMsg += ` | Last handoff: auto (${latestHandoff.status})`;
          } else {
            startupMsg += ` | Last handoff: task-${latestHandoff.taskNumber} (${latestHandoff.status})`;
          }
        }
        startupMsg += ' (run /resume_handoff to continue)';
        message = startupMsg;
      } else {
        // resume/clear/compact: load full context
        console.error(`✓ Ledger loaded: ${sessionName} → ${currentFocus}`);
        message = `[${sessionType}] Loaded: ${mostRecent} | Goal: ${goalSummary} | Focus: ${currentFocus}`;

        // For clear/compact, provide full ledger content as additional context
        if (sessionType === 'clear' || sessionType === 'compact') {
          additionalContext = `Continuity ledger loaded from ${mostRecent}:\n\n${ledgerContent}`;

          // Check for unmarked handoffs and prompt user to mark outcomes
          const unmarkedHandoffs = getUnmarkedHandoffs();
          if (unmarkedHandoffs.length > 0) {
            additionalContext += `\n\n---\n\n## Unmarked Session Outcomes\n\n`;
            additionalContext += `The following handoffs have no outcome marked. Consider marking them to improve future session recommendations:\n\n`;
            for (const h of unmarkedHandoffs) {
              const taskLabel = h.task_number ? `task-${h.task_number}` : 'handoff';
              const summaryPreview = h.task_summary ? h.task_summary.substring(0, 60) + '...' : '(no summary)';
              additionalContext += `- **${h.session_name}/${taskLabel}** (ID: \`${h.id.substring(0, 8)}\`): ${summaryPreview}\n`;
            }
            additionalContext += `\nTo mark an outcome:\n\`\`\`bash\nuv run python scripts/artifact_mark.py --handoff <ID> --outcome SUCCEEDED|PARTIAL_PLUS|PARTIAL_MINUS|FAILED\n\`\`\`\n`;
          }

          // Add handoff context if available
          if (latestHandoff) {
            const handoffPath = path.join(handoffDir, latestHandoff.filename);
            const handoffContent = fs.readFileSync(handoffPath, 'utf-8');

            const handoffLabel = latestHandoff.isAutoHandoff ? 'Latest auto-handoff' : 'Latest task handoff';
            additionalContext += `\n\n---\n\n${handoffLabel} (${latestHandoff.filename}):\n`;
            additionalContext += `Status: ${latestHandoff.status}${latestHandoff.isAutoHandoff ? '' : ` | Task: ${latestHandoff.taskNumber}`}\n\n`;

            // Include truncated handoff content (first 2000 chars)
            const truncatedHandoff = handoffContent.length > 2000
              ? handoffContent.substring(0, 2000) + '\n\n[... truncated, read full file if needed]'
              : handoffContent;
            additionalContext += truncatedHandoff;

            // List other handoffs in directory
            const allHandoffs = fs.readdirSync(handoffDir)
              .filter(f => (f.startsWith('task-') || f.startsWith('auto-handoff-')) && f.endsWith('.md'))
              .sort((a, b) => {
                // Sort by modification time (most recent first)
                const statA = fs.statSync(path.join(handoffDir, a));
                const statB = fs.statSync(path.join(handoffDir, b));
                return statB.mtime.getTime() - statA.mtime.getTime();
              });
            if (allHandoffs.length > 1) {
              additionalContext += `\n\n---\n\nAll handoffs in ${handoffDir}:\n`;
              allHandoffs.forEach(f => {
                additionalContext += `- ${f}\n`;
              });
            }
          }

          // Learnings are now extracted via --learn and compounded via /compound-learnings skill
          // No need to surface raw learnings at SessionStart - they become permanent rules
        }
      }
    } else {
      // No ledger found
      if (sessionType !== 'startup') {
        console.error(`⚠ No ledger found. Run /continuity_ledger to track session state.`);
        message = `[${sessionType}] No ledger found. Consider running /continuity_ledger to track session state.`;
      }
      // For startup without ledger, stay silent (normal case)
    }
  }

  // Output with proper format per Claude Code docs
  const output: Record<string, unknown> = { result: 'continue' };

  if (message) {
    output.message = message;
    output.systemMessage = message;  // Try both fields for visibility
  }

  if (additionalContext) {
    output.hookSpecificOutput = {
      hookEventName: 'SessionStart',
      additionalContext: additionalContext
    };
  }

  console.log(JSON.stringify(output));
}

async function readStdin(): Promise<string> {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.on('data', chunk => data += chunk);
    process.stdin.on('end', () => resolve(data));
  });
}

main().catch(console.error);
