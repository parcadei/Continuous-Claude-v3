#!/usr/bin/env node
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { execSync } from 'child_process';

// Import shared resource reader (Phase 4 module)
import { readResourceState, ResourceState } from './shared/resource-reader.js';

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

interface PromptTriggers {
    keywords?: string[];
    intentPatterns?: string[];
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
 */
function runPatternInference(prompt: string, projectDir: string): PatternInference | null {
    try {
        const scriptPath = join(projectDir, 'scripts', 'agentica', 'pattern_inference.py');
        if (!existsSync(scriptPath)) {
            return null;
        }

        // Escape prompt for shell
        const escapedPrompt = prompt.replace(/'/g, "'\\''");

        // Run the Python module with uv
        const result = execSync(
            `cd "${projectDir}" && uv run python -c "
import sys
sys.path.insert(0, '.')
from scripts.agentica.pattern_inference import infer_pattern, generate_work_breakdown
import json
prompt = '''${escapedPrompt}'''
result = infer_pattern(prompt)
output = result.to_dict()
output['work_breakdown_detailed'] = generate_work_breakdown(result)
print(json.dumps(output))
"`,
            {
                encoding: 'utf-8',
                timeout: 5000,  // 5 second timeout
                stdio: ['pipe', 'pipe', 'pipe'],
            }
        );

        return JSON.parse(result.trim()) as PatternInference;
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
        // High confidence - auto-select pattern, show work breakdown
        output += 'WORK BREAKDOWN:\n';
        output += `  ${inference.work_breakdown_detailed}\n`;
        output += '\n';
        output += `Confidence: ${Math.round(inference.confidence * 100)}%\n`;
        if (inference.signals.length > 0) {
            output += `Signals detected: ${inference.signals.join(', ')}\n`;
        }
        output += '\n';
        output += 'ACTION: Proceed with this approach. Use Task tool to spawn agents.\n';
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
        output += `Confidence: ${Math.round(inference.confidence * 100)}%\n`;
        output += '\n';
        output += 'ACTION: Use AskUserQuestion to clarify before proceeding.\n';
    }

    output += '='.repeat(50) + '\n';
    return output;
}

async function main() {
    try {
        // Read input from stdin
        const input = readFileSync(0, 'utf-8');
        const data: HookInput = JSON.parse(input);
        const prompt = data.prompt.toLowerCase();

        // Load skill rules (try project first, then global)
        const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
        const homeDir = process.env.HOME || '';
        const projectRulesPath = join(projectDir, '.claude', 'skills', 'skill-rules.json');
        const globalRulesPath = join(homeDir, '.claude', 'skills', 'skill-rules.json');

        let rulesPath = '';
        if (existsSync(projectRulesPath)) {
            rulesPath = projectRulesPath;
        } else if (existsSync(globalRulesPath)) {
            rulesPath = globalRulesPath;
        } else {
            // No rules file found, exit silently
            process.exit(0);
        }
        const rules: SkillRules = JSON.parse(readFileSync(rulesPath, 'utf-8'));

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

        // Generate output if matches found
        if (matchedSkills.length > 0 || matchedAgents.length > 0) {
            // Check which skills need LLM validation (potential false positives)
            const skillsNeedingValidation = matchedSkills.filter(s => s.needsValidation);
            const agentsNeedingValidation = matchedAgents.filter(a => a.needsValidation);
            const allNeedingValidation = [...skillsNeedingValidation, ...agentsNeedingValidation];

            // Filter out skills that need validation from the main lists
            // (they will be shown in a separate section)
            const confirmedSkills = matchedSkills.filter(s => !s.needsValidation);
            const confirmedAgents = matchedAgents.filter(a => !a.needsValidation);

            let output = '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n';
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

            // Special handling for agentica-orchestrator with pattern inference
            if (matchedAgents.some(a => a.name === 'agentica-orchestrator')) {
                // Try pattern inference first (inference-first approach)
                const inference = runPatternInference(data.prompt, projectDir);

                if (inference) {
                    // Pattern inference succeeded - use it
                    output += generateAgenticaOutput(inference, data.prompt);
                } else {
                    // Fallback to manual pattern selection if inference fails
                    output += '\n';
                    output += '='.repeat(50) + '\n';
                    output += 'AGENTICA ORCHESTRATION ACTIVATED\n';
                    output += '='.repeat(50) + '\n';
                    output += '\n';
                    output += 'Pattern inference unavailable. Manual selection:\n';
                    output += '\n';
                    output += 'Use AskUserQuestion to gather information:\n';
                    output += '1. Ask user to describe their task in detail\n';
                    output += '2. Ask which approach fits best:\n';
                    output += '   - Research/Explore (Swarm pattern)\n';
                    output += '   - Build/Implement (Hierarchical pattern)\n';
                    output += '   - Iterate/Refine (Generator/Critic pattern)\n';
                    output += '   - Validate/Verify (Jury pattern)\n';
                    output += '\n';
                    output += 'After user selects, spawn appropriate pattern with:\n';
                    output += '  SWARM_ID=<uuid> environment variable\n';
                    output += '='.repeat(50) + '\n';
                }
            }

            console.log(output);
        }

        // Check context % from statusLine temp file and add tiered warnings
        // CLAUDE_PPID is passed from shell wrapper (matches status.sh's $PPID)
        // This ensures we read the same file that StatusLine wrote
        const sessionId = process.env.CLAUDE_SESSION_ID || process.env.CLAUDE_PPID || 'default';
        const contextFile = `/tmp/claude-context-pct-${sessionId}.txt`;
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

        process.exit(0);
    } catch (err) {
        console.error('Error in skill-activation-prompt hook:', err);
        process.exit(1);
    }
}

main().catch(err => {
    console.error('Uncaught error:', err);
    process.exit(1);
});
