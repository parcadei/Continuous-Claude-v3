#!/usr/bin/env python3
"""Cross-platform status line for Claude Code.

Shows: 145K 72% | main U:6 | Goal → Current focus
Critical: ⚠ 160K 80% | main U:6 | Current focus

Replaces status.sh for Windows compatibility.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def get_session_id(data: dict) -> str:
    """Get session ID from Claude Code input.

    Claude Code provides session_id in the JSON input which:
    - Is unique per Claude terminal
    - Changes on /clear (correct - context resets)
    - Allows multiple Claudes in same project without interference
    """
    # session_id from Claude Code is the canonical source
    session_id = data.get("session_id", "")
    if session_id:
        return session_id[:8]  # First 8 chars for filename
    # Fallback to env var or ppid
    return os.environ.get("CLAUDE_SESSION_ID", str(os.getppid()))


def get_context_info(data: dict) -> tuple[int, int, str]:
    """Extract token usage and calculate context percentage.

    Returns:
        Tuple of (total_tokens, context_pct, token_display)
    """
    ctx = data.get("context_window", {})
    usage = ctx.get("current_usage", {})

    input_tokens = usage.get("input_tokens", 0) or 0
    cache_read = usage.get("cache_read_input_tokens", 0) or 0
    cache_creation = usage.get("cache_creation_input_tokens", 0) or 0

    system_overhead = 45000
    total_tokens = input_tokens + cache_read + cache_creation + system_overhead

    context_size = ctx.get("context_window_size", 200000) or 200000
    context_pct = min(100, total_tokens * 100 // context_size)

    # Format as K with one decimal
    token_display = f"{total_tokens / 1000:.1f}K"

    return total_tokens, context_pct, token_display


def cleanup_old_context_files(tmp_dir: Path, max_age_hours: int = 1) -> None:
    """Delete context percentage files older than max_age_hours.

    Runs occasionally to prevent /tmp accumulation.
    """
    import time
    import random

    # Only run cleanup 1% of the time to avoid overhead
    if random.random() > 0.01:
        return

    try:
        cutoff = time.time() - (max_age_hours * 3600)
        for f in tmp_dir.glob("claude-context-pct-*.txt"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except OSError:
                pass  # File may have been deleted
    except OSError:
        pass  # Non-critical


def log_context_drop(session_id: str, prev_pct: int, curr_pct: int) -> None:
    """Log significant context drops (likely auto-compaction).

    Logs to ~/.claude/autocompact.log (local, not pushed to repo).
    """
    from datetime import datetime
    log_file = Path.home() / ".claude" / "autocompact.log"
    try:
        with open(log_file, "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{timestamp} | session:{session_id} | {prev_pct}% → {curr_pct}% (drop: {prev_pct - curr_pct}%)\n")
    except OSError:
        pass


def write_context_pct(context_pct: int, data: dict) -> None:
    """Write context percentage for other hooks to read.

    Uses tempfile.gettempdir() for cross-platform compatibility.
    On macOS this returns $TMPDIR (/var/folders/...) which matches
    Node.js os.tmpdir() used by skill-activation-prompt.ts.

    Also detects and logs significant context drops (auto-compaction).
    """
    session_id = get_session_id(data)
    tmp_dir = Path(tempfile.gettempdir())
    tmp_file = tmp_dir / f"claude-context-pct-{session_id}.txt"
    try:
        # Check for context drop (auto-compaction detection)
        if tmp_file.exists():
            try:
                prev_pct = int(tmp_file.read_text().strip())
                # Log if drop > 10% (likely auto-compact, not normal variation)
                if prev_pct - context_pct > 10:
                    log_context_drop(session_id, prev_pct, context_pct)
            except (ValueError, OSError):
                pass

        tmp_file.write_text(str(context_pct))
        # Occasionally clean up old files
        cleanup_old_context_files(tmp_dir)
    except OSError:
        pass  # Non-critical, skip silently


def get_git_info(cwd: Path) -> str:
    """Get git branch and change counts.

    Returns:
        Formatted git info string with ANSI colors, or empty string
    """
    try:
        # Check if git repo
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--git-dir"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return ""

        # Get branch name
        result = subprocess.run(
            ["git", "-C", str(cwd), "--no-optional-locks", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5
        )
        branch = result.stdout.strip() if result.returncode == 0 else ""
        if len(branch) > 12:
            branch = branch[:10] + ".."

        # Get staged count
        result = subprocess.run(
            ["git", "-C", str(cwd), "--no-optional-locks", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=5
        )
        staged = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0

        # Get unstaged count
        result = subprocess.run(
            ["git", "-C", str(cwd), "--no-optional-locks", "diff", "--name-only"],
            capture_output=True, text=True, timeout=5
        )
        unstaged = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0

        # Get untracked count
        result = subprocess.run(
            ["git", "-C", str(cwd), "--no-optional-locks", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, timeout=5
        )
        added = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0

        # Build counts string
        counts_parts = []
        if staged > 0:
            counts_parts.append(f"S:{staged}")
        if unstaged > 0:
            counts_parts.append(f"U:{unstaged}")
        if added > 0:
            counts_parts.append(f"A:{added}")

        if counts_parts:
            counts = " ".join(counts_parts)
            return f"{branch} \033[33m{counts}\033[0m"
        else:
            return f"\033[32m{branch}\033[0m"

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def parse_filename_timestamp(path: Path) -> str:
    """Extract YYYY-MM-DD_HH-MM timestamp from filename.

    Returns '0000-00-00_00-00' if no timestamp found (sorts oldest).
    """
    match = re.search(r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2})', path.name)
    return match.group(1) if match else '0000-00-00_00-00'


def find_latest_handoff(project_dir: Path) -> Path | None:
    """Find the most recent handoff file by filename timestamp."""
    handoffs_dir = project_dir / "thoughts" / "shared" / "handoffs"
    if not handoffs_dir.exists():
        return None

    # Find all yaml/yml files recursively (YAML is current format, .md is legacy)
    handoff_files = []
    for pattern in ["**/*.yaml", "**/*.yml"]:
        handoff_files.extend(handoffs_dir.glob(pattern))

    if not handoff_files:
        return None

    # Sort by filename timestamp (YYYY-MM-DD_HH-MM), most recent first
    handoff_files.sort(key=parse_filename_timestamp, reverse=True)
    return handoff_files[0]


def extract_yaml_field(content: str, field: str) -> str:
    """Extract a top-level YAML field value."""
    pattern = rf"^{field}:\s*(.+?)$"
    match = re.search(pattern, content, re.MULTILINE)
    if match:
        return match.group(1).strip().strip('"\'')
    return ""


def get_continuity_info(project_dir: Path) -> tuple[str, str]:
    """Get goal and current focus from handoffs or legacy ledgers.

    Returns:
        Tuple of (goal, now_focus)
    """
    goal = ""
    now_focus = ""

    # Priority 1: YAML handoffs (new format)
    latest_handoff = find_latest_handoff(project_dir)
    if latest_handoff:
        try:
            content = latest_handoff.read_text()

            # Extract goal: and now: from YAML
            goal = extract_yaml_field(content, "goal")
            now_focus = extract_yaml_field(content, "now")

            # Fallback for markdown: topic or title
            if not goal:
                goal = extract_yaml_field(content, "topic")
            if not goal:
                match = re.search(r"^# (.+?)$", content, re.MULTILINE)
                if match:
                    goal = match.group(1).replace("Handoff:", "").strip()

            # Fallback for now: Action Items or Next Steps section
            if not now_focus:
                match = re.search(r"^## (?:Action Items|Next Steps)\s*\n(?:.*\n)*?^(\d+\.)\s*(.+?)$",
                                  content, re.MULTILINE)
                if match:
                    now_focus = match.group(2).strip()

            # Try P0 section
            if not now_focus:
                match = re.search(r"^### P0\s*\n(?:.*\n)*?^(\d+\.)\s*(.+?)$", content, re.MULTILINE)
                if match:
                    now_focus = match.group(2).strip()

        except OSError:
            pass

    # Priority 2: Legacy ledger files
    if not goal and not now_focus:
        ledgers_dir = project_dir / "thoughts" / "ledgers"
        if ledgers_dir.exists():
            ledger_files = list(ledgers_dir.glob("CONTINUITY_CLAUDE-*.md"))
            if ledger_files:
                ledger_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                try:
                    content = ledger_files[0].read_text()

                    # Get goal from ## Goal section
                    match = re.search(r"^## Goal\s*\n(.+?)$", content, re.MULTILINE)
                    if match:
                        goal = match.group(1).strip()[:40]

                    # Get Now: item
                    match = re.search(r"^\s*-\s*Now:\s*(.+?)$", content, re.MULTILINE)
                    if match:
                        now_focus = match.group(1).strip()

                except OSError:
                    pass

    # Truncate for display
    if len(goal) > 25:
        goal = goal[:23] + ".."
    if len(now_focus) > 30:
        now_focus = now_focus[:28] + ".."

    return goal, now_focus


def build_output(context_pct: int, token_display: str, git_info: str,
                 goal: str, now_focus: str) -> str:
    """Build the final colored output string."""
    # Build continuity string
    if goal and now_focus:
        continuity = f"{goal} → {now_focus}"
    elif now_focus:
        continuity = now_focus
    elif goal:
        continuity = goal
    else:
        continuity = ""

    # Color based on context usage
    if context_pct >= 80:
        # CRITICAL - Red warning
        ctx_display = f"\033[31m⚠ {token_display} {context_pct}%\033[0m"
        parts = [ctx_display]
        if git_info:
            parts.append(git_info)
        if now_focus:  # Only show now_focus when critical
            parts.append(now_focus)
    elif context_pct >= 60:
        # WARNING - Yellow
        ctx_display = f"\033[33m{token_display} {context_pct}%\033[0m"
        parts = [ctx_display]
        if git_info:
            parts.append(git_info)
        if continuity:
            parts.append(continuity)
    else:
        # NORMAL - Green
        ctx_display = f"\033[32m{token_display} {context_pct}%\033[0m"
        parts = [ctx_display]
        if git_info:
            parts.append(git_info)
        if continuity:
            parts.append(continuity)

    return " | ".join(parts)


def find_project_root(start_dir: Path) -> Path:
    """Find project root by looking for .git directory.

    Walks up from start_dir until finding .git or hitting filesystem root.
    This ensures we find the right directory even if cwd is a subdirectory.
    """
    current = start_dir.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return start_dir  # Fallback to original if no .git found


def main() -> None:
    """Main entry point."""
    # Read JSON from stdin
    try:
        stdin_data = sys.stdin.read()
        data = json.loads(stdin_data) if stdin_data.strip() else {}
    except json.JSONDecodeError:
        data = {}

    # Get working directory with robust fallback chain
    workspace = data.get("workspace", {})
    cwd_str = workspace.get("current_dir", "")

    if not cwd_str:
        # Fallback 1: CLAUDE_PROJECT_DIR env var (most reliable)
        cwd_str = os.environ.get("CLAUDE_PROJECT_DIR", "")

    if not cwd_str:
        # Fallback 2: Walk up from cwd to find .git
        cwd_str = str(find_project_root(Path.cwd()))

    cwd = Path(cwd_str)

    # Validate: if cwd doesn't have .git, try to find project root
    if not (cwd / ".git").exists():
        cwd = find_project_root(cwd)

    project_dir = cwd

    # Get context info
    _, context_pct, token_display = get_context_info(data)

    # Write context percentage for hooks (use session_id from Claude Code)
    write_context_pct(context_pct, data)

    # Get git info
    git_info = get_git_info(cwd)

    # Get continuity info
    goal, now_focus = get_continuity_info(project_dir)

    # Build and print output
    output = build_output(context_pct, token_display, git_info, goal, now_focus)
    print(output)


if __name__ == "__main__":
    main()
