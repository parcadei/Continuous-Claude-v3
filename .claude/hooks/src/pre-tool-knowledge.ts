#!/usr/bin/env node
/**
 * Pre-Tool Knowledge Injection Hook
 *
 * Injects knowledge tree context before implementation tasks.
 * Helps Claude Code find relevant files and understand project structure.
 *
 * Hook: PreToolUse (Task)
 * Condition: Implementation/coding task detected
 */

import * as fs from 'fs';
import * as path from 'path';

interface PreToolUseInput {
  tool_name: string;
  tool_input: Record<string, unknown>;
}

interface KnowledgeTree {
  version: string;
  project: {
    name: string;
    description: string;
    type: string;
    stack: string[];
  };
  structure: {
    root: string;
    directories: Record<string, { purpose: string; key_files?: string[] }>;
  };
  components: Array<{
    name: string;
    type: string;
    files: string[];
    description: string;
  }>;
  navigation: {
    common_tasks: Record<string, string[]>;
    entry_points: Record<string, string>;
  };
  goals: {
    source: string | null;
    current: { title: string; description: string; started?: string } | null;
    completed: Array<{ title: string; completed?: string }>;
    planned: Array<{ title: string; priority: string }>;
  };
}

const IMPLEMENTATION_TRIGGERS = [
  'implement', 'create', 'add', 'build', 'write',
  'develop', 'make', 'fix', 'update', 'refactor',
  'kraken', 'spark', 'architect'
];

const TASK_TYPE_PATTERNS: Record<string, string[]> = {
  'add_api_endpoint': ['api', 'endpoint', 'route', 'controller', 'rest'],
  'add_database_model': ['database', 'model', 'schema', 'migration', 'table'],
  'add_component': ['component', 'ui', 'view', 'page', 'widget'],
  'add_test': ['test', 'spec', 'testing', 'coverage'],
  'add_hook': ['hook', 'hooks'],
  'add_skill': ['skill', 'skills']
};

function isImplementationTask(input: PreToolUseInput): boolean {
  const toolName = input.tool_name.toLowerCase();
  const taskPrompt = String(input.tool_input?.prompt || '').toLowerCase();
  const subagentType = String(input.tool_input?.subagent_type || '').toLowerCase();

  if (toolName !== 'task') return false;

  for (const trigger of IMPLEMENTATION_TRIGGERS) {
    if (taskPrompt.includes(trigger) || subagentType.includes(trigger)) {
      return true;
    }
  }

  return false;
}

function detectTaskType(prompt: string): string | null {
  const promptLower = prompt.toLowerCase();

  for (const [taskType, keywords] of Object.entries(TASK_TYPE_PATTERNS)) {
    for (const keyword of keywords) {
      if (promptLower.includes(keyword)) {
        return taskType;
      }
    }
  }

  return null;
}

function loadKnowledgeTree(projectDir: string): KnowledgeTree | null {
  const treePath = path.join(projectDir, '.claude', 'knowledge-tree.json');

  if (!fs.existsSync(treePath)) {
    return null;
  }

  try {
    const content = fs.readFileSync(treePath, 'utf-8');
    return JSON.parse(content) as KnowledgeTree;
  } catch {
    return null;
  }
}

function buildContextForTask(tree: KnowledgeTree, taskType: string | null): string {
  const lines: string[] = ['## Project Knowledge Tree Context'];

  lines.push('');
  lines.push(`**Project:** ${tree.project.name} (${tree.project.type})`);

  if (tree.project.description) {
    lines.push(`**Description:** ${tree.project.description}`);
  }

  if (tree.project.stack.length > 0) {
    lines.push(`**Stack:** ${tree.project.stack.join(', ')}`);
  }

  if (tree.goals.current) {
    lines.push('');
    lines.push(`**Current Goal:** ${tree.goals.current.title}`);
    if (tree.goals.current.description) {
      lines.push(`  ${tree.goals.current.description}`);
    }
  }

  if (taskType && tree.navigation.common_tasks[taskType]) {
    lines.push('');
    lines.push(`**Relevant Locations for ${taskType}:**`);
    for (const loc of tree.navigation.common_tasks[taskType]) {
      const dirInfo = tree.structure.directories[loc];
      if (dirInfo) {
        lines.push(`- \`${loc}\`: ${dirInfo.purpose}`);
      } else {
        lines.push(`- \`${loc}\``);
      }
    }
  }

  const relevantComponents = tree.components.slice(0, 3);
  if (relevantComponents.length > 0) {
    lines.push('');
    lines.push('**Key Components:**');
    for (const comp of relevantComponents) {
      lines.push(`- **${comp.name}** (${comp.type}): ${comp.description || 'No description'}`);
      if (comp.files.length > 0) {
        lines.push(`  Files: ${comp.files.slice(0, 3).join(', ')}`);
      }
    }
  }

  if (Object.keys(tree.navigation.entry_points).length > 0) {
    lines.push('');
    lines.push('**Entry Points:**');
    for (const [name, loc] of Object.entries(tree.navigation.entry_points)) {
      lines.push(`- ${name}: \`${loc}\``);
    }
  }

  return lines.join('\n');
}

async function main() {
  const input = await readStdin();
  if (!input.trim()) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  let data: PreToolUseInput;
  try {
    data = JSON.parse(input);
  } catch {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  if (!isImplementationTask(data)) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const tree = loadKnowledgeTree(projectDir);

  if (!tree) {
    console.log(JSON.stringify({ result: 'continue' }));
    return;
  }

  const prompt = String(data.tool_input?.prompt || '');
  const taskType = detectTaskType(prompt);
  const context = buildContextForTask(tree, taskType);

  console.error(`✓ Knowledge tree context injected for: ${tree.project.name}`);

  const output = {
    result: 'continue',
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      additionalContext: context
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
  console.error('pre-tool-knowledge error:', err);
  console.log(JSON.stringify({ result: 'continue' }));
});
