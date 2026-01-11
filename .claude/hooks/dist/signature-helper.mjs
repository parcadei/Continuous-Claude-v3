// src/signature-helper.ts
import { readFileSync as readFileSync2 } from "fs";

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

// src/signature-helper.ts
var SKIP_NAMES = /* @__PURE__ */ new Set([
  "if",
  "for",
  "while",
  "with",
  "except",
  "match",
  "case",
  "print",
  "len",
  "str",
  "int",
  "list",
  "dict",
  "set",
  "tuple",
  "range",
  "enumerate",
  "zip",
  "map",
  "filter",
  "sorted",
  "reversed",
  "type",
  "isinstance",
  "hasattr",
  "getattr",
  "setattr",
  "super",
  "open",
  "input",
  "any",
  "all",
  "min",
  "max",
  "sum",
  "abs",
  "require",
  "import",
  "export",
  "return",
  "const",
  "let",
  "var",
  "function",
  "async",
  "await",
  "new",
  "this",
  "class",
  "extends"
]);
function extractFunctionCalls(code) {
  const callRe = /\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(/g;
  const calls = /* @__PURE__ */ new Set();
  let match;
  while ((match = callRe.exec(code)) !== null) {
    const name = match[1];
    if (!SKIP_NAMES.has(name)) {
      calls.add(name);
    }
  }
  return Array.from(calls);
}
function findFunctionFile(funcName, projectDir) {
  try {
    const response = queryDaemonSync(
      { cmd: "search", pattern: `def ${funcName}` },
      projectDir
    );
    if (response.indexing || response.status === "unavailable" || response.status === "error") {
      return null;
    }
    if (response.results && response.results.length > 0) {
      return `${projectDir}/${response.results[0].file}`;
    }
  } catch {
  }
  return null;
}
function getSignatureFromTLDR(funcName, filePath) {
  try {
    const projectDir = getProjectDir();
    const response = queryDaemonSync(
      { cmd: "extract", file: filePath },
      projectDir
    );
    if (response.indexing || response.status === "unavailable" || response.status === "error") {
      return null;
    }
    const extract = response.result;
    if (!extract?.functions) {
      return null;
    }
    for (const func of extract.functions) {
      if (func.name === funcName || func.name === `async ${funcName}`) {
        return func.signature;
      }
    }
  } catch {
  }
  return null;
}
function getProjectDir() {
  return process.env.CLAUDE_PROJECT_DIR || process.cwd();
}
async function main() {
  const input = JSON.parse(readFileSync2(0, "utf-8"));
  if (input.tool_name !== "Edit") {
    console.log("{}");
    return;
  }
  const newCode = input.tool_input.new_string || "";
  if (!newCode || newCode.length < 10) {
    console.log("{}");
    return;
  }
  const calls = extractFunctionCalls(newCode);
  if (calls.length === 0) {
    console.log("{}");
    return;
  }
  const projectDir = getProjectDir();
  const signatures = [];
  for (const call of calls.slice(0, 5)) {
    const filePath = findFunctionFile(call, projectDir);
    if (filePath) {
      const sig = getSignatureFromTLDR(call, filePath);
      if (sig) {
        signatures.push(sig);
      }
    }
  }
  if (signatures.length === 0) {
    console.log("{}");
    return;
  }
  const output = {
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      additionalContext: `[Signatures from TLDR]
${signatures.join("\n")}`
    }
  };
  console.log(JSON.stringify(output));
}
main().catch(() => console.log("{}"));
