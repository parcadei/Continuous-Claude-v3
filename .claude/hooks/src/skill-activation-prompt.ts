#!/usr/bin/env node
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { spawnSync } from 'child_process';
import { tmpdir } from 'os';

// Import shared resource reader (Phase 4 module)
import { readResourceState, ResourceState } from './shared/resource-reader.js';
import { outputContinue } from './shared/output.js';

// Import validation module for false-positive reduction
import {
    shouldValidateWithLLM,
    buildValidationPrompt,
    SkillMatch,
} from './skill-validation-prompt.js';

interface HookInput {
    session_id: string;
    transcript_path: string;
    cwd: string;
    permission_mode: string;
    prompt: string;
}

// Pattern inference result from Python module
interface PatternInference {
    pattern: string;
    confidence: number;
    signals: string[];
    needs_clarification: boolean;
    clarification_probe: string | null;
    ambiguity_type: string | null;
    alternatives: string[];
    work_breakdown: string;
    work_breakdown_detailed: string;
}

// Pattern-to-agent mapping
const PATTERN_AGENT_MAP: Record<string, string> = {
    'swarm': 'research-agent',
    'hierarchical': 'kraken',
    'pipeline': 'kraken',
    'generator_critic': 'review-agent',
    'adversarial': 'validate-agent',
    'map_reduce': 'kraken',
    'jury': 'validate-agent',
    'blackboard': 'maestro',
    'circuit_breaker': 'kraken',
    'chain_of_responsibility': 'maestro',
    'event_driven': 'kraken',
};

interface PromptTriggers {
    keywords?: string[];
    intentPatterns?: string[];
}

// Phase 2: High-confidence workflow triggers
// These trigger auto-invoke (blocking with clear instruction) when confidence > 0.9
interface WorkflowTrigger {
    skill: string;
    pattern: RegExp;
    antiPattern?: RegExp;
    confidence: number;
    description: string;
}

const WORKFLOW_TRIGGERS: WorkflowTrigger[] = [
    {
        skill: 'fix',
        pattern: /\b(fix|debug|broken|failing)\s+(the\s+)?(bug|error|issue|problem)/i,
        antiPattern: /\b(don't|do\s+not|no\s+need\s+to)\s+fix/i,
        confidence: 0.95,
        description: 'Bug/error investigation and resolution'
    },
    {
        skill: 'build',
        pattern: /\b(build|create|implement)\s+(?:a\s+)?(?:new\s+)?(feature|component|page|module|api|endpoint)/i,
        antiPattern: /\b(don't|do\s+not)\s+(build|create|implement)/i,
        confidence: 0.90,
        description: 'Feature development workflow'
    },
    {
        skill: 'commit',
        pattern: /\b(commit|save)\s+(these\s+|the\s+|my\s+)?changes/i,
        antiPattern: /\b(don't|do\s+not|before\s+you)\s+commit/i,
        confidence: 0.95,
        description: 'Git commit workflow'
    },
    {
        skill: 'explore',
        pattern: /\b(explore|understand|navigate|analyze)\s+(the\s+)?(codebase|project|repository|code\s+structure)/i,
        confidence: 0.90,
        description: 'Codebase exploration and understanding'
    },
    {
        skill: 'ralph',
        pattern: /\b(start|run|launch|use)\s+ralph/i,
        confidence: 0.99,
        description: 'Ralph autonomous development workflow'
    },
    {
        skill: 'refactor',
        pattern: /\brefactor\s+(the\s+)?(this\s+)?(code|function|class|module|component)/i,
        confidence: 0.90,
        description: 'Code refactoring workflow'
    },
    {
        skill: 'test',
        pattern: /\b(write|add|create)\s+(unit\s+|integration\s+)?tests?\s+for/i,
        confidence: 0.85,
        description: 'Test writing workflow'
    }
];

/**
 * Check if prompt matches a high-confidence workflow trigger.
 * Returns the workflow to auto-invoke, or null if no match.
 */
function checkWorkflowTriggers(prompt: string): WorkflowTrigger | null {
    for (const trigger of WORKFLOW_TRIGGERS) {
        if (trigger.pattern.test(prompt)) {
            if (trigger.antiPattern && trigger.antiPattern.test(prompt)) {
                continue;
            }
            return trigger;
        }
    }
    return null;
}

interface SkillRule {
    type: 'guardrail' | 'domain';
    enforcement: 'block' | 'suggest' | 'warn';
    priority: 'critical' | 'high' | 'medium' | 'low';
    promptTriggers?: PromptTriggers;
    description?: string;
}

interface SkillRules {
    version: string;
    skills: Record<string, SkillRule>;
    agents?: Record<string, SkillRule>;
}

interface MatchedSkill {
    name: string;
    matchType: 'keyword' | 'intent';
    matchedTerm?: string;
    config: SkillRule;
    isAgent?: boolean;
    needsValidation?: boolean;
}

/**
 * Run pattern inference using the Python module.
 * Returns null if inference fails or module not available.
 *
 * Cross-platform: Uses spawnSync with cwd option (works on Windows/macOS/Linux).
 */
function runPatternInference(prompt: string, projectDir: string): PatternInference | null {
    // Defense in depth: Skip in ~/.claude (infrastructure directory)
    const homeDir = process.env.HOME || process.env.USERPROFILE || '';
    if (homeDir) {
        const claudeDir = homeDir.replace(/\\/g, '/') + '/.claude';
        const normalizedProject = projectDir.replace(/\\/g, '/');
        if (normalizedProject === claudeDir || normalizedProject.endsWith('/.claude')) {
            return null;
        }
    }

    try {
        const scriptPath = join(projectDir, 'scripts', 'agentica_patterns', 'pattern_inference.py');
        if (!existsSync(scriptPath)) {
            return null;
        }

        // Build Python code as a string (no shell escaping needed with spawnSync)
        const pythonCode = `
import sys
import json
import importlib.util

# Direct import bypassing __init__.py
spec = importlib.util.spec_from_file_location(
    'pattern_inference',
    ${JSON.stringify(scriptPath)}
)
pattern_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pattern_mod)

prompt = ${JSON.stringify(prompt)}
result = pattern_mod.infer_pattern(prompt)
output = result.to_dict()
output['work_breakdown_detailed'] = pattern_mod.generate_work_breakdown(result)
print(json.dumps(output))
`;

        // Cross-platform: use spawnSync with cwd instead of shell cd && command
        const result = spawnSync('uv', ['run', 'python', '-c', pythonCode], {
            encoding: 'utf-8',
            timeout: 2000,
            cwd: projectDir,
            stdio: ['pipe', 'pipe', 'pipe'],
            killSignal: 'SIGKILL',
        });

        if (result.status !== 0 || !result.stdout) {
            return null;
        }

        return JSON.parse(result.stdout.trim()) as PatternInference;
    } catch (err) {
        // Pattern inference is optional - fail silently
        return null;
    }
}

/**
 * Generate agentica orchestration output based on pattern inference.
 */
function generateAgenticaOutput(inference: PatternInference, prompt: string): string {
    let output = '\n';
    output += '='.repeat(50) + '\n';
    output += 'AGENTICA PATTERN INFERENCE\n';
    output += '='.repeat(50) + '\n';
    output += '\n';

    if (inference.confidence >= 0.7) {
        const suggestedAgent = PATTERN_AGENT_MAP[inference.pattern] || 'kraken';
        output += 'SUGGESTED APPROACH:\n';
        output += `  Agent: ${suggestedAgent}\n`;
        output += `  Pattern: ${inference.work_breakdown_detailed}\n`;
        const confidencePct = Math.round(inference.confidence * 100);
        output += `  Confidence: ${confidencePct}%\n`;
        output += '\n';
        output += 'ACTION: Use AskUserQuestion to confirm before spawning:\n';
        output += `  "I'll use ${suggestedAgent} to ${inference.work_breakdown}. Proceed?"\n`;
        output += '  Options: [Yes, proceed] [Different approach] [Let me explain more]\n';
        if (inference.alternatives.length > 0) {
            output += `\nAlternative approaches available: ${inference.alternatives.join(', ')}\n`;
        }
    } else {
        // Low confidence - ask CDM probe
        output += 'CLARIFICATION NEEDED:\n';
        output += '\n';
        if (inference.clarification_probe) {
            output += `Ask the user: "${inference.clarification_probe}"\n`;
        }
        output += '\n';
        output += 'Initial analysis suggests: ' + inference.work_breakdown + '\n';
        const confidencePct = Math.round(inference.confidence * 100);
        output += `Confidence: ${confidencePct}%\n`;
        output += '\n';
        output += 'ACTION: Use AskUserQuestion to clarify before proceeding.\n';
    }

    output += '='.repeat(50) + '\n';
    return output;
}

/**
 * Detect semantic/natural language queries that would benefit from TLDR semantic search.
 * Pattern: Questions starting with how/what/where/why/when/which
 */
function detectSemanticQuery(prompt: string): { isSemanticQuery: boolean; suggestion?: string } {
    // Question word patterns that indicate semantic queries
    const semanticPatterns = [
        /^(how|what|where|why|when|which)\s/i,
        /\?$/,
        /^(find|show|list|get|explain)\s+(all|the|every|any)/i,
        /^.*\s+(implementation|architecture|flow|pattern|logic|system)$/i,
    ];

    const isSemanticQuery = semanticPatterns.some(p => p.test(prompt.trim()));

    if (!isSemanticQuery) {
        return { isSemanticQuery: false };
    }

    // Generate suggestion for semantic search
    const shortPrompt = prompt.length > 50 ? prompt.slice(0, 50) + '...' : prompt;
    const suggestion = `💡 **Semantic Query Detected**

Your question "${shortPrompt}" may benefit from semantic code search.

**Try:**
\`\`\`bash
tldr semantic search "${prompt.slice(0, 100)}" .
\`\`\`

Or use the /explore skill for guided exploration.
`;

    return { isSemanticQuery: true, suggestion };
}

async function main() {
    try {
        // Read input from stdin
        const input = readFileSync(0, 'utf-8');
        let data: HookInput;
        try {
            data = JSON.parse(input);
        } catch {
            // Malformed JSON - exit silently
            outputContinue();
            process.exit(0);
        }

        // Early validation - prompt is required
        if (!data.prompt || typeof data.prompt !== 'string') {
            outputContinue();
            process.exit(0);
        }

        // Guard: Skip in ~/.claude (infrastructure directory)
        const homeDir = process.env.HOME || process.env.USERPROFILE || '';
        if (homeDir) {
            const claudeDir = homeDir.replace(/\\/g, '/') + '/.claude';
            const normalizedCwd = (data.cwd || '').replace(/\\/g, '/');
            if (normalizedCwd === claudeDir || normalizedCwd.endsWith('/.claude')) {
                outputContinue();
                process.exit(0);
            }
        }

        const prompt = data.prompt.toLowerCase();

        // Load skill rules (try project first, then global)
        const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
        const projectRulesPath = join(projectDir, '.claude', 'skills', 'skill-rules.json');
        const globalRulesPath = join(homeDir, '.claude', 'skills', 'skill-rules.json');

        let rulesPath = '';
        if (existsSync(projectRulesPath)) {
            rulesPath = projectRulesPath;
        } else if (existsSync(globalRulesPath)) {
            rulesPath = globalRulesPath;
        } else {
            // No rules file found, exit silently
            outputContinue();
            process.exit(0);
        }
        const rules: SkillRules = JSON.parse(readFileSync(rulesPath, 'utf-8'));

        // Phase 2: Check for high-confidence workflow triggers FIRST
        // Output message directly - UserPromptSubmit hooks inject context, they don't truly block
        const workflowTrigger = checkWorkflowTriggers(data.prompt);
        if (workflowTrigger && workflowTrigger.confidence >= 0.90) {
            const confidencePct = Math.round(workflowTrigger.confidence * 100);
            const autoInvokeMessage = `
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 WORKFLOW DETECTED: /${workflowTrigger.skill}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

High-confidence workflow match (${confidencePct}%):
  → ${workflowTrigger.description}

⚠️ ACTION REQUIRED - INVOKE SKILL FIRST:
Use the Skill tool with: { "skill": "${workflowTrigger.skill}" }

Do NOT skip this step. The skill provides:
- Structured methodology for this task type
- Built-in verification steps
- Proper agent orchestration

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`;
            // Output directly - this gets injected into Claude's context
            console.log(autoInvokeMessage);
            outputContinue();
            process.exit(0);
        }

        // CHANGE 1: Run pattern inference EARLY on all prompts
        const patternInference = runPatternInference(data.prompt, projectDir);

        // CHANGE 3: Detect semantic queries and suggest TLDR semantic search
        const semanticQuery = detectSemanticQuery(data.prompt);

        const matchedSkills: MatchedSkill[] = [];

        // Check each skill for matches
        for (const [skillName, config] of Object.entries(rules.skills)) {
            const triggers = config.promptTriggers;
            if (!triggers) {
                continue;
            }

            // Keyword matching
            if (triggers.keywords) {
                const matchedKeyword = triggers.keywords.find(kw =>
                    prompt.includes(kw.toLowerCase())
                );
                if (matchedKeyword) {
                    // Check if this match needs LLM validation
                    const skillMatchForValidation: SkillMatch = {
                        skillName,
                        matchType: 'keyword',
                        matchedTerm: matchedKeyword,
                        prompt: data.prompt, // Use original prompt (not lowercased)
                        skillDescription: config.description,
                        enforcement: config.enforcement,
                    };
                    const needsValidation = shouldValidateWithLLM(skillMatchForValidation);

                    matchedSkills.push({
                        name: skillName,
                        matchType: 'keyword',
                        matchedTerm: matchedKeyword,
                        config,
                        needsValidation,
                    });
                    continue;
                }
            }

            // Intent pattern matching (no validation needed - strong signal)
            if (triggers.intentPatterns) {
                const intentMatch = triggers.intentPatterns.some(pattern => {
                    try {
                        const regex = new RegExp(pattern, 'i');
                        return regex.test(prompt);
                    } catch {
                        // Invalid regex pattern, skip
                        return false;
                    }
                });
                if (intentMatch) {
                    matchedSkills.push({
                        name: skillName,
                        matchType: 'intent',
                        config,
                        needsValidation: false,
                    });
                }
            }
        }

        // Check each agent for matches
        const matchedAgents: MatchedSkill[] = [];
        if (rules.agents) {
            for (const [agentName, config] of Object.entries(rules.agents)) {
                const triggers = config.promptTriggers;
                if (!triggers) {
                    continue;
                }

                // Keyword matching
                if (triggers.keywords) {
                    const matchedKeyword = triggers.keywords.find(kw =>
                        prompt.includes(kw.toLowerCase())
                    );
                    if (matchedKeyword) {
                        // Check if this match needs LLM validation
                        const skillMatchForValidation: SkillMatch = {
                            skillName: agentName,
                            matchType: 'keyword',
                            matchedTerm: matchedKeyword,
                            prompt: data.prompt,
                            skillDescription: config.description,
                            enforcement: config.enforcement,
                        };
                        const needsValidation = shouldValidateWithLLM(skillMatchForValidation);

                        matchedAgents.push({
                            name: agentName,
                            matchType: 'keyword',
                            matchedTerm: matchedKeyword,
                            config,
                            isAgent: true,
                            needsValidation,
                        });
                        continue;
                    }
                }

                // Intent pattern matching (no validation needed - strong signal)
                if (triggers.intentPatterns) {
                    const intentMatch = triggers.intentPatterns.some(pattern => {
                        try {
                            const regex = new RegExp(pattern, 'i');
                            return regex.test(prompt);
                        } catch {
                            // Invalid regex pattern, skip
                            return false;
                        }
                    });
                    if (intentMatch) {
                        matchedAgents.push({
                            name: agentName,
                            matchType: 'intent',
                            config,
                            isAgent: true,
                            needsValidation: false,
                        });
                    }
                }
            }
        }

        // Generate output if matches found OR pattern inference succeeded OR semantic query detected
        if (matchedSkills.length > 0 || matchedAgents.length > 0 || patternInference || semanticQuery.isSemanticQuery) {
            // Check which skills need LLM validation (potential false positives)
            const skillsNeedingValidation = matchedSkills.filter(s => s.needsValidation);
            const agentsNeedingValidation = matchedAgents.filter(a => a.needsValidation);
            const allNeedingValidation = [...skillsNeedingValidation, ...agentsNeedingValidation];

            // Filter out skills that need validation from the main lists
            // (they will be shown in a separate section)
            const confirmedSkills = matchedSkills.filter(s => !s.needsValidation);
            const confirmedAgents = matchedAgents.filter(a => !a.needsValidation);

            let output = '';
            
            // CHANGE 2: Show pattern inference output FIRST if available
            if (patternInference) {
                output += generateAgenticaOutput(patternInference, data.prompt);
                output += '\n';
            }

            // CHANGE 3: Show semantic query suggestion if detected
            if (semanticQuery.isSemanticQuery && semanticQuery.suggestion) {
                output += semanticQuery.suggestion;
                output += '\n';
            }

            // Show skill activation check only if skills/agents matched
            if (matchedSkills.length > 0 || matchedAgents.length > 0) {
                output += '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n';
                output += '🎯 SKILL ACTIVATION CHECK\n';
                output += '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n';

                // Show skills needing validation FIRST
                if (allNeedingValidation.length > 0) {
                    output += '❓ AMBIGUOUS MATCHES (validate before activating):\n';
                    output += '   The following skills matched on keywords that may be used\n';
                    output += '   in a non-technical context. Consider if they\'re needed:\n\n';

                    for (const item of allNeedingValidation) {
                        const isAgent = item.isAgent ? ' [agent]' : '';
                        output += `   • ${item.name}${isAgent}\n`;
                        output += `     Matched: "${item.matchedTerm}" (keyword match)\n`;
                        if (item.config.description) {
                            output += `     Purpose: ${item.config.description}\n`;
                        }
                        output += `     → Skip if the user is NOT asking for this functionality\n`;
                        output += '\n';
                    }

                    output += '   VALIDATION: Before activating these, ask yourself:\n';
                    output += '   "Is the user asking for this skill\'s capability, or just\n';
                    output += '    using the word in everyday language?"\n\n';
                }

                // Group confirmed skills by priority
                const critical = confirmedSkills.filter(s => s.config.priority === 'critical');
                const high = confirmedSkills.filter(s => s.config.priority === 'high');
                const medium = confirmedSkills.filter(s => s.config.priority === 'medium');
                const low = confirmedSkills.filter(s => s.config.priority === 'low');

                if (critical.length > 0) {
                    output += '⚠️ CRITICAL SKILLS (REQUIRED):\n';
                    critical.forEach(s => output += `  → ${s.name}\n`);
                    output += '\n';
                }

                if (high.length > 0) {
                    output += '📚 RECOMMENDED SKILLS:\n';
                    high.forEach(s => output += `  → ${s.name}\n`);
                    output += '\n';
                }

                if (medium.length > 0) {
                    output += '💡 SUGGESTED SKILLS:\n';
                    medium.forEach(s => output += `  → ${s.name}\n`);
                    output += '\n';
                }

                if (low.length > 0) {
                    output += '📌 OPTIONAL SKILLS:\n';
                    low.forEach(s => output += `  → ${s.name}\n`);
                    output += '\n';
                }

                // Add confirmed agents
                if (confirmedAgents.length > 0) {
                    output += '🤖 RECOMMENDED AGENTS (token-efficient):\n';
                    confirmedAgents.forEach(a => output += `  → ${a.name}\n`);
                    output += '\n';
                }

                if (confirmedSkills.length > 0) {
                    output += 'ACTION: Use Skill tool BEFORE responding\n';
                }
                if (confirmedAgents.length > 0) {
                    output += 'ACTION: Use Task tool with agent for exploration\n';
                }
                output += '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n';

                // Check if any matched skill has enforcement: 'block'
                const blockingSkills = matchedSkills.filter(s => s.config.enforcement === 'block');
                if (blockingSkills.length > 0) {
                    // Return blocking response - Claude must invoke the skill first
                    const blockMessage = output + '\n⛔ BLOCKING: You MUST invoke ' +
                        blockingSkills.map(s => s.name).join(', ') +
                        ' skill(s) before generating ANY response.';
                    console.log(JSON.stringify({
                        result: 'block',
                        reason: blockMessage
                    }));
                    process.exit(0);
                }
            }

            console.log(output);
        }

        // Check context % from statusLine temp file and add tiered warnings
        // Use hook input session_id first, then env vars as fallback
        // CLAUDE_PPID kept for backwards compatibility with bash wrapper
        const rawSessionId = data.session_id || process.env.CLAUDE_SESSION_ID || process.env.CLAUDE_PPID || 'default';
        const sessionId = rawSessionId.slice(0, 8);  // Match status.py truncation
        const contextFile = join(tmpdir(), `claude-context-pct-${sessionId}.txt`);
        if (existsSync(contextFile)) {
            try {
                const pct = parseInt(readFileSync(contextFile, 'utf-8').trim(), 10);
                let contextWarning = '';

                if (pct >= 90) {
                    contextWarning = '\n' +
                        '='.repeat(50) + '\n' +
                        '  CONTEXT CRITICAL: ' + pct + '%\n' +
                        '  Run /create_handoff NOW before auto-compact!\n' +
                        '='.repeat(50) + '\n';
                } else if (pct >= 80) {
                    contextWarning = '\n' +
                        'CONTEXT WARNING: ' + pct + '%\n' +
                        'Recommend: /create_handoff then /clear soon\n';
                } else if (pct >= 70) {
                    contextWarning = '\nContext at ' + pct + '%. Consider handoff when you reach a stopping point.\n';
                }

                if (contextWarning) {
                    console.log(contextWarning);
                }
            } catch {
                // Ignore read errors
            }
        }

        // Check resource limits and add advisory warnings
        // Phase 5: Soft Limit Advisory
        const resources = readResourceState();
        if (resources && resources.maxAgents > 0) {
            const utilization = resources.activeAgents / resources.maxAgents;
            let resourceWarning = '';

            if (utilization >= 1.0) {
                // At or over limit: CRITICAL
                resourceWarning = '\n' +
                    '='.repeat(50) + '\n' +
                    'RESOURCE CRITICAL: At limit (' + resources.activeAgents + '/' + resources.maxAgents + ' agents)\n' +
                    'Do NOT spawn new agents until existing ones complete.\n' +
                    '='.repeat(50) + '\n';
            } else if (utilization >= 0.8) {
                // Near limit (80%+): WARNING
                const remaining = resources.maxAgents - resources.activeAgents;
                resourceWarning = '\n' +
                    'RESOURCE WARNING: Near limit (' + resources.activeAgents + '/' + resources.maxAgents + ' agents)\n' +
                    'Only ' + remaining + ' agent slot(s) remaining. Limit spawning.\n';
            }

            if (resourceWarning) {
                console.log(resourceWarning);
            }
        }

        outputContinue();
        process.exit(0);
    } catch (err) {
        console.error('Error in skill-activation-prompt hook:', err);
        outputContinue();
        process.exit(1);
    }
}

main().catch(err => {
    console.error('Uncaught error:', err);
    outputContinue();
    process.exit(1);
});
