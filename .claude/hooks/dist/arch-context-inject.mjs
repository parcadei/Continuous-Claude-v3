// src/arch-context-inject.ts
import { readFileSync as readFileSync2, existsSync as existsSync2 } from "fs";

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

// src/arch-context-inject.ts
var PLANNING_PATTERNS = [
  /\bplan\b/i,
  /\bdesign\b/i,
  /\barchitecture\b/i,
  /\brefactor\b/i,
  /\brestructure\b/i,
  /\breorganize\b/i,
  /\bmodularize\b/i,
  /\bsplit\s+(?:into|up)\b/i,
  /\bextract\s+(?:to|into)\b/i,
  /\bcreate\s+(?:new\s+)?(?:module|package|service)\b/i
];
function readStdin() {
  return readFileSync2(0, "utf-8");
}
function hasPlanningIntent(text) {
  return PLANNING_PATTERNS.some((pattern) => pattern.test(text));
}
function getArchitecture(projectPath) {
  try {
    const response = queryDaemonSync({ cmd: "arch", language: "python" }, projectPath);
    if (response.status === "unavailable" || response.status === "error") {
      return null;
    }
    if (response.indexing) {
      return null;
    }
    const result = response.result;
    if (!result) {
      return null;
    }
    const layers = {};
    if (result.entry_layer && Array.isArray(result.entry_layer)) {
      layers.entry = result.entry_layer.slice(0, 15).map(
        (f) => `${f.file}:${f.function}`
      );
    }
    if (result.leaf_layer && Array.isArray(result.leaf_layer)) {
      layers.leaf = result.leaf_layer.slice(0, 15).map(
        (f) => `${f.file}:${f.function}`
      );
    }
    const circular = result.circular_dependencies?.map(
      (c) => `${c.a} <-> ${c.b}`
    );
    if (Object.keys(layers).length === 0) {
      return null;
    }
    return { layers, circular };
  } catch {
    return null;
  }
}
function formatArchContext(arch) {
  const lines = ["## Architecture Layers"];
  for (const [layer, files] of Object.entries(arch.layers)) {
    if (!files || files.length === 0) continue;
    lines.push("");
    lines.push(`### ${layer.toUpperCase()}`);
    for (const file of files.slice(0, 10)) {
      lines.push(`- ${file}`);
    }
    if (files.length > 10) {
      lines.push(`- ... and ${files.length - 10} more`);
    }
  }
  if (arch.circular && arch.circular.length > 0) {
    lines.push("");
    lines.push("### Circular Dependencies (WARNING)");
    for (const dep of arch.circular.slice(0, 5)) {
      lines.push(`- ${dep}`);
    }
  }
  return lines.join("\n");
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
  if (!hasPlanningIntent(fullText)) {
    console.log("{}");
    return;
  }
  if (prompt.includes("## Architecture") || prompt.includes("### ENTRY") || prompt.includes("### SERVICE")) {
    console.log("{}");
    return;
  }
  const projectDir = process.env.CLAUDE_PROJECT_DIR || input.cwd;
  if (!projectDir || !existsSync2(projectDir)) {
    console.log("{}");
    return;
  }
  const arch = getArchitecture(projectDir);
  if (!arch) {
    console.log("{}");
    return;
  }
  const archContext = formatArchContext(arch);
  const enhancedPrompt = `${archContext}

---

${prompt}`;
  const output = {
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "allow",
      permissionDecisionReason: "Injected architecture context for planning task",
      updatedInput: {
        ...input.tool_input,
        prompt: enhancedPrompt
      }
    }
  };
  console.log(JSON.stringify(output));
}
main().catch(() => {
  console.log("{}");
});
