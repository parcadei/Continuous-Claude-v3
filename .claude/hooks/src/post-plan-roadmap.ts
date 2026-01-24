#!/usr/bin/env node
/**
 * Post-Plan ROADMAP Hook
 *
 * Fires on PostToolUse for ExitPlanMode to update ROADMAP.md with planning decisions.
 * This enables the Knowledge Tree to track project goals and progression.
 *
 * Hook: PostToolUse (ExitPlanMode)
 * Output: Updates {project}/ROADMAP.md
 */

import * as fs from 'fs';
import * as path from 'path';

interface PostToolUseInput {
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_output?: string;
  tool_result?: string;
}

interface RoadmapSection {
  current: { title: string; description: string; started: string } | null;
  completed: Array<{ title: string; completed: string }>;
  planned: Array<{ title: string; priority: string }>;
  sessions: Array<{ date: string; title: string; decisions: string[] }>;
}

function parseRoadmap(content: string): RoadmapSection {
  const result: RoadmapSection = {
    current: null,
    completed: [],
    planned: [],
    sessions: []
  };

  const lines = content.split('\n');
  let section: string | null = null;
  let currentTitle: string | null = null;

  for (const line of lines) {
    const stripped = line.trim();

    if (stripped.toLowerCase().startsWith('## current')) {
      section = 'current';
      continue;
    } else if (stripped.toLowerCase().startsWith('## completed')) {
      section = 'completed';
      continue;
    } else if (stripped.toLowerCase().startsWith('## planned')) {
      section = 'planned';
      continue;
    } else if (stripped.toLowerCase().startsWith('## recent planning')) {
      section = 'sessions';
      continue;
    } else if (stripped.startsWith('## ')) {
      section = null;
      continue;
    }

    if (section === 'current' && stripped.startsWith('**') && stripped.endsWith('**')) {
      currentTitle = stripped.replace(/\*\*/g, '').trim();
      result.current = { title: currentTitle, description: '', started: '' };
    } else if (section === 'current' && result.current && stripped.startsWith('-')) {
      const text = stripped.slice(1).trim();
      if (text.toLowerCase().startsWith('started:')) {
        result.current.started = text.replace(/^started:\s*/i, '');
      } else if (result.current.description) {
        result.current.description += '; ' + text;
      } else {
        result.current.description = text;
      }
    }

    if (section === 'completed') {
      const match = stripped.match(/^-\s*\[x\]\s*(.+?)(?:\s*\(([^)]+)\))?$/i);
      if (match) {
        result.completed.push({
          title: match[1].trim(),
          completed: match[2] || ''
        });
      }
    }

    if (section === 'planned') {
      const match = stripped.match(/^-\s*\[\s*\]\s*(.+?)(?:\s*\(([^)]+)\))?$/i);
      if (match) {
        let priority = 'medium';
        const prio = match[2] || '';
        if (prio.toLowerCase().includes('high')) priority = 'high';
        if (prio.toLowerCase().includes('low')) priority = 'low';
        result.planned.push({ title: match[1].trim(), priority });
      }
    }

    if (section === 'sessions' && stripped.startsWith('### ')) {
      const sessionMatch = stripped.match(/^###\s*(\d{4}-\d{2}-\d{2}):\s*(.+)$/);
      if (sessionMatch) {
        result.sessions.push({
          date: sessionMatch[1],
          title: sessionMatch[2].trim(),
          decisions: []
        });
      }
    } else if (section === 'sessions' && result.sessions.length > 0 && stripped.startsWith('-')) {
      const lastSession = result.sessions[result.sessions.length - 1];
      lastSession.decisions.push(stripped.slice(1).trim());
    }
  }

  return result;
}

function generateRoadmap(sections: RoadmapSection): string {
  const lines: string[] = ['# Project Roadmap', ''];

  lines.push('## Current Focus');
  if (sections.current) {
    lines.push(`**${sections.current.title}**`);
    if (sections.current.description) {
      lines.push(`- ${sections.current.description}`);
    }
    if (sections.current.started) {
      lines.push(`- Started: ${sections.current.started}`);
    }
  } else {
    lines.push('No current focus set.');
  }
  lines.push('');

  lines.push('## Completed');
  if (sections.completed.length > 0) {
    for (const item of sections.completed) {
      const dateStr = item.completed ? ` (${item.completed})` : '';
      lines.push(`- [x] ${item.title}${dateStr}`);
    }
  } else {
    lines.push('_No completed items yet._');
  }
  lines.push('');

  lines.push('## Planned');
  if (sections.planned.length > 0) {
    for (const item of sections.planned) {
      lines.push(`- [ ] ${item.title} (${item.priority} priority)`);
    }
  } else {
    lines.push('_No planned items yet._');
  }
  lines.push('');

  lines.push('## Recent Planning Sessions');
  if (sections.sessions.length > 0) {
    for (const session of sections.sessions.slice(0, 5)) {
      lines.push(`### ${session.date}: ${session.title}`);
      for (const decision of session.decisions) {
        lines.push(`- ${decision}`);
      }
      lines.push('');
    }
  } else {
    lines.push('_No planning sessions recorded._');
  }

  return lines.join('\n');
}

function extractPlanInfo(planContent: string): {
  title: string;
  decisions: string[];
  approach: string;
  affectedFiles: string[];
} {
  const result = {
    title: 'Planning Session',
    decisions: [] as string[],
    approach: '',
    affectedFiles: [] as string[]
  };

  const lines = planContent.split('\n');

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    if (line.startsWith('# ')) {
      result.title = line.slice(2).trim();
    }

    if (line.toLowerCase().includes('decision') || line.toLowerCase().includes('approach')) {
      if (line.startsWith('- ')) {
        result.decisions.push(line.slice(2).trim());
      } else if (i + 1 < lines.length && lines[i + 1].trim().startsWith('- ')) {
        let j = i + 1;
        while (j < lines.length && lines[j].trim().startsWith('- ')) {
          result.decisions.push(lines[j].trim().slice(2));
          j++;
        }
      }
    }

    if (line.toLowerCase().includes('file') && line.includes(':')) {
      const fileMatch = line.match(/`([^`]+)`/g);
      if (fileMatch) {
        result.affectedFiles.push(...fileMatch.map(f => f.replace(/`/g, '')));
      }
    }
  }

  return result;
}

async function main() {
  const input = await readStdin();
  if (!input.trim()) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  let data: PostToolUseInput;
  try {
    data = JSON.parse(input);
  } catch {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  if (data.tool_name !== 'ExitPlanMode') {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const roadmapPath = path.join(projectDir, 'ROADMAP.md');
  const planDir = path.join(projectDir, '.claude', 'plans');

  let planContent = '';
  if (fs.existsSync(planDir)) {
    const planFiles = fs.readdirSync(planDir)
      .filter(f => f.endsWith('.md'))
      .sort((a, b) => {
        const statA = fs.statSync(path.join(planDir, a));
        const statB = fs.statSync(path.join(planDir, b));
        return statB.mtime.getTime() - statA.mtime.getTime();
      });

    if (planFiles.length > 0) {
      planContent = fs.readFileSync(path.join(planDir, planFiles[0]), 'utf-8');
    }
  }

  const toolOutput = data.tool_output || data.tool_result || '';
  if (!planContent && toolOutput) {
    planContent = toolOutput;
  }

  let sections: RoadmapSection;
  if (fs.existsSync(roadmapPath)) {
    const existingContent = fs.readFileSync(roadmapPath, 'utf-8');
    sections = parseRoadmap(existingContent);
  } else {
    sections = {
      current: null,
      completed: [],
      planned: [],
      sessions: []
    };
  }

  const planInfo = extractPlanInfo(planContent);
  const today = new Date().toISOString().split('T')[0];

  if (planInfo.title && planInfo.title !== 'Planning Session') {
    if (sections.current && sections.current.title !== planInfo.title) {
      sections.completed.unshift({
        title: sections.current.title,
        completed: today
      });
    }

    sections.current = {
      title: planInfo.title,
      description: planInfo.decisions.slice(0, 2).join('; ') || '',
      started: today
    };
  }

  const newSession = {
    date: today,
    title: planInfo.title,
    decisions: planInfo.decisions.slice(0, 5)
  };

  const existingToday = sections.sessions.findIndex(s => s.date === today);
  if (existingToday >= 0) {
    sections.sessions[existingToday] = newSession;
  } else {
    sections.sessions.unshift(newSession);
  }

  sections.sessions = sections.sessions.slice(0, 10);

  const newContent = generateRoadmap(sections);
  fs.mkdirSync(path.dirname(roadmapPath), { recursive: true });
  fs.writeFileSync(roadmapPath, newContent, 'utf-8');

  console.error(`✓ ROADMAP.md updated: ${planInfo.title}`);

  const output = {
    result: 'continue',
    message: `📋 ROADMAP.md updated with planning session: ${planInfo.title}`,
    hookSpecificOutput: {
      hookEventName: 'PostToolUse',
      additionalContext: `Planning session recorded:\n- Goal: ${planInfo.title}\n- Decisions: ${planInfo.decisions.length}\n- ROADMAP.md: ${roadmapPath}`
    }
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
  console.error('post-plan-roadmap error:', err);
  console.log(JSON.stringify({ result: 'continue' }));
});
