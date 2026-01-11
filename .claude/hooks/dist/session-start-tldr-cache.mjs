// src/session-start-tldr-cache.ts
import { readFileSync as readFileSync2, existsSync as existsSync2, statSync } from "fs";
import { join as join2 } from "path";

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

// src/session-start-tldr-cache.ts
function readStdin() {
  return readFileSync2(0, "utf-8");
}
function getSemanticIndexStatus(projectDir) {
  const indexPath = join2(projectDir, ".tldr", "cache", "semantic", "index.faiss");
  return {
    exists: existsSync2(indexPath),
    path: indexPath
  };
}
function getCacheStatus(projectDir) {
  const cacheDir = join2(projectDir, ".claude", "cache", "tldr");
  if (!existsSync2(cacheDir)) {
    return { exists: false, files: { arch: false, calls: false, dead: false } };
  }
  const archPath = join2(cacheDir, "arch.json");
  const callsPath = join2(cacheDir, "call_graph.json");
  const deadPath = join2(cacheDir, "dead.json");
  const metaPath = join2(cacheDir, "meta.json");
  const files = {
    arch: existsSync2(archPath) && statSync(archPath).size > 10,
    calls: existsSync2(callsPath) && statSync(callsPath).size > 10,
    dead: existsSync2(deadPath) && statSync(deadPath).size > 2
  };
  let age_hours;
  if (existsSync2(metaPath)) {
    try {
      const meta = JSON.parse(readFileSync2(metaPath, "utf-8"));
      const cachedAt = new Date(meta.cached_at);
      age_hours = Math.round((Date.now() - cachedAt.getTime()) / (1e3 * 60 * 60));
    } catch {
    }
  }
  return {
    exists: files.arch || files.calls || files.dead,
    age_hours,
    files
  };
}
async function main() {
  const input = JSON.parse(readStdin());
  if (!["startup", "resume"].includes(input.source)) {
    console.log("{}");
    return;
  }
  const projectDir = process.env.CLAUDE_PROJECT_DIR || input.cwd;
  const cache = getCacheStatus(projectDir);
  const shouldWarm = !cache.exists || cache.age_hours !== void 0 && cache.age_hours > 24;
  let warmStatus = "";
  if (shouldWarm) {
    try {
      const warmResponse = queryDaemonSync({ cmd: "warm" }, projectDir);
      if (warmResponse.status === "ok") {
        warmStatus = " \u{1F525} Cache warmed!";
      } else if (warmResponse.indexing) {
        warmStatus = " \u23F3 Warming in progress...";
      }
    } catch {
    }
  }
  if (!cache.exists && !warmStatus) {
    console.log("{}");
    return;
  }
  const available = [];
  if (cache.files.arch) available.push("arch");
  if (cache.files.calls) available.push("calls");
  if (cache.files.dead) available.push("dead");
  const ageStr = cache.age_hours !== void 0 ? ` (${cache.age_hours}h old)` : "";
  const freshness = cache.age_hours !== void 0 && cache.age_hours > 168 ? " \u26A0\uFE0F STALE" : "";
  const semantic = getSemanticIndexStatus(projectDir);
  const semanticWarning = semantic.exists ? "" : "\n\u26A0\uFE0F No semantic index found. Run `tldr semantic index .` for AI-powered code search.";
  const cacheInfo = cache.exists ? `${available.join(", ")}` : "building...";
  const message = `\u{1F4CA} TLDR cache${ageStr}${freshness}${warmStatus}: ${cacheInfo}${semanticWarning}`;
  console.log(message);
}
main().catch(() => {
  console.log("{}");
});
