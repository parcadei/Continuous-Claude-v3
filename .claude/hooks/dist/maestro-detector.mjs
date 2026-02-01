#!/usr/bin/env node

// src/maestro-detector.ts
import { readFileSync } from "fs";

// src/shared/output.ts
function outputContinue() {
  console.log(JSON.stringify({ result: "continue" }));
}

// src/maestro-detector.ts
var COMPLEXITY_SIGNALS = [
  // Multi-task indicators
  { name: "conjunction", pattern: /\b(and then|and also|plus|as well as)\b/i, weight: 0.25 },
  { name: "sequence", pattern: /\b(first|then|after that|finally|next)\b/i, weight: 0.2 },
  { name: "list_numbered", pattern: /\d+\.\s+\w/g, weight: 0.15, global: true },
  { name: "list_bulleted", pattern: /^[\-\*]\s+\w/gm, weight: 0.15, global: true },
  // Scope indicators
  { name: "system_scope", pattern: /\b(system|architecture|full|complete|entire|whole)\b/i, weight: 0.2 },
  { name: "feature_scope", pattern: /\b(feature|module|component|service)\b/i, weight: 0.15 },
  // Process keywords (multiple phases)
  { name: "research", pattern: /\b(research|explore|understand|investigate|analyze)\b/i, weight: 0.15 },
  { name: "planning", pattern: /\b(plan|design|architect|strategy|approach)\b/i, weight: 0.15 },
  { name: "implementation", pattern: /\b(build|create|implement|develop|add)\b/i, weight: 0.15 },
  { name: "testing", pattern: /\b(test|validate|verify|check)\b/i, weight: 0.1 },
  { name: "review", pattern: /\b(review|audit|assess)\b/i, weight: 0.1 },
  // Complexity indicators
  { name: "complexity_explicit", pattern: /\b(complex|complicated|sophisticated|comprehensive)\b/i, weight: 0.25 },
  { name: "multiplicity", pattern: /\b(multiple|several|various|many)\b/i, weight: 0.2 },
  { name: "integration", pattern: /\b(integrate|coordinate|orchestrate|combine)\b/i, weight: 0.25 },
  // Cross-cutting concerns
  { name: "cross_cutting", pattern: /\b(across|throughout|all|every)\s+(the\s+)?(codebase|project|system|modules?)/i, weight: 0.2 }
];
var COMPLEXITY_THRESHOLD = 0.65;
function readStdin() {
  return readFileSync(0, "utf-8");
}
function analyzeComplexity(prompt) {
  const detected = [];
  let totalScore = 0;
  for (const signal of COMPLEXITY_SIGNALS) {
    if (signal.global) {
      const matches = prompt.match(signal.pattern);
      if (matches && matches.length > 0) {
        const weight = Math.min(signal.weight * matches.length, signal.weight * 3);
        detected.push({ name: signal.name, weight, matches: matches.length });
        totalScore += weight;
      }
    } else {
      if (signal.pattern.test(prompt)) {
        detected.push({ name: signal.name, weight: signal.weight, matches: 1 });
        totalScore += signal.weight;
      }
    }
  }
  return { score: Math.min(totalScore, 1.5), signals: detected };
}
function countProcessPhases(prompt) {
  const phases = [
    /\b(research|explore|understand|investigate)\b/i,
    /\b(plan|design|architect)\b/i,
    /\b(build|create|implement|develop)\b/i,
    /\b(test|validate|verify)\b/i,
    /\b(review|audit|deploy)\b/i
  ];
  return phases.filter((p) => p.test(prompt)).length;
}
function formatSignals(signals) {
  const top = signals.sort((a, b) => b.weight - a.weight).slice(0, 4).map((s) => `  - ${s.name.replace(/_/g, " ")} (+${(s.weight * 100).toFixed(0)}%)`).join("\n");
  return top;
}
function makeSuggestionOutput(score, signals, phases) {
  const confidencePct = Math.round(score * 100);
  const message = `
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u{1F3BC} MAESTRO ORCHESTRATION SUGGESTED
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

This looks like a complex multi-step task (${confidencePct}% confidence).

**Detected signals:**
${formatSignals(signals)}

**Estimated phases:** ${phases}

**Recommended approach:**
1. Use Maestro orchestrator for coordination
2. Discovery interview for thorough requirements
3. Delegate to specialized agents

**To proceed with Maestro:**
Say "Yes, use Maestro" or "orchestrate this"

**To skip:**
Continue with your request normally.
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
`;
  console.log(message);
}
async function main() {
  try {
    const rawInput = readStdin();
    if (!rawInput.trim()) {
      outputContinue();
      return;
    }
    let input;
    try {
      input = JSON.parse(rawInput);
    } catch {
      outputContinue();
      return;
    }
    if (!input.prompt || typeof input.prompt !== "string") {
      outputContinue();
      return;
    }
    const prompt = input.prompt;
    if (prompt.length < 50) {
      outputContinue();
      return;
    }
    if (/\b(maestro|orchestrat)/i.test(prompt)) {
      outputContinue();
      return;
    }
    if (/^(what|how|why|where|when|can you|could you|is there)\s/i.test(prompt) && prompt.length < 100) {
      outputContinue();
      return;
    }
    const { score, signals } = analyzeComplexity(prompt);
    const phases = countProcessPhases(prompt);
    const adjustedScore = phases >= 3 ? score + 0.15 : score;
    if (adjustedScore >= COMPLEXITY_THRESHOLD && signals.length >= 2) {
      makeSuggestionOutput(adjustedScore, signals, Math.max(phases, 2));
    } else {
      outputContinue();
    }
  } catch (err) {
    outputContinue();
  }
}
main();
