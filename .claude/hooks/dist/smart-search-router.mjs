var __require = /* @__PURE__ */ ((x) => typeof require !== "undefined" ? require : typeof Proxy !== "undefined" ? new Proxy(x, {
  get: (a, b) => (typeof require !== "undefined" ? require : a)[b]
}) : x)(function(x) {
  if (typeof require !== "undefined") return require.apply(this, arguments);
  throw Error('Dynamic require of "' + x + '" is not supported');
});

// src/smart-search-router.ts
import { existsSync as existsSync2, mkdirSync, writeFileSync } from "fs";
import { execSync as execSync2 } from "child_process";

// src/daemon-client.ts
import { existsSync, readFileSync } from "fs";
import { execSync, spawnSync } from "child_process";
import { join } from "path";
import * as net from "net";
import * as crypto from "crypto";
var QUERY_TIMEOUT = 3e3;
function getConnectionInfo(projectDir) {
  const hash = crypto.createHash("md5").update(projectDir).digest("hex").substring(0, 8);
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
        const { unlinkSync } = __require("fs");
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
    while (Date.now() - start < 2e3) {
      if (isDaemonReachable(projectDir)) {
        return true;
      }
      const end = Date.now() + 50;
      while (Date.now() < end) {
      }
    }
    return isDaemonReachable(projectDir);
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

// src/smart-search-router.ts
var CONTEXT_DIR = "/tmp/claude-search-context";
function storeSearchContext(sessionId, context) {
  try {
    if (!existsSync2(CONTEXT_DIR)) {
      mkdirSync(CONTEXT_DIR, { recursive: true });
    }
    writeFileSync(
      `${CONTEXT_DIR}/${sessionId}.json`,
      JSON.stringify(context, null, 2)
    );
  } catch {
  }
}
function tldrSearch(pattern, projectDir = ".") {
  try {
    const response = queryDaemonSync({ cmd: "search", pattern }, projectDir);
    if (response.indexing || response.status === "unavailable") {
      return ripgrepFallback(pattern, projectDir);
    }
    if (response.status === "ok" && response.results) {
      return response.results;
    }
    return [];
  } catch {
    return ripgrepFallback(pattern, projectDir);
  }
}
function ripgrepFallback(pattern, projectDir) {
  try {
    const escaped = pattern.replace(/"/g, '\\"').replace(/\$/g, "\\$");
    const result = execSync2(
      `rg "${escaped}" "${projectDir}" --type py --line-number --max-count 10 2>/dev/null`,
      { encoding: "utf-8", timeout: 3e3 }
    );
    return result.trim().split("\n").filter((l) => l).slice(0, 10).map((line) => {
      const match = line.match(/^([^:]+):(\d+):(.*)$/);
      if (match) {
        return { file: match[1], line: parseInt(match[2], 10), content: match[3] };
      }
      return { file: line, line: 0, content: "" };
    });
  } catch {
    return [];
  }
}
function tldrSemantic(query, projectDir = ".") {
  try {
    const response = queryDaemonSync({ cmd: "semantic", query, k: 5 }, projectDir);
    if (response.indexing || response.status === "unavailable") {
      return [];
    }
    if (response.status === "ok" && response.results) {
      return response.results;
    }
    return [];
  } catch {
    return [];
  }
}
function tldrImpact(funcName, projectDir = ".") {
  try {
    const response = queryDaemonSync({ cmd: "impact", func: funcName }, projectDir);
    if (response.indexing || response.status === "unavailable") {
      return [];
    }
    if (response.status === "ok" && response.callers) {
      return response.callers.map((c) => `${c.file}:${c.line}`);
    }
    return [];
  } catch {
    return [];
  }
}
function lookupCallers(pattern) {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || ".";
  return tldrImpact(pattern, projectDir).slice(0, 20);
}
function lookupSymbol(pattern) {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || ".";
  const funcResults = tldrSearch(`def ${pattern}`, projectDir);
  if (funcResults.length > 0) {
    return {
      type: "function",
      location: `${funcResults[0].file}:${funcResults[0].line}`
    };
  }
  const classResults = tldrSearch(`class ${pattern}`, projectDir);
  if (classResults.length > 0) {
    return {
      type: "class",
      location: `${classResults[0].file}:${classResults[0].line}`
    };
  }
  if (/^[A-Z][A-Z0-9_]+$/.test(pattern)) {
    const varResults = tldrSearch(`${pattern} =`, projectDir);
    if (varResults.length > 0) {
      return {
        type: "variable",
        location: `${varResults[0].file}:${varResults[0].line}`
      };
    }
  }
  return null;
}
var FUNCTION_VERB_PREFIXES = /^(get|set|is|has|do|can|create|update|delete|fetch|load|save|read|write|parse|build|make|init|setup|run|start|stop|handle|process|validate|check|find|search|filter|sort|map|reduce|transform|convert|format|render|display|show|hide|enable|disable|add|remove|insert|append|push|pop|clear|reset|close|open|connect|disconnect|send|receive|emit|on_|async_|_get|_set|_is|_has|_do|_create|_update|_delete|_fetch|_load|_save|_read|_write|_parse|_build|_make|_init|_setup|_run|_handle|_process|_validate|_check|_find|poll|call|exec|execute|invoke|apply|bind|dispatch|trigger|fire|notify|broadcast|publish|subscribe|unsubscribe|listen|watch|observe|register|unregister|mount|unmount|attach|detach|flush|dump|log|warn|error|debug|trace|print|throw|raise|assert|test|mock|stub|spy|wait|sleep|delay|retry|abort|cancel|pause|resume|refresh|reload|rerun|revert|rollback|commit|merge|split|join|clone|copy|move|swap|toggle|flip|increment|decrement|next|prev|first|last|peek|drain|consume|produce|yield|spawn|fork|join|kill|terminate|shutdown|cleanup|destroy|dispose|release|acquire|lock|unlock|enter|exit|begin|end|finalize)(_|$)/;
function extractTarget(pattern) {
  const indexed = lookupSymbol(pattern);
  if (indexed) {
    return { target: pattern, targetType: indexed.type };
  }
  const classMatch = pattern.match(/^class\s+(\w+)/);
  if (classMatch) return { target: classMatch[1], targetType: "class" };
  const defMatch = pattern.match(/^(?:async\s+)?def\s+(\w+)/);
  if (defMatch) return { target: defMatch[1], targetType: "function" };
  const functionMatch = pattern.match(/^(?:async\s+)?function\s+(\w+)/);
  if (functionMatch) return { target: functionMatch[1], targetType: "function" };
  const decoratorMatch = pattern.match(/^@(\w+)/);
  if (decoratorMatch) return { target: decoratorMatch[1], targetType: "decorator" };
  const importMatch = pattern.match(/^(?:import|from)\s+(\w+)/);
  if (importMatch) return { target: importMatch[1], targetType: "import" };
  const attrMatch = pattern.match(/(?:self|this)(?:\.|\\\.|\\\.\s*)(\w+)/);
  if (attrMatch) {
    const attr = attrMatch[1];
    if (FUNCTION_VERB_PREFIXES.test(attr)) {
      return { target: attr, targetType: "function" };
    }
    return { target: attr, targetType: "variable" };
  }
  if (/^__[a-z][a-z0-9_]*__$/.test(pattern)) {
    const moduleVars = ["__all__", "__version__", "__author__", "__doc__", "__file__", "__name__", "__package__", "__path__", "__cached__", "__loader__", "__spec__", "__builtins__", "__dict__", "__module__", "__slots__", "__annotations__"];
    if (moduleVars.includes(pattern)) {
      return { target: pattern, targetType: "variable" };
    }
    return { target: pattern, targetType: "function" };
  }
  if (/^[A-Z][A-Z0-9_]+$/.test(pattern)) return { target: pattern, targetType: "variable" };
  if (/^[A-Z][a-zA-Z0-9]+$/.test(pattern)) return { target: pattern, targetType: "class" };
  if (/^_?[a-z][a-z0-9_]*$/.test(pattern) && FUNCTION_VERB_PREFIXES.test(pattern)) {
    return { target: pattern, targetType: "function" };
  }
  if (/^_?[a-z][a-z0-9_]*$/.test(pattern)) {
    return { target: pattern, targetType: "variable" };
  }
  const camelCaseVerbPattern = /^(get|set|is|has|do|can|use|create|update|delete|fetch|load|save|read|write|parse|build|make|init|setup|run|start|stop|handle|process|validate|check|find|search|filter|sort|map|reduce|transform|convert|format|render|display|show|hide|enable|disable|add|remove|insert|append|push|pop|clear|reset|close|open|connect|disconnect|send|receive|emit|on|async|poll|call|exec|execute|invoke|apply|bind|dispatch|trigger|fire|notify|broadcast|publish|subscribe|watch|observe|register|mount|attach|flush|dump|log|warn|error|debug|print|throw|assert|test|mock|wait|sleep|retry|abort|cancel|pause|resume|refresh|reload|revert|commit|merge|clone|copy|move|toggle|spawn|fork|kill|terminate|shutdown|cleanup|destroy|dispose|release|acquire|lock|unlock|enter|exit|begin|end)[A-Z]/;
  if (camelCaseVerbPattern.test(pattern)) {
    return { target: pattern, targetType: "function" };
  }
  if (/^[a-z][a-zA-Z0-9]*$/.test(pattern) && /[A-Z]/.test(pattern)) {
    return { target: pattern, targetType: "variable" };
  }
  const identMatch = pattern.match(/\b([a-zA-Z_][a-zA-Z0-9_]{2,})\b/);
  if (identMatch) return { target: identMatch[1], targetType: "unknown" };
  return { target: null, targetType: "unknown" };
}
function suggestLayers(targetType, queryType) {
  switch (targetType) {
    case "function":
      return ["ast", "call_graph", "cfg"];
    case "class":
      return ["ast", "call_graph"];
    case "variable":
      return ["ast", "dfg"];
    case "import":
      return ["ast"];
    case "decorator":
      return ["ast", "call_graph"];
    default:
      return queryType === "semantic" ? ["ast", "call_graph", "cfg"] : ["ast", "call_graph"];
  }
}
function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => resolve(data));
  });
}
function classifyQuery(pattern) {
  const structuralPatterns = [
    /^(class|function|def|async def|const|let|var|interface|type|export)\s+\w+/,
    /^(import|from|require)\s/,
    /^\w+\s*\([^)]*\)/,
    // function calls
    /^async\s+(function|def)/,
    /\$\w+/,
    // AST-grep metavariables
    /^@\w+/
    // decorators
  ];
  if (structuralPatterns.some((p) => p.test(pattern))) {
    return "structural";
  }
  if (pattern.includes("\\") || pattern.includes("[") || /\([^)]*\|/.test(pattern)) {
    return "literal";
  }
  if (/^[A-Z][a-zA-Z0-9]*$/.test(pattern) || /^[a-z_][a-z0-9_]*$/.test(pattern) || /^[A-Z_][A-Z0-9_]*$/.test(pattern)) {
    return "literal";
  }
  if (pattern.includes("/") || /\.(ts|py|js|go|rs|md)/.test(pattern)) {
    return "literal";
  }
  const words = pattern.split(/\s+/).filter((w) => w.length > 0);
  if (words.length <= 2 && !/^(how|what|where|why|when|find|show|list)/i.test(pattern)) {
    return "literal";
  }
  const semanticPatterns = [
    /^(how|what|where|why|when|which)\s/i,
    /\?$/,
    /^(find|show|list|get|explain)\s+(all|the|every|any)/i,
    /works?$/i,
    /^.*\s+(implementation|architecture|flow|pattern|logic|system)$/i
  ];
  if (semanticPatterns.some((p) => p.test(pattern))) {
    return "semantic";
  }
  if (words.length >= 3) {
    return "semantic";
  }
  return "literal";
}
function getAstGrepSuggestion(pattern, lang = "python") {
  const suggestions = {
    "function": `def $FUNC($$$):`,
    "async": `async def $FUNC($$$):`,
    "class": `class $NAME:`,
    "import": `import $MODULE`,
    "decorator": `@$DECORATOR`
  };
  for (const [keyword, astPattern] of Object.entries(suggestions)) {
    if (pattern.toLowerCase().includes(keyword)) {
      return astPattern;
    }
  }
  return `$PATTERN($$$)`;
}
async function main() {
  const input = JSON.parse(await readStdin());
  if (input.tool_name !== "Grep") {
    console.log("{}");
    return;
  }
  const pattern = input.tool_input.pattern;
  const queryType = classifyQuery(pattern);
  const sessionId = input.session_id || "default";
  const { target, targetType } = extractTarget(pattern);
  const layers = suggestLayers(targetType, queryType);
  const symbolInfo = target ? lookupSymbol(target) : null;
  const callers = target ? lookupCallers(target) : [];
  storeSearchContext(sessionId, {
    timestamp: Date.now(),
    queryType,
    pattern,
    target,
    targetType,
    suggestedLayers: layers,
    definitionLocation: symbolInfo?.location,
    callers: callers.slice(0, 20)
    // Limit to 20 callers for token efficiency
  });
  if (queryType === "literal") {
    const projectDir2 = process.env.CLAUDE_PROJECT_DIR || ".";
    const searchResults = tldrSearch(pattern, projectDir2);
    let systemMsg2 = `\u{1F50D} **TLDR Search Results** for "${pattern}":

`;
    if (searchResults.length > 0) {
      systemMsg2 += searchResults.slice(0, 10).map(
        (r) => `  - ${r.file}:${r.line}: ${r.content.trim().substring(0, 80)}`
      ).join("\n");
      systemMsg2 += "\n\n*Grep proceeding as fallback. Consider using Read tool on specific files above.*";
    } else {
      systemMsg2 += `No TLDR results found. Grep proceeding normally.`;
    }
    const output2 = {
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "allow"
      },
      systemMessage: systemMsg2
    };
    console.log(JSON.stringify(output2));
    return;
  }
  if (queryType === "structural") {
    const astPattern = getAstGrepSuggestion(pattern);
    const projectDir2 = process.env.CLAUDE_PROJECT_DIR || ".";
    const searchResults = tldrSearch(pattern, projectDir2);
    let systemMsg2 = `\u{1F3AF} **Structural Query Detected**: "${pattern}"

`;
    systemMsg2 += `**AST-grep pattern**: \`${astPattern}\`

`;
    if (searchResults.length > 0) {
      systemMsg2 += `**TLDR found**:
`;
      systemMsg2 += searchResults.slice(0, 5).map(
        (r) => `  - ${r.file}:${r.line}`
      ).join("\n");
      systemMsg2 += "\n\n";
    }
    systemMsg2 += `*Grep proceeding. For richer context, try: \`tldr search "${target || pattern}" .\`*`;
    const output2 = {
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "allow"
      },
      systemMessage: systemMsg2
    };
    console.log(JSON.stringify(output2));
    return;
  }
  const projectDir = process.env.CLAUDE_PROJECT_DIR || ".";
  const semanticResults = tldrSemantic(pattern, projectDir);
  let systemMsg;
  if (semanticResults.length > 0) {
    const resultsStr = semanticResults.map((r) => {
      const loc = `${r.file}:${r.function || "module"}`;
      const score = r.score ? ` (${(r.score * 100).toFixed(0)}%)` : "";
      return `  - ${loc}${score}`;
    }).join("\n");
    systemMsg = `\u{1F9E0} **Semantic Search Results** (via TLDR daemon):

${resultsStr}

`;
    systemMsg += `*Grep proceeding as fallback. Consider Read tool on: \`${semanticResults[0].file}\`*`;
  } else {
    systemMsg = `\u{1F9E0} Semantic query detected: "${pattern}"
`;
    systemMsg += `*No TLDR semantic results. Grep proceeding. For deep analysis, try: Task(subagent_type="scout")*`;
  }
  const output = {
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "allow"
    },
    systemMessage: systemMsg
  };
  console.log(JSON.stringify(output));
}
main().catch(console.error);
