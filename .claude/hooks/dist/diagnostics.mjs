#!/usr/bin/env node

// src/diagnostics.ts
import * as fs from "fs";
import * as path from "path";
var HOOKS_DIR = path.join(process.env.USERPROFILE || process.env.HOME || "", ".claude", "hooks");
var DIST_DIR = path.join(HOOKS_DIR, "dist");
var SRC_DIR = path.join(HOOKS_DIR, "src");
var ERROR_LOG = path.join(HOOKS_DIR, "errors.log");
var SETTINGS_PATH = path.join(process.env.USERPROFILE || process.env.HOME || "", ".claude", "settings.json");
function getHookConfig() {
  try {
    const content = fs.readFileSync(SETTINGS_PATH, "utf-8");
    return JSON.parse(content);
  } catch {
    return {};
  }
}
function buildInventory(settings) {
  const inventory = [];
  if (!settings.hooks) return inventory;
  for (const [event, entries] of Object.entries(settings.hooks)) {
    for (const entry of entries) {
      const matcher = entry.matcher || "*";
      for (const hook of entry.hooks) {
        const match = hook.command.match(/([^/\\]+)\.mjs|([^/\\]+)\.ps1/);
        const name = match ? match[1] || match[2] : hook.command;
        const isTypeScript = hook.command.includes(".mjs");
        const isPowerShell = hook.command.includes(".ps1");
        let sourceExists = false;
        let builtExists = false;
        if (isTypeScript) {
          const srcName = name.replace(".mjs", "") + ".ts";
          sourceExists = fs.existsSync(path.join(SRC_DIR, srcName));
          builtExists = fs.existsSync(path.join(DIST_DIR, name + ".mjs"));
        } else if (isPowerShell) {
          sourceExists = fs.existsSync(path.join(HOOKS_DIR, name + ".ps1"));
          builtExists = sourceExists;
        }
        inventory.push({
          name,
          event,
          matcher,
          sourceExists,
          builtExists,
          timeout: hook.timeout
        });
      }
    }
  }
  return inventory;
}
function getRecentErrors(maxLines = 50) {
  const errors = [];
  if (!fs.existsSync(ERROR_LOG)) {
    return errors;
  }
  try {
    const content = fs.readFileSync(ERROR_LOG, "utf-8");
    const lines = content.split("\n").filter((l) => l.trim());
    const recentLines = lines.slice(-maxLines);
    for (const line of recentLines) {
      const timestampMatch = line.match(/^\[?(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})/);
      errors.push({
        timestamp: timestampMatch ? timestampMatch[1] : "unknown",
        message: line.slice(0, 200)
        // Truncate long messages
      });
    }
  } catch {
  }
  return errors;
}
function assessHealth(inventory, errors) {
  const issues = [];
  const missingBuilds = inventory.filter((h) => h.sourceExists && !h.builtExists);
  if (missingBuilds.length > 0) {
    issues.push(`${missingBuilds.length} hook(s) not built: ${missingBuilds.map((h) => h.name).join(", ")}`);
  }
  const missingSources = inventory.filter((h) => !h.sourceExists);
  if (missingSources.length > 0) {
    issues.push(`${missingSources.length} hook(s) missing source: ${missingSources.map((h) => h.name).join(", ")}`);
  }
  const recentErrorCount = errors.filter((e) => {
    if (e.timestamp === "unknown") return false;
    const errorTime = new Date(e.timestamp).getTime();
    const oneHourAgo = Date.now() - 60 * 60 * 1e3;
    return errorTime > oneHourAgo;
  }).length;
  if (recentErrorCount > 10) {
    issues.push(`${recentErrorCount} errors in the last hour`);
  } else if (recentErrorCount > 0) {
    issues.push(`${recentErrorCount} recent error(s)`);
  }
  let status = "healthy";
  if (missingBuilds.length > 0 || recentErrorCount > 10) {
    status = "unhealthy";
  } else if (missingSources.length > 0 || recentErrorCount > 0) {
    status = "degraded";
  }
  return { status, issues };
}
function runDiagnostics(args2) {
  const settings = getHookConfig();
  const inventory = buildInventory(settings);
  const errors = getRecentErrors();
  const health = assessHealth(inventory, errors);
  const byEvent = {};
  for (const hook of inventory) {
    byEvent[hook.event] = (byEvent[hook.event] || 0) + 1;
  }
  return {
    timestamp: (/* @__PURE__ */ new Date()).toISOString(),
    hooks: {
      total: inventory.length,
      byEvent,
      inventory
    },
    errors: {
      count: errors.length,
      recent: errors.slice(-10)
      // Last 10 errors
    },
    health
  };
}
function formatDiagnostics(result2) {
  const lines = [];
  lines.push("=".repeat(60));
  lines.push("HOOK DIAGNOSTICS DASHBOARD");
  lines.push(`Generated: ${result2.timestamp}`);
  lines.push("=".repeat(60));
  lines.push("");
  const statusEmoji = result2.health.status === "healthy" ? "[OK]" : result2.health.status === "degraded" ? "[WARN]" : "[FAIL]";
  lines.push(`HEALTH: ${statusEmoji} ${result2.health.status.toUpperCase()}`);
  if (result2.health.issues.length > 0) {
    for (const issue of result2.health.issues) {
      lines.push(`  - ${issue}`);
    }
  }
  lines.push("");
  lines.push("HOOKS SUMMARY");
  lines.push(`  Total: ${result2.hooks.total}`);
  for (const [event, count] of Object.entries(result2.hooks.byEvent)) {
    lines.push(`  ${event}: ${count}`);
  }
  lines.push("");
  lines.push("HOOK INVENTORY");
  lines.push("-".repeat(60));
  const byEvent = {};
  for (const hook of result2.hooks.inventory) {
    if (!byEvent[hook.event]) byEvent[hook.event] = [];
    byEvent[hook.event].push(hook);
  }
  for (const [event, hooks] of Object.entries(byEvent)) {
    lines.push(`[${event}]`);
    for (const hook of hooks) {
      const status = hook.builtExists ? "[OK]" : hook.sourceExists ? "[BUILD]" : "[MISS]";
      const matcherStr = hook.matcher !== "*" ? ` (${hook.matcher})` : "";
      lines.push(`  ${status} ${hook.name}${matcherStr} [${hook.timeout}ms]`);
    }
    lines.push("");
  }
  if (result2.errors.recent.length > 0) {
    lines.push("RECENT ERRORS");
    lines.push("-".repeat(60));
    for (const error of result2.errors.recent) {
      lines.push(`[${error.timestamp}] ${error.message}`);
    }
  } else {
    lines.push("RECENT ERRORS: None");
  }
  return lines.join("\n");
}
var args = process.argv.slice(2);
var jsonOutput = args.includes("--json");
var errorsOnly = args.includes("--errors");
var hooksOnly = args.includes("--hooks");
var result = runDiagnostics(args);
if (jsonOutput) {
  console.log(JSON.stringify(result, null, 2));
} else if (errorsOnly) {
  if (result.errors.recent.length === 0) {
    console.log("No recent errors.");
  } else {
    console.log("Recent Errors:");
    for (const error of result.errors.recent) {
      console.log(`[${error.timestamp}] ${error.message}`);
    }
  }
} else if (hooksOnly) {
  console.log("Hook Inventory:");
  for (const hook of result.hooks.inventory) {
    const status = hook.builtExists ? "[OK]" : "[MISS]";
    console.log(`${status} ${hook.event}/${hook.name}`);
  }
} else {
  console.log(formatDiagnostics(result));
}
