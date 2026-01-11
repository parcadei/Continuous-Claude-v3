// src/tldr-context-inject.ts
import { readFileSync as readFileSync2, existsSync as existsSync2 } from "fs";
import { join as join2, dirname } from "path";

// src/daemon-client.ts
import { existsSync, readFileSync, writeFileSync, unlinkSync } from "fs";
import { execSync, spawnSync } from "child_process";
import { join, resolve } from "path";
import * as net from "net";
import * as crypto from "crypto";
function resolveProjectDir(projectDir) {
  return resolve(projectDir);
}
function getLockPath(projectDir) {
  const resolvedPath = resolveProjectDir(projectDir);
  const hash = crypto.createHash("md5").update(resolvedPath).digest("hex").substring(0, 8);
  return `/tmp/tldr-${hash}.lock`;
}
function tryAcquireLock(projectDir) {
  const lockPath = getLockPath(projectDir);
  try {
    if (existsSync(lockPath)) {
      const lockContent = readFileSync(lockPath, "utf-8");
      const lockTime = parseInt(lockContent, 10);
      if (!isNaN(lockTime) && Date.now() - lockTime < 3e4) {
        return false;
      }
      try {
        unlinkSync(lockPath);
      } catch {
      }
    }
    writeFileSync(lockPath, Date.now().toString(), { flag: "wx" });
    return true;
  } catch {
    return false;
  }
}
function releaseLock(projectDir) {
  try {
    unlinkSync(getLockPath(projectDir));
  } catch {
  }
}
var QUERY_TIMEOUT = 3e3;
function getConnectionInfo(projectDir) {
  const resolvedPath = resolveProjectDir(projectDir);
  const hash = crypto.createHash("md5").update(resolvedPath).digest("hex").substring(0, 8);
  if (process.platform === "win32") {
    const port = 49152 + parseInt(hash, 16) % 1e4;
    return { type: "tcp", host: "127.0.0.1", port };
  } else {
    return { type: "unix", path: `/tmp/tldr-${hash}.sock` };
  }
}
function getStatusFile(projectDir) {
  const statusPath = join(projectDir, ".tldr", "status");
  if (existsSync(statusPath)) {
    try {
      return readFileSync(statusPath, "utf-8").trim();
    } catch {
      return null;
    }
  }
  return null;
}
function isIndexing(projectDir) {
  return getStatusFile(projectDir) === "indexing";
}
function isDaemonReachable(projectDir) {
  const connInfo = getConnectionInfo(projectDir);
  if (connInfo.type === "tcp") {
    try {
      const testSocket = new net.Socket();
      testSocket.setTimeout(100);
      let connected = false;
      testSocket.on("connect", () => {
        connected = true;
        testSocket.destroy();
      });
      testSocket.on("error", () => {
        testSocket.destroy();
      });
      testSocket.connect(connInfo.port, connInfo.host);
      const end = Date.now() + 200;
      while (Date.now() < end && !connected) {
      }
      return connected;
    } catch {
      return false;
    }
  } else {
    if (!existsSync(connInfo.path)) {
      return false;
    }
    try {
      execSync(`echo '{"cmd":"ping"}' | nc -U "${connInfo.path}"`, {
        encoding: "utf-8",
        timeout: 500,
        stdio: ["pipe", "pipe", "pipe"]
      });
      return true;
    } catch {
      try {
        unlinkSync(connInfo.path);
      } catch {
      }
      return false;
    }
  }
}
function tryStartDaemon(projectDir) {
  try {
    if (isDaemonReachable(projectDir)) {
      return true;
    }
    if (!tryAcquireLock(projectDir)) {
      const start = Date.now();
      while (Date.now() - start < 5e3) {
        if (isDaemonReachable(projectDir)) {
          return true;
        }
        const end = Date.now() + 100;
        while (Date.now() < end) {
        }
      }
      return isDaemonReachable(projectDir);
    }
    try {
      const tldrPath = join(projectDir, "opc", "packages", "tldr-code");
      const result = spawnSync("uv", ["run", "tldr", "daemon", "start", "--project", projectDir], {
        timeout: 1e4,
        stdio: "ignore",
        cwd: tldrPath
      });
      if (result.status !== 0) {
        spawnSync("tldr", ["daemon", "start", "--project", projectDir], {
          timeout: 5e3,
          stdio: "ignore"
        });
      }
      const start = Date.now();
      while (Date.now() - start < 1e4) {
        if (isDaemonReachable(projectDir)) {
          const cooldown = Date.now() + 1e3;
          while (Date.now() < cooldown) {
          }
          return true;
        }
        const end = Date.now() + 100;
        while (Date.now() < end) {
        }
      }
      return isDaemonReachable(projectDir);
    } finally {
      releaseLock(projectDir);
    }
  } catch {
    return false;
  }
}
function queryDaemonSync(query, projectDir) {
  if (isIndexing(projectDir)) {
    return {
      indexing: true,
      status: "indexing",
      message: "Daemon is still indexing, results may be incomplete"
    };
  }
  const connInfo = getConnectionInfo(projectDir);
  if (!isDaemonReachable(projectDir)) {
    if (!tryStartDaemon(projectDir)) {
      return { status: "unavailable", error: "Daemon not running and could not start" };
    }
  }
  try {
    const input = JSON.stringify(query);
    let result;
    if (connInfo.type === "tcp") {
      const psCommand = `
        $client = New-Object System.Net.Sockets.TcpClient('${connInfo.host}', ${connInfo.port})
        $stream = $client.GetStream()
        $writer = New-Object System.IO.StreamWriter($stream)
        $reader = New-Object System.IO.StreamReader($stream)
        $writer.WriteLine('${input.replace(/'/g, "''")}')
        $writer.Flush()
        $response = $reader.ReadLine()
        $client.Close()
        Write-Output $response
      `.trim();
      result = execSync(`powershell -Command "${psCommand.replace(/"/g, '\\"')}"`, {
        encoding: "utf-8",
        timeout: QUERY_TIMEOUT
      });
    } else {
      result = execSync(`echo '${input}' | nc -U "${connInfo.path}"`, {
        encoding: "utf-8",
        timeout: QUERY_TIMEOUT
      });
    }
    return JSON.parse(result.trim());
  } catch (err) {
    if (err.killed) {
      return { status: "error", error: "timeout" };
    }
    if (err.message?.includes("ECONNREFUSED") || err.message?.includes("ENOENT")) {
      return { status: "unavailable", error: "Daemon not running" };
    }
    return { status: "error", error: err.message || "Unknown error" };
  }
}

// src/tldr-context-inject.ts
var INTENT_PATTERNS = [
  {
    // Data flow questions
    patterns: [
      /where\s+does?\s+(\w+)\s+come\s+from/i,
      /what\s+sets?\s+(\w+)/i,
      /who\s+assigns?\s+(\w+)/i,
      /track\s+(?:the\s+)?(?:variable\s+)?(\w+)/i,
      /data\s+flow/i,
      /variable\s+(?:origin|source)/i
    ],
    layers: ["dfg"],
    description: "data flow analysis"
  },
  {
    // Program slicing / dependency questions
    patterns: [
      /what\s+affects?\s+(?:line\s+)?(\d+)/i,
      /what\s+depends?\s+on/i,
      /slice\s+(?:at|from)/i,
      /dependencies?\s+(?:of|for)/i,
      /impact\s+(?:of|analysis)/i
    ],
    layers: ["pdg"],
    description: "program slicing"
  },
  {
    // Complexity / control flow questions
    patterns: [
      /how\s+complex/i,
      /complexity\s+(?:of|for)/i,
      /control\s+flow/i,
      /branch(?:es|ing)/i,
      /cyclomatic/i,
      /paths?\s+through/i
    ],
    layers: ["cfg"],
    description: "control flow analysis"
  },
  {
    // Structure only
    patterns: [
      /list\s+(?:all\s+)?(?:functions?|methods?|classes?)/i,
      /show\s+structure/i,
      /what\s+(?:functions?|methods?)\s+(?:are\s+)?in/i,
      /overview\s+of/i
    ],
    layers: ["ast"],
    description: "structure overview"
  },
  {
    // Debug / investigate (default rich context)
    patterns: [
      /debug/i,
      /investigate/i,
      /fix\s+(?:the\s+)?(?:bug|issue|error)/i,
      /understand/i,
      /how\s+does?\s+(\w+)\s+work/i,
      /explain/i
    ],
    layers: ["call_graph", "cfg"],
    description: "debugging context"
  }
];
var FUNCTION_PATTERNS = [
  /(?:function|method|def|fn)\s+[`"']?(\w+)[`"']?/gi,
  /the\s+[`"']?(\w+)[`"']?\s+(?:function|method)/gi,
  /(?:fix|debug|investigate|look at|check|analyze)\s+[`"']?(\w+(?:\.\w+)?)[`"']?/gi,
  /[`"']?(\w+\.\w+)[`"']?/g,
  /[`"']?([a-z][a-z0-9_]{2,})[`"']?/g
];
var EXCLUDE_WORDS = /* @__PURE__ */ new Set([
  "the",
  "and",
  "for",
  "with",
  "from",
  "this",
  "that",
  "what",
  "how",
  "can",
  "you",
  "fix",
  "debug",
  "investigate",
  "look",
  "check",
  "analyze",
  "function",
  "method",
  "class",
  "file",
  "code",
  "error",
  "bug",
  "issue",
  "please",
  "help",
  "need",
  "want",
  "should",
  "could",
  "would",
  "make",
  "add",
  "remove",
  "update",
  "change",
  "modify",
  "create",
  "delete",
  "test",
  "tests",
  "run",
  "build",
  "install",
  "start",
  "stop",
  "where",
  "does",
  "come",
  "from",
  "affects",
  "line",
  "variable"
]);
function detectIntent(prompt) {
  for (const intent of INTENT_PATTERNS) {
    for (const pattern of intent.patterns) {
      if (pattern.test(prompt)) {
        return { layers: intent.layers, description: intent.description };
      }
    }
  }
  return { layers: ["call_graph"], description: "code navigation" };
}
function detectLanguage(projectPath) {
  const indicators = {
    python: ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
    typescript: ["tsconfig.json", "package.json"],
    rust: ["Cargo.toml"],
    go: ["go.mod", "go.sum"]
  };
  for (const [lang, files] of Object.entries(indicators)) {
    for (const file of files) {
      if (existsSync2(join2(projectPath, file))) {
        return lang;
      }
    }
  }
  return "python";
}
function extractEntryPoints(prompt) {
  const candidates = /* @__PURE__ */ new Set();
  for (const pattern of FUNCTION_PATTERNS) {
    let match;
    while ((match = pattern.exec(prompt)) !== null) {
      const candidate = match[1];
      if (candidate && candidate.length > 2 && !EXCLUDE_WORDS.has(candidate.toLowerCase())) {
        candidates.add(candidate);
      }
    }
  }
  return Array.from(candidates).sort((a, b) => {
    const aHasDot = a.includes(".");
    const bHasDot = b.includes(".");
    if (aHasDot && !bHasDot) return -1;
    if (bHasDot && !aHasDot) return 1;
    return b.length - a.length;
  });
}
function extractLineNumber(prompt) {
  const match = prompt.match(/line\s+(\d+)/i);
  return match ? parseInt(match[1], 10) : null;
}
function extractVariableName(prompt) {
  const patterns = [
    /where\s+does?\s+[`"']?(\w+)[`"']?\s+come\s+from/i,
    /what\s+sets?\s+[`"']?(\w+)[`"']?/i,
    /track\s+(?:the\s+)?(?:variable\s+)?[`"']?(\w+)[`"']?/i
  ];
  for (const pattern of patterns) {
    const match = prompt.match(pattern);
    if (match) return match[1];
  }
  return null;
}
function getTldrContext(projectPath, entryPoint, language, layers, lineNumber, varName) {
  const results = [];
  try {
    for (const layer of layers) {
      switch (layer) {
        case "call_graph": {
          const response = queryDaemonSync(
            { cmd: "context", entry: entryPoint, language, depth: 2 },
            projectPath
          );
          if (response.status === "ok" && response.result) {
            const ctx = response.result;
            const lines = [`## Context: ${entryPoint}`];
            if (ctx.entry_point) {
              lines.push(`\u{1F4CD} ${ctx.entry_point.file}:${ctx.entry_point.line}`);
              if (ctx.entry_point.signature) {
                lines.push(`  ${ctx.entry_point.signature}`);
              }
            }
            if (ctx.callees && ctx.callees.length > 0) {
              lines.push(`
Calls:`);
              for (const c of ctx.callees.slice(0, 10)) {
                lines.push(`  \u2192 ${c.function} (${c.file}:${c.line})`);
              }
            }
            if (ctx.callers && ctx.callers.length > 0) {
              lines.push(`
Called by:`);
              for (const c of ctx.callers.slice(0, 10)) {
                lines.push(`  \u2190 ${c.function} (${c.file}:${c.line})`);
              }
            }
            results.push(lines.join("\n"));
          }
          break;
        }
        case "cfg": {
          const searchResp = queryDaemonSync(
            { cmd: "search", pattern: `def ${entryPoint}` },
            projectPath
          );
          if (searchResp.results && searchResp.results.length > 0) {
            const file = searchResp.results[0].file;
            const cfgResp = queryDaemonSync(
              { cmd: "cfg", file, function: entryPoint, language },
              projectPath
            );
            if (cfgResp.status === "ok" && cfgResp.result) {
              const cfg = cfgResp.result;
              const lines = [`## CFG: ${entryPoint}`];
              lines.push(`Blocks: ${cfg.num_blocks || "N/A"}`);
              lines.push(`Cyclomatic: ${cfg.cyclomatic_complexity || "N/A"}`);
              if (cfg.blocks && Array.isArray(cfg.blocks)) {
                for (const b of cfg.blocks.slice(0, 8)) {
                  lines.push(`  Block ${b.id}: lines ${b.start_line}-${b.end_line} (${b.block_type})`);
                }
              }
              results.push(lines.join("\n"));
            }
          }
          break;
        }
        case "dfg": {
          const funcForDfg = entryPoint.split(".").pop() || entryPoint;
          const searchResp = queryDaemonSync(
            { cmd: "search", pattern: `def ${funcForDfg}` },
            projectPath
          );
          if (searchResp.results && searchResp.results.length > 0) {
            const file = searchResp.results[0].file;
            const dfgResp = queryDaemonSync(
              { cmd: "dfg", file, function: funcForDfg, language },
              projectPath
            );
            if (dfgResp.status === "ok" && dfgResp.result) {
              const dfg = dfgResp.result;
              const varTarget = varName || entryPoint;
              const lines = [`## DFG: ${varTarget} in ${funcForDfg}`];
              if (dfg.definitions && Array.isArray(dfg.definitions)) {
                lines.push("Definitions:");
                for (const d of dfg.definitions.slice(0, 10)) {
                  lines.push(`  ${d.var_name} @ line ${d.line}`);
                }
              }
              if (dfg.uses && Array.isArray(dfg.uses)) {
                lines.push("Uses:");
                for (const u of dfg.uses.slice(0, 8)) {
                  lines.push(`  ${u.var_name} @ line ${u.line}`);
                }
              }
              results.push(lines.join("\n"));
            }
          }
          break;
        }
        case "pdg": {
          const targetLine = lineNumber || 10;
          const searchResp = queryDaemonSync(
            { cmd: "search", pattern: `def ${entryPoint}` },
            projectPath
          );
          if (searchResp.results && searchResp.results.length > 0) {
            const file = searchResp.results[0].file;
            const sliceResp = queryDaemonSync(
              { cmd: "slice", file, function: entryPoint, line: targetLine, direction: "backward" },
              projectPath
            );
            if (sliceResp.status === "ok" && sliceResp.result) {
              const slice = sliceResp.result;
              const lines = [`## PDG Slice: ${entryPoint} @ line ${targetLine}`];
              if (slice.lines && Array.isArray(slice.lines)) {
                lines.push(`Slice lines: ${slice.lines.length}`);
                for (const ln of slice.lines.slice(0, 15)) {
                  lines.push(`  Line ${ln}`);
                }
              }
              if (slice.variables && Array.isArray(slice.variables)) {
                lines.push(`Variables: ${slice.variables.join(", ")}`);
              }
              results.push(lines.join("\n"));
            }
          }
          break;
        }
        case "ast": {
          const structResp = queryDaemonSync(
            { cmd: "structure", language, max_results: 20 },
            projectPath
          );
          if (structResp.status === "ok" && structResp.result) {
            const struct = structResp.result;
            const lines = [`## Structure Overview`];
            if (struct.files && Array.isArray(struct.files)) {
              for (const file of struct.files.slice(0, 10)) {
                lines.push(`
### ${file.path || file.file}`);
                if (file.functions && Array.isArray(file.functions)) {
                  for (const fn of file.functions.slice(0, 8)) {
                    lines.push(`  fn ${fn.name}:${fn.line}`);
                  }
                }
                if (file.classes && Array.isArray(file.classes)) {
                  for (const cls of file.classes.slice(0, 5)) {
                    lines.push(`  class ${cls.name}:${cls.line}`);
                  }
                }
              }
            }
            results.push(lines.join("\n"));
          }
          break;
        }
      }
    }
    return results.length > 0 ? results.join("\n\n") : null;
  } catch {
    return null;
  }
}
function findProjectRoot(startPath) {
  let current = startPath;
  const markers = [".git", "pyproject.toml", "package.json", "Cargo.toml", "go.mod"];
  while (current !== "/") {
    for (const marker of markers) {
      if (existsSync2(join2(current, marker))) {
        return current;
      }
    }
    current = dirname(current);
  }
  return startPath;
}
function readStdin() {
  return readFileSync2(0, "utf-8");
}
async function main() {
  const input = JSON.parse(readStdin());
  if (input.tool_name !== "Task") {
    console.log("{}");
    return;
  }
  const prompt = input.tool_input.prompt || "";
  const description = input.tool_input.description || "";
  const fullText = `${prompt} ${description}`;
  if (prompt.includes("## Code Context:") || prompt.includes("## CFG:") || prompt.includes("## DFG:")) {
    console.log("{}");
    return;
  }
  const { layers, description: intentDesc } = detectIntent(fullText);
  const entryPoints = extractEntryPoints(fullText);
  const lineNumber = extractLineNumber(fullText);
  const varName = extractVariableName(fullText);
  if (entryPoints.length === 0 && !varName && !lineNumber) {
    console.log("{}");
    return;
  }
  const projectRoot = findProjectRoot(input.cwd);
  const language = detectLanguage(projectRoot);
  let tldrContext = null;
  let usedTarget = varName || entryPoints[0] || `line ${lineNumber}`;
  for (const entryPoint of entryPoints.slice(0, 3)) {
    tldrContext = getTldrContext(projectRoot, entryPoint, language, layers, lineNumber, varName);
    if (tldrContext) {
      usedTarget = entryPoint;
      break;
    }
  }
  if (!tldrContext && varName) {
    tldrContext = getTldrContext(projectRoot, varName, language, layers, lineNumber, varName);
  }
  if (!tldrContext) {
    console.log("{}");
    return;
  }
  const enhancedPrompt = `## TLDR Context (${intentDesc}: ${layers.join("+")})

${tldrContext}

---
ORIGINAL TASK:
${prompt}`;
  const output = {
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "allow",
      permissionDecisionReason: `Injected ${layers.join("+")} context for: ${usedTarget}`,
      updatedInput: {
        ...input.tool_input,
        prompt: enhancedPrompt
      }
    }
  };
  console.log(JSON.stringify(output));
}
main().catch((err) => {
  console.error(`TLDR hook error: ${err.message}`);
  console.log("{}");
});
