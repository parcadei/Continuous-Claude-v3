// src/navigator-safety.ts
import { readFileSync } from "fs";

// src/shared/pageindex-client.ts
var CACHE_TTL_MS = 5 * 60 * 1e3;

// src/shared/output.ts
function outputContinue() {
  console.log(JSON.stringify({ result: "continue" }));
}

// src/navigator-safety.ts
var DESTRUCTIVE_PATTERNS = [
  {
    pattern: /^git\s+(reset\s+--hard|checkout\s+\.|clean\s+-f)/i,
    category: "Git (destructive)",
    ruleQuery: "git destructive commands confirmation",
    ruleText: "Per destructive-commands.md: Ask user before git reset/checkout/clean"
  },
  {
    pattern: /^git\s+push\s+(-f|--force)/i,
    category: "Git (force push)",
    ruleQuery: "git force push dangerous",
    ruleText: "Per destructive-commands.md: NEVER force push to shared branches without explicit confirmation"
  },
  {
    pattern: /^git\s+(checkout|stash|rebase|merge|push|commit)(?:\s|$)/i,
    category: "Git (state-modifying)",
    ruleQuery: "git confirmation state modify",
    ruleText: "Per destructive-commands.md: State-modifying git commands require confirmation"
  },
  {
    pattern: /\brm\s+/i,
    category: "File deletion",
    ruleQuery: "file deletion rm confirmation",
    ruleText: "Per destructive-commands.md: Ask before running rm (any form)"
  },
  {
    pattern: /\brmdir\b/i,
    category: "Directory deletion",
    ruleQuery: "directory deletion confirmation",
    ruleText: "Per destructive-commands.md: Ask before removing directories"
  },
  {
    pattern: /\b(DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE|DELETE\s+FROM)\b/i,
    category: "Database (destructive)",
    ruleQuery: "database destructive operations",
    ruleText: "Database destructive operations require explicit confirmation"
  }
];
function readStdin() {
  return readFileSync(0, "utf-8");
}
function checkDestructivePatterns(command) {
  const matches = [];
  for (const { pattern, category, ruleText } of DESTRUCTIVE_PATTERNS) {
    if (pattern.test(command)) {
      matches.push({ category, ruleText });
    }
  }
  return {
    isDestructive: matches.length > 0,
    categories: matches.map((m) => m.category),
    ruleTexts: matches.map((m) => m.ruleText)
  };
}
function buildSafetyWarning(command, categories, ruleTexts) {
  const lines = [];
  lines.push("NAVIGATOR SAFETY ALERT");
  lines.push("");
  lines.push(`Command: ${command.slice(0, 100)}${command.length > 100 ? "..." : ""}`);
  lines.push(`Pattern: ${categories.join(", ")}`);
  lines.push("");
  lines.push("Relevant Rules:");
  for (const ruleText of ruleTexts) {
    lines.push(`  - ${ruleText}`);
  }
  lines.push("");
  lines.push("Ensure user has confirmed this operation.");
  return lines.join("\n");
}
async function main() {
  const input = JSON.parse(readStdin());
  if (input.tool_name !== "Bash") {
    outputContinue();
    return;
  }
  const command = input.tool_input.command;
  if (!command) {
    outputContinue();
    return;
  }
  const { isDestructive, categories, ruleTexts } = checkDestructivePatterns(command);
  if (!isDestructive) {
    outputContinue();
    return;
  }
  const warning = buildSafetyWarning(command, categories, ruleTexts);
  const output = {
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "allow",
      permissionDecisionReason: warning
    }
  };
  console.log(JSON.stringify(output));
}
main().catch(() => {
  outputContinue();
});
