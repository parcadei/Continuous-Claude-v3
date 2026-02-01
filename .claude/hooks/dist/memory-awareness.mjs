// src/memory-awareness.ts
import { readFileSync, existsSync as existsSync2 } from "fs";
import * as path from "path";
import { spawnSync } from "child_process";

// src/shared/opc-path.ts
import { existsSync } from "fs";
import { join } from "path";
function getOpcDir() {
  const envOpcDir = process.env.CLAUDE_OPC_DIR;
  if (envOpcDir && existsSync(envOpcDir)) {
    return envOpcDir;
  }
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const localOpc = join(projectDir, "opc");
  if (existsSync(localOpc)) {
    return localOpc;
  }
  const homeDir = process.env.HOME || process.env.USERPROFILE || "";
  if (homeDir) {
    const globalClaude = join(homeDir, ".claude");
    const globalScripts = join(globalClaude, "scripts", "core");
    if (existsSync(globalScripts) && globalClaude !== projectDir) {
      return globalClaude;
    }
  }
  return null;
}

// src/shared/output.ts
function outputContinue() {
  console.log(JSON.stringify({ result: "continue" }));
}

// src/memory-awareness.ts
function readStdin() {
  return readFileSync(0, "utf-8");
}
function isInfrastructureDir(projectDir) {
  const homeDir = process.env.HOME || process.env.USERPROFILE || "";
  if (!homeDir) return false;
  const claudeDir = homeDir.replace(/\\/g, "/") + "/.claude";
  const normalizedProject = (projectDir || "").replace(/\\/g, "/");
  return normalizedProject === claudeDir || normalizedProject.endsWith("/.claude");
}
function extractIntent(prompt) {
  const metaPhrases = [
    /^(can you|could you|would you|please|help me|i want to|i need to|let's|lets)\s+/gi,
    /^(show me|tell me|find|search for|look for|recall|remember)\s+/gi,
    /^(how do i|how can i|how to|what is|what are|where is|where are)\s+/gi,
    /\s+(for me|please|thanks|thank you)$/gi,
    /\?$/g
  ];
  let intent = prompt.trim();
  for (const pattern of metaPhrases) {
    intent = intent.replace(pattern, "");
  }
  intent = intent.trim();
  if (intent.length < 5) {
    return extractKeywords(prompt);
  }
  return intent;
}
function extractKeywords(prompt) {
  const stopWords = /* @__PURE__ */ new Set([
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "must",
    "can",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "at",
    "by",
    "from",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "under",
    "again",
    "further",
    "then",
    "once",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "all",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "s",
    "t",
    "just",
    "don",
    "now",
    "i",
    "me",
    "my",
    "you",
    "your",
    "we",
    "help",
    "with",
    "our",
    "they",
    "them",
    "their",
    "it",
    "its",
    "this",
    "that",
    "these",
    "what",
    "which",
    "who",
    "whom",
    "and",
    "but",
    "if",
    "or",
    "because",
    "until",
    "while",
    "about",
    "against",
    "also",
    "get",
    "got",
    "make",
    "want",
    "need",
    "look",
    "see",
    "use",
    "like",
    "know",
    "think",
    "take",
    "come",
    "go",
    "say",
    "said",
    "tell",
    "please",
    "help",
    "let",
    "sure",
    "recall",
    "remember",
    "similar",
    "problems",
    "issues"
  ]);
  const words = prompt.toLowerCase().replace(/[^\w\s-]/g, " ").split(/\s+/).filter((w) => w.length > 2 && !stopWords.has(w));
  return [...new Set(words)].slice(0, 5).join(" ");
}
function checkLocalMemory(intent, projectDir) {
  const homeDir = process.env.HOME || process.env.USERPROFILE || "";
  const projectMemoryScript = path.join(homeDir, ".claude", "scripts", "core", "core", "project_memory.py");
  if (!existsSync2(projectMemoryScript)) return null;
  try {
    const result = spawnSync("uv", [
      "run",
      "python",
      projectMemoryScript,
      "query",
      intent,
      "--project-dir",
      projectDir,
      "-k",
      "3",
      "--json"
    ], {
      encoding: "utf-8",
      cwd: path.join(homeDir, ".claude", "scripts", "core", "core"),
      timeout: 2e3,
      killSignal: "SIGKILL"
    });
    if (result.status !== 0 || !result.stdout) return null;
    const data = JSON.parse(result.stdout);
    if (!data.results || data.results.length === 0) return null;
    const results = data.results.slice(0, 3).map((r) => ({
      id: r.task_id || r.id || "local",
      type: "LOCAL_HANDOFF",
      content: r.summary || r.content || "",
      score: r.similarity || 0.5
    }));
    return { count: data.count || results.length, results };
  } catch {
    return null;
  }
}
function checkMemoryRelevance(intent, projectDir) {
  if (!intent || intent.length < 3) return null;
  const localMatch = checkLocalMemory(intent, projectDir);
  if (localMatch) {
    return localMatch;
  }
  const opcDir = getOpcDir();
  if (!opcDir) return null;
  const searchTerm = intent.replace(/[_\/]/g, " ").replace(/\b\w{1,2}\b/g, "").replace(/\s+/g, " ").trim();
  const result = spawnSync("uv", [
    "run",
    "python",
    "scripts/core/recall_learnings.py",
    "--query",
    searchTerm,
    "--k",
    "3",
    "--json",
    "--text-only"
  ], {
    encoding: "utf-8",
    cwd: opcDir,
    env: {
      ...process.env,
      PYTHONPATH: opcDir
    },
    timeout: 2e3,
    killSignal: "SIGKILL"
  });
  if (result.status !== 0 || !result.stdout) {
    return null;
  }
  try {
    const data = JSON.parse(result.stdout);
    if (!data.results || data.results.length === 0) {
      return null;
    }
    const results = data.results.slice(0, 3).map((r) => {
      const content = r.content || "";
      const preview = content.split("\n").filter((l) => l.trim().length > 0).map((l) => l.trim()).join(" ").slice(0, 120);
      return {
        id: (r.id || "unknown").slice(0, 8),
        type: r.learning_type || r.type || "UNKNOWN",
        content: preview + (content.length > 120 ? "..." : ""),
        score: r.score || 0
      };
    });
    return {
      count: data.results.length,
      results
    };
  } catch {
    return null;
  }
}
async function main() {
  const input = JSON.parse(readStdin());
  const projectDir = process.env.CLAUDE_PROJECT_DIR || input.cwd;
  if (isInfrastructureDir(projectDir)) {
    outputContinue();
    return;
  }
  if (process.env.CLAUDE_AGENT_ID) {
    outputContinue();
    return;
  }
  if (input.prompt.length < 15) {
    outputContinue();
    return;
  }
  if (input.prompt.trim().startsWith("/")) {
    outputContinue();
    return;
  }
  const intent = extractIntent(input.prompt);
  if (intent.length < 3) {
    outputContinue();
    return;
  }
  const match = checkMemoryRelevance(intent, projectDir);
  if (match) {
    const resultLines = match.results.map(
      (r, i) => `${i + 1}. [${r.type}] ${r.content} (id: ${r.id})`
    ).join("\n");
    const claudeContext = `MEMORY MATCH (${match.count} results) for "${intent}":
${resultLines}
Use /recall "${intent}" for full content. Disclose if helpful.`;
    console.log(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "UserPromptSubmit",
        additionalContext: claudeContext
      }
    }));
  } else {
    outputContinue();
  }
}
main().catch(() => {
  outputContinue();
});
