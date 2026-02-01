// src/browser-learning-extractor.ts
import { readFileSync } from "fs";
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

// src/browser-learning-extractor.ts
var ERROR_PATTERNS = {
  staleRef: /No element found with reference/i,
  tabClosed: /No tabs available/i,
  unsupportedInput: /not a supported form input/i,
  detached: /Detached while handling/i,
  invalidRef: /invalid ref|ref not found/i,
  extensionNotRunning: /Extension not (running|connected)/i,
  oauthExpired: /OAuth token has expired/i
};
function readStdin() {
  return readFileSync(0, "utf-8");
}
function extractPatterns(code) {
  const patterns = [];
  if (code.includes("aria-ref=")) patterns.push("aria-ref-selector");
  if (code.includes("getByRole")) patterns.push("role-selector");
  if (code.includes("getByText")) patterns.push("text-selector");
  if (code.includes("locator(")) patterns.push("css-selector");
  if (code.includes(".fill(")) patterns.push("form-fill");
  if (code.includes(".click(")) patterns.push("click");
  if (code.includes(".check(")) patterns.push("checkbox");
  if (code.includes("keyboard.press")) patterns.push("keyboard");
  if (code.includes("screenshot")) patterns.push("screenshot");
  if (code.includes("accessibilitySnapshot")) patterns.push("a11y-snapshot");
  if (code.includes("page.goto")) patterns.push("navigation");
  if (code.includes("newPage()")) patterns.push("new-tab");
  return patterns;
}
function isPlaywriterSuccess(input) {
  const response = input.tool_response;
  if (response.error) return false;
  if (response.output?.includes("timed out")) return false;
  if (response.output?.includes("TimeoutError")) return false;
  if (response.output?.includes("Extension not connected")) return false;
  if (response.output?.includes("No browser tabs")) return false;
  return true;
}
function extractChromePatterns(toolName, input) {
  const patterns = [];
  const shortName = toolName.replace("mcp__claude-in-chrome__", "");
  patterns.push(shortName);
  if (shortName === "computer") {
    const action = input.tool_input.action;
    if (action) patterns.push(`computer-${action}`);
    if (input.tool_input.ref) patterns.push("ref-selector");
    if (input.tool_input.coordinate) patterns.push("coordinate-selector");
  }
  if (shortName === "navigate") patterns.push("navigation");
  if (shortName === "form_input") patterns.push("form-fill");
  if (shortName === "read_page") patterns.push("a11y-snapshot");
  if (shortName === "find") patterns.push("natural-language-find");
  if (shortName === "read_console_messages") patterns.push("console-debug");
  if (shortName === "read_network_requests") patterns.push("network-debug");
  if (shortName === "gif_creator") patterns.push("recording");
  return patterns;
}
function isChromeSuccess(input) {
  const response = input.tool_response;
  if (response.error) return false;
  const output = response.output || "";
  if (output.includes("Extension not running")) return false;
  if (output.includes("tab doesn't exist")) return false;
  if (output.includes("invalid tab")) return false;
  if (output.includes("OAuth token has expired")) return false;
  return true;
}
function extractChromeLearning(input) {
  const toolName = input.tool_name;
  const shortName = toolName.replace("mcp__claude-in-chrome__", "");
  const patterns = extractChromePatterns(toolName, input);
  const success = isChromeSuccess(input);
  const output = input.tool_response.output || "";
  const error = input.tool_response.error || "";
  if (shortName === "navigate") {
    const url = input.tool_input.url || "unknown";
    if (success) {
      return {
        type: "WORKING_SOLUTION",
        content: `Claude-in-Chrome navigation to ${url} succeeded. Unlike Playwriter, navigate() works reliably for URL changes.`,
        context: "Browser automation navigation",
        tags: ["claude-in-chrome", "navigation", "success", "auto_extracted"],
        confidence: "high"
      };
    } else {
      return {
        type: "FAILED_APPROACH",
        content: `Claude-in-Chrome navigation to ${url} failed: ${error || output.slice(0, 200)}`,
        context: "Browser automation navigation failure",
        tags: ["claude-in-chrome", "navigation", "failure", "auto_extracted"],
        confidence: "high"
      };
    }
  }
  if (shortName === "find" && !success && output.includes("OAuth")) {
    return {
      type: "FAILED_APPROACH",
      content: "Claude-in-Chrome find tool may fail with OAuth errors. Workaround: use refs from read_page instead of natural language find.",
      context: "Browser automation element finding",
      tags: ["claude-in-chrome", "find", "oauth", "workaround", "auto_extracted"],
      confidence: "high"
    };
  }
  if (shortName === "form_input" && success) {
    const value = String(input.tool_input.value || "").slice(0, 50);
    const ref = input.tool_input.ref || "unknown";
    return {
      type: "WORKING_SOLUTION",
      content: `Claude-in-Chrome form_input succeeded with ref=${ref}, value="${value}". Use refs from read_page for reliable form filling.`,
      context: "Browser form automation",
      tags: ["claude-in-chrome", "forms", "form_input", "auto_extracted"],
      confidence: "medium"
    };
  }
  if (shortName === "computer" && success) {
    const action = input.tool_input.action;
    if (action === "screenshot") {
      return {
        type: "CODEBASE_PATTERN",
        content: "Claude-in-Chrome computer(screenshot) captures visual state for verification.",
        context: "Browser visual verification",
        tags: ["claude-in-chrome", "screenshot", "verification", "auto_extracted"],
        confidence: "low"
      };
    }
    if (action === "left_click" || action === "right_click") {
      const target = input.tool_input.ref || (input.tool_input.coordinate ? `coordinate[${input.tool_input.coordinate}]` : "unknown");
      return {
        type: "WORKING_SOLUTION",
        content: `Claude-in-Chrome computer(${action}) on ${target} succeeded.`,
        context: "Browser click automation",
        tags: ["claude-in-chrome", "click", action, "auto_extracted"],
        confidence: "medium"
      };
    }
  }
  if (shortName === "read_console_messages" && success) {
    const messages = input.tool_response.messages;
    if (messages && Array.isArray(messages) && messages.length > 0) {
      return {
        type: "CODEBASE_PATTERN",
        content: `Console monitoring captured ${messages.length} messages. Use pattern filter to reduce noise.`,
        context: "Browser console debugging",
        tags: ["claude-in-chrome", "console", "debugging", "auto_extracted"],
        confidence: "medium"
      };
    }
  }
  if (shortName === "read_network_requests" && success) {
    const requests = input.tool_response.requests;
    if (requests && Array.isArray(requests) && requests.length > 0) {
      return {
        type: "CODEBASE_PATTERN",
        content: `Network monitoring captured ${requests.length} requests. Use urlPattern to filter API calls.`,
        context: "Browser network debugging",
        tags: ["claude-in-chrome", "network", "debugging", "auto_extracted"],
        confidence: "medium"
      };
    }
  }
  if (shortName === "gif_creator") {
    const action = input.tool_input.action;
    if (action === "export" && success) {
      return {
        type: "WORKING_SOLUTION",
        content: "Claude-in-Chrome GIF export succeeded. Pattern: start_recording \u2192 screenshot \u2192 actions \u2192 screenshot \u2192 stop_recording \u2192 export.",
        context: "Browser GIF recording",
        tags: ["claude-in-chrome", "gif", "recording", "auto_extracted"],
        confidence: "medium"
      };
    }
  }
  if (!success && (output.includes("Extension not running") || output.includes("click the playwriter extension"))) {
    return {
      type: "FAILED_APPROACH",
      content: "Claude-in-Chrome extension not active. User must click extension icon on target tab before automation.",
      context: "Browser extension activation",
      tags: ["claude-in-chrome", "extension", "activation", "auto_extracted"],
      confidence: "high"
    };
  }
  if (!success && ERROR_PATTERNS.staleRef.test(output)) {
    return {
      type: "FAILED_APPROACH",
      content: "Stale ref error - element no longer exists. Recovery: re-read page with read_page(), find element again by text/role.",
      context: "Browser element reference",
      tags: ["claude-in-chrome", "stale-ref", "recovery", "auto_extracted"],
      confidence: "high"
    };
  }
  if (!success && ERROR_PATTERNS.unsupportedInput.test(output)) {
    return {
      type: "FAILED_APPROACH",
      content: 'form_input failed on non-input element (likely custom checkbox as button). Recovery: use computer({ action: "left_click" }) instead.',
      context: "Browser form automation",
      tags: ["claude-in-chrome", "form_input", "custom-checkbox", "recovery", "auto_extracted"],
      confidence: "high"
    };
  }
  if (!success && ERROR_PATTERNS.detached.test(output)) {
    return {
      type: "FAILED_APPROACH",
      content: "Detached error - frame not ready. Recovery: wait(1) then retry the action. Usually succeeds on second attempt.",
      context: "Browser frame handling",
      tags: ["claude-in-chrome", "detached", "retry", "recovery", "auto_extracted"],
      confidence: "high"
    };
  }
  if (!success && ERROR_PATTERNS.tabClosed.test(output)) {
    return {
      type: "FAILED_APPROACH",
      content: "Tab closed or invalid tabId. Recovery: call tabs_context_mcp() to get fresh tab list, create new tab if needed.",
      context: "Browser tab management",
      tags: ["claude-in-chrome", "tab-closed", "recovery", "auto_extracted"],
      confidence: "high"
    };
  }
  return null;
}
function extractPlaywriterLearning(input) {
  const code = input.tool_input.code || "";
  const output = input.tool_response.output || "";
  const error = input.tool_response.error || "";
  const patterns = extractPatterns(code);
  const success = isPlaywriterSuccess(input);
  if (code.length < 50 && !patterns.length) return null;
  if (patterns.includes("navigation") && !success) {
    return {
      type: "FAILED_APPROACH",
      content: "Playwriter page.goto() fails with timeout. Extension only controls current page - cannot navigate programmatically.",
      context: "Browser automation navigation limitation",
      tags: ["playwriter", "navigation", "limitation", "auto_extracted"],
      confidence: "high"
    };
  }
  if (patterns.includes("new-tab") && !success) {
    return {
      type: "FAILED_APPROACH",
      content: "Playwriter cannot create new tabs via context.newPage(). User must open tabs manually and click extension.",
      context: "Browser automation tab limitation",
      tags: ["playwriter", "tabs", "limitation", "auto_extracted"],
      confidence: "high"
    };
  }
  if (success && patterns.includes("form-fill")) {
    const selectorMatch = code.match(/locator\(['"]([^'"]+)['"]\)|getBy\w+\(['"]([^'"]+)['"]\)/);
    const selector = selectorMatch ? selectorMatch[1] || selectorMatch[2] : "unknown";
    return {
      type: "WORKING_SOLUTION",
      content: `Playwriter form fill succeeded with selector pattern: ${selector}. Code: ${code.slice(0, 200)}`,
      context: "Browser form automation",
      tags: ["playwriter", "forms", ...patterns, "auto_extracted"],
      confidence: "medium"
    };
  }
  if (success && patterns.includes("checkbox")) {
    return {
      type: "WORKING_SOLUTION",
      content: `Playwriter checkbox interaction pattern: ${code.slice(0, 200)}`,
      context: "Browser checkbox automation",
      tags: ["playwriter", "checkbox", "forms", "auto_extracted"],
      confidence: "medium"
    };
  }
  if (success && patterns.includes("screenshot")) {
    return {
      type: "CODEBASE_PATTERN",
      content: "screenshotWithAccessibilityLabels() captures visual state when a11y tree misses modal/overlay content.",
      context: "Browser visual verification",
      tags: ["playwriter", "screenshot", "verification", "auto_extracted"],
      confidence: "low"
      // Common pattern, low novelty
    };
  }
  if (success && patterns.includes("keyboard")) {
    const keyMatch = code.match(/press\(['"]([^'"]+)['"]\)/);
    const key = keyMatch ? keyMatch[1] : "unknown";
    return {
      type: "WORKING_SOLUTION",
      content: `Keyboard ${key} key works in Playwriter for interactions like closing modals.`,
      context: "Browser keyboard automation",
      tags: ["playwriter", "keyboard", key.toLowerCase(), "auto_extracted"],
      confidence: "medium"
    };
  }
  return null;
}
function storeLearning(learning, sessionId) {
  const opcDir = getOpcDir();
  if (!opcDir) return false;
  const args = [
    "run",
    "python",
    "scripts/core/store_learning.py",
    "--session-id",
    sessionId,
    "--type",
    learning.type,
    "--content",
    learning.content,
    "--context",
    learning.context,
    "--tags",
    learning.tags.join(","),
    "--confidence",
    learning.confidence
  ];
  const result = spawnSync("uv", args, {
    encoding: "utf-8",
    cwd: opcDir,
    env: { ...process.env, PYTHONPATH: opcDir },
    timeout: 1e4
  });
  return result.status === 0;
}
async function main() {
  const input = JSON.parse(readStdin());
  const isPlaywriter = input.tool_name.startsWith("mcp__playwriter__");
  const isChrome = input.tool_name.startsWith("mcp__claude-in-chrome__");
  if (!isPlaywriter && !isChrome) {
    return;
  }
  if (input.tool_name === "mcp__playwriter__reset") {
    return;
  }
  if (input.tool_name === "mcp__claude-in-chrome__tabs_context_mcp" || input.tool_name === "mcp__claude-in-chrome__tabs_create_mcp") {
    return;
  }
  let learning = null;
  if (isPlaywriter) {
    learning = extractPlaywriterLearning(input);
  } else if (isChrome) {
    learning = extractChromeLearning(input);
  }
  if (learning) {
    if (learning.confidence === "high") {
      const stored = storeLearning(learning, input.session_id);
      if (stored) {
        console.log(JSON.stringify({
          hookSpecificOutput: {
            hookEventName: "PostToolUse",
            additionalContext: `[Browser Learning Stored] ${learning.type}: ${learning.content.slice(0, 100)}...`
          }
        }));
        return;
      }
    }
    console.log(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PostToolUse",
        additionalContext: `[Browser Pattern] ${learning.type}: ${learning.content.slice(0, 150)}...`
      }
    }));
  }
}
main().catch(() => {
});
