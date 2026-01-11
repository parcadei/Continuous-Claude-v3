// src/tldr-read-enforcer.ts
import { readFileSync as readFileSync2, existsSync as existsSync2, statSync } from "fs";
import { basename, extname } from "path";

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
function trackHookActivitySync(hookName, projectDir, success = true, metrics = {}) {
  try {
    queryDaemonSync(
      { cmd: "track", hook: hookName, success, metrics },
      projectDir
    );
  } catch {
  }
}

// src/tldr-read-enforcer.ts
var CONTEXT_DIR = "/tmp/claude-search-context";
var CONTEXT_MAX_AGE_MS = 3e4;
function getSearchContext(sessionId) {
  try {
    const contextPath = `${CONTEXT_DIR}/${sessionId}.json`;
    if (!existsSync2(contextPath)) return null;
    const context = JSON.parse(readFileSync2(contextPath, "utf-8"));
    if (Date.now() - context.timestamp > CONTEXT_MAX_AGE_MS) {
      return null;
    }
    return context;
  } catch {
    return null;
  }
}
function analyzeTranscript(transcriptPath) {
  try {
    if (!existsSync2(transcriptPath)) return null;
    const content = readFileSync2(transcriptPath, "utf-8");
    const lines = content.trim().split("\n").slice(-20);
    let recentText = "";
    for (const line of lines) {
      try {
        const msg = JSON.parse(line);
        if (msg.type === "human" || msg.type === "assistant") {
          const text = typeof msg.message === "string" ? msg.message : JSON.stringify(msg.message);
          recentText += " " + text;
        }
      } catch {
      }
    }
    recentText = recentText.toLowerCase();
    const intentPatterns = [
      {
        patterns: [/debug/, /bug/, /fix\s+(the|this|a)?\s*(error|issue|problem)/, /investigate/, /broken/],
        layers: ["ast", "call_graph", "cfg"],
        name: "debugging"
      },
      {
        patterns: [/where\s+does/, /data\s*flow/, /variable/, /track\s+\w+/, /what\s+sets/],
        layers: ["ast", "dfg"],
        name: "data-flow"
      },
      {
        patterns: [/complexity/, /how\s+complex/, /refactor/, /simplify/, /control\s+flow/],
        layers: ["ast", "call_graph", "cfg"],
        name: "complexity"
      },
      {
        patterns: [/what\s+depends/, /impact/, /affects/, /slice/],
        layers: ["ast", "call_graph", "pdg"],
        name: "dependencies"
      },
      {
        patterns: [/understand/, /how\s+does.*work/, /explain/],
        layers: ["ast", "call_graph", "cfg"],
        name: "understanding"
      }
    ];
    for (const intent of intentPatterns) {
      if (intent.patterns.some((p) => p.test(recentText))) {
        const funcMatch = recentText.match(/(?:function|method|def|class)\s+(\w+)/);
        const target = funcMatch ? funcMatch[1] : null;
        return {
          layers: intent.layers,
          target,
          source: `transcript:${intent.name}`
        };
      }
    }
    return null;
  } catch {
    return null;
  }
}
var CODE_EXTENSIONS = /* @__PURE__ */ new Set([
  ".py",
  ".ts",
  ".tsx",
  ".js",
  ".jsx",
  ".go",
  ".rs"
]);
var ALLOWED_PATTERNS = [
  /\.json$/,
  /\.yaml$/,
  /\.yml$/,
  /\.toml$/,
  /\.md$/,
  /\.txt$/,
  /\.env/,
  /\.gitignore$/,
  /Makefile$/,
  /Dockerfile$/,
  /requirements\.txt$/,
  /package\.json$/,
  /tsconfig\.json$/,
  /pyproject\.toml$/,
  // Allow test files (need full context for implementation)
  /test_.*\.py$/,
  /.*_test\.py$/,
  /.*\.test\.(ts|js)$/,
  /.*\.spec\.(ts|js)$/,
  // Allow hooks/skills (we edit these)
  /\.claude\/hooks\//,
  /\.claude\/skills\//,
  /init-db\.sql$/,
  /migrations\//
];
var ALLOWED_DIRS = ["/tmp/", "node_modules/", ".venv/", "__pycache__/"];
function isCodeFile(filePath) {
  return CODE_EXTENSIONS.has(extname(filePath));
}
function isAllowedFile(filePath) {
  for (const pattern of ALLOWED_PATTERNS) {
    if (pattern.test(filePath)) return true;
  }
  for (const dir of ALLOWED_DIRS) {
    if (filePath.includes(dir)) return true;
  }
  return false;
}
function detectLanguage(filePath) {
  const ext = extname(filePath);
  const langMap = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust"
  };
  return langMap[ext] || "python";
}
function getTldrContext(filePath, language, layers = ["ast", "call_graph"], target = null, sessionId = null) {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const fileName = basename(filePath);
  const results = [];
  try {
    results.push(`# ${fileName}`);
    results.push(`Language: ${language}`);
    results.push("");
    if (layers.includes("ast") || layers.includes("call_graph")) {
      const extractResp = queryDaemonSync(
        { cmd: "extract", file: filePath, session: sessionId || void 0 },
        projectDir
      );
      if (extractResp.status === "ok" && extractResp.result) {
        const info = extractResp.result;
        if (info.functions && info.functions.length > 0) {
          results.push("## Functions");
          for (const fn of info.functions) {
            const params = fn.params ? fn.params.join(", ") : "";
            const ret = fn.return_type ? ` -> ${fn.return_type}` : "";
            results.push(`  ${fn.name}(${params})${ret}  [line ${fn.line_number || fn.line}]`);
            if (fn.docstring) {
              const doc = fn.docstring.substring(0, 100).replace(/\n/g, " ");
              results.push(`    # ${doc}`);
            }
          }
        }
        if (info.classes && info.classes.length > 0) {
          results.push("");
          results.push("## Classes");
          for (const cls of info.classes) {
            results.push(`  class ${cls.name}  [line ${cls.line_number || cls.line}]`);
            if (cls.methods) {
              for (const m of cls.methods.slice(0, 10)) {
                results.push(`    .${m.name}()`);
              }
            }
          }
        }
        if (layers.includes("call_graph") && info.call_graph && info.call_graph.calls) {
          results.push("");
          results.push("## Call Graph");
          const entries = Object.entries(info.call_graph.calls).slice(0, 15);
          for (const [caller, callees] of entries) {
            results.push(`  ${caller} -> ${callees}`);
          }
        }
      }
    }
    if (layers.includes("cfg")) {
      const funcName = target || "main";
      const cfgResp = queryDaemonSync(
        { cmd: "cfg", file: filePath, function: funcName, language },
        projectDir
      );
      if (cfgResp.status === "ok" && cfgResp.result) {
        const cfg = cfgResp.result;
        results.push("");
        results.push(`## CFG: ${funcName}`);
        results.push(`  Blocks: ${cfg.num_blocks || "N/A"}, Cyclomatic: ${cfg.cyclomatic_complexity || "N/A"}`);
        if (cfg.blocks && Array.isArray(cfg.blocks)) {
          for (const b of cfg.blocks.slice(0, 8)) {
            results.push(`    Block ${b.id}: lines ${b.start_line}-${b.end_line} (${b.block_type})`);
          }
        }
      }
    }
    if (layers.includes("dfg")) {
      const funcName = target || "main";
      const dfgResp = queryDaemonSync(
        { cmd: "dfg", file: filePath, function: funcName, language },
        projectDir
      );
      if (dfgResp.status === "ok" && dfgResp.result) {
        const dfg = dfgResp.result;
        results.push("");
        results.push(`## DFG: ${funcName}`);
        if (dfg.definitions && dfg.definitions.length > 0) {
          results.push("  Definitions:");
          for (const d of dfg.definitions.slice(0, 10)) {
            results.push(`    ${d.var_name} @ line ${d.line}`);
          }
        }
        if (dfg.uses && dfg.uses.length > 0) {
          results.push("  Uses:");
          for (const u of dfg.uses.slice(0, 8)) {
            results.push(`    ${u.var_name} @ line ${u.line}`);
          }
        }
      }
    }
    if (layers.includes("pdg")) {
      const funcName = target || "main";
      const sliceResp = queryDaemonSync(
        { cmd: "slice", file: filePath, function: funcName, line: 10, direction: "backward" },
        projectDir
      );
      if (sliceResp.status === "ok" && sliceResp.result) {
        const slice = sliceResp.result;
        results.push("");
        results.push(`## PDG: ${funcName}`);
        if (slice.lines && slice.lines.length > 0) {
          results.push(`  Slice lines: ${slice.lines.length}`);
        }
        if (slice.variables && slice.variables.length > 0) {
          results.push(`  Variables: ${slice.variables.join(", ")}`);
        }
      }
    }
    return results.length > 3 ? results.join("\n") : null;
  } catch {
    return null;
  }
}
function readStdin() {
  return readFileSync2(0, "utf-8");
}
async function main() {
  const input = JSON.parse(readStdin());
  if (input.tool_name !== "Read") {
    console.log("{}");
    return;
  }
  const filePath = input.tool_input.file_path || "";
  if (!isCodeFile(filePath)) {
    console.log("{}");
    return;
  }
  if (isAllowedFile(filePath)) {
    console.log("{}");
    return;
  }
  if (input.tool_input.offset || input.tool_input.limit && input.tool_input.limit < 100) {
    console.log("{}");
    return;
  }
  try {
    const stats = statSync(filePath);
    if (stats.size < 3e3) {
      console.log("{}");
      return;
    }
  } catch {
    console.log("{}");
    return;
  }
  const language = detectLanguage(filePath);
  let layers = ["ast", "call_graph"];
  let target = null;
  let contextSource = "default";
  const searchContext = getSearchContext(input.session_id);
  if (searchContext) {
    layers = searchContext.suggestedLayers;
    target = searchContext.target;
    contextSource = `${searchContext.targetType}: ${searchContext.target}`;
  } else if (input.transcript_path) {
    const transcriptIntent = analyzeTranscript(input.transcript_path);
    if (transcriptIntent) {
      layers = transcriptIntent.layers;
      target = transcriptIntent.target;
      contextSource = transcriptIntent.source;
    }
  }
  const tldrContext = getTldrContext(filePath, language, layers, target, input.session_id);
  if (!tldrContext) {
    console.log("{}");
    return;
  }
  const layerNames = layers.map((l) => {
    switch (l) {
      case "ast":
        return "L1:AST";
      case "call_graph":
        return "L2:CallGraph";
      case "cfg":
        return "L3:CFG";
      case "dfg":
        return "L4:DFG";
      case "pdg":
        return "L5:PDG";
      default:
        return l;
    }
  }).join(" + ");
  let crossFileSection = "";
  if (searchContext?.callers && searchContext.callers.length > 0) {
    const callerLines = searchContext.callers.slice(0, 10).map((c) => {
      const parts = c.split("/");
      const fileAndLine = parts[parts.length - 1];
      const dir = parts.length > 2 ? parts[parts.length - 2] : "";
      return `  ${dir ? dir + "/" : ""}${fileAndLine}`;
    });
    crossFileSection = `
## Cross-File Usage (${searchContext.callers.length} refs)
${callerLines.join("\n")}${searchContext.callers.length > 10 ? `
  ... and ${searchContext.callers.length - 10} more` : ""}
`;
  }
  let definitionSection = "";
  if (searchContext?.definitionLocation && !searchContext.definitionLocation.includes(basename(filePath))) {
    definitionSection = `
\u{1F4CD} Defined at: ${searchContext.definitionLocation}
`;
  }
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  trackHookActivitySync("tldr-read-enforcer", projectDir, true, {
    reads_intercepted: 1,
    layers_returned: layers.length
  });
  const output = {
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: `\u{1F4CA} TLDR Context (${layerNames}) - 95% token savings:
${searchContext ? `\u{1F517} Context: ${contextSource}` : ""}${definitionSection}

${tldrContext}${crossFileSection}
---
To read specific lines, use: Read with offset/limit
To read full file anyway, use: Read ${basename(filePath)} (test files bypass this)`
    }
  };
  console.log(JSON.stringify(output));
}
main().catch((err) => {
  console.error(`TLDR enforcer error: ${err.message}`);
  console.log("{}");
});
