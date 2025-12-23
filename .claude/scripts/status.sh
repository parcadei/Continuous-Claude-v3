#!/bin/bash
# StatusLine - shows what you'd forget after compaction
# Format: 145K 72% | main U:6 | ✓ Last done → Current focus
# Critical: ⚠ 160K 80% | main U:6 | Current focus

input=$(cat)

project_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cwd=$(echo "$input" | jq -r '.workspace.current_dir // ""' 2>/dev/null)
[[ -z "$cwd" || "$cwd" == "null" ]] && cwd="$project_dir"

# ─────────────────────────────────────────────────────────────────
# TOKENS - Context usage
# ─────────────────────────────────────────────────────────────────
input_tokens=$(echo "$input" | jq -r '.context_window.current_usage.input_tokens // 0' 2>/dev/null)
cache_read=$(echo "$input" | jq -r '.context_window.current_usage.cache_read_input_tokens // 0' 2>/dev/null)
cache_creation=$(echo "$input" | jq -r '.context_window.current_usage.cache_creation_input_tokens // 0' 2>/dev/null)

system_overhead=45000
total_tokens=$((input_tokens + cache_read + cache_creation + system_overhead))
context_size=$(echo "$input" | jq -r '.context_window.context_window_size // 200000' 2>/dev/null)

context_pct=$((total_tokens * 100 / context_size))
[[ "$context_pct" -gt 100 ]] && context_pct=100

# Write for hooks (per-session to avoid multi-instance conflicts)
echo "$context_pct" > "/tmp/claude-context-pct-${CLAUDE_SESSION_ID:-default}.txt"

# Format as K with one decimal
token_display=$(awk "BEGIN {printf \"%.1fK\", $total_tokens/1000}")

# ─────────────────────────────────────────────────────────────────
# GIT - Branch + S/U/A counts
# ─────────────────────────────────────────────────────────────────
git_info=""
if git -C "$cwd" rev-parse --git-dir > /dev/null 2>&1; then
    branch=$(git -C "$cwd" --no-optional-locks rev-parse --abbrev-ref HEAD 2>/dev/null)
    [[ ${#branch} -gt 12 ]] && branch="${branch:0:10}.."

    staged=$(git -C "$cwd" --no-optional-locks diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
    unstaged=$(git -C "$cwd" --no-optional-locks diff --name-only 2>/dev/null | wc -l | tr -d ' ')
    added=$(git -C "$cwd" --no-optional-locks ls-files --others --exclude-standard 2>/dev/null | wc -l | tr -d ' ')

    counts=""
    [[ "$staged" -gt 0 ]] && counts="S:$staged"
    [[ "$unstaged" -gt 0 ]] && counts="${counts:+$counts }U:$unstaged"
    [[ "$added" -gt 0 ]] && counts="${counts:+$counts }A:$added"

    if [[ -n "$counts" ]]; then
        git_info="$branch \033[33m$counts\033[0m"
    else
        git_info="\033[32m$branch\033[0m"
    fi
fi

# ─────────────────────────────────────────────────────────────────
# CONTINUITY - Last done + Current focus (what you'd forget)
# ─────────────────────────────────────────────────────────────────
ledger=$(ls -t "$project_dir"/CONTINUITY_CLAUDE-*.md 2>/dev/null | head -1)
last_done=""
now_focus=""

if [[ -n "$ledger" ]]; then
    # Get the most recent "Done:" item (last one in the list)
    last_done=$(grep -E '^\s*-\s*Done:' "$ledger" 2>/dev/null | \
        tail -1 | \
        sed 's/^[[:space:]]*-[[:space:]]*Done:[[:space:]]*//')

    # Truncate
    [[ ${#last_done} -gt 20 ]] && last_done="${last_done:0:18}.."

    # Get "Now:" item
    now_focus=$(grep -E '^\s*-\s*Now:' "$ledger" 2>/dev/null | \
        sed 's/^[[:space:]]*-[[:space:]]*Now:[[:space:]]*//' | \
        head -1)

    # Truncate based on whether we have last_done
    if [[ -n "$last_done" ]]; then
        [[ ${#now_focus} -gt 25 ]] && now_focus="${now_focus:0:23}.."
    else
        [[ ${#now_focus} -gt 40 ]] && now_focus="${now_focus:0:38}.."
    fi
fi

# Build continuity string: "✓ Last → Now" or just "Now"
continuity=""
if [[ -n "$last_done" && -n "$now_focus" ]]; then
    continuity="✓ $last_done → $now_focus"
elif [[ -n "$now_focus" ]]; then
    continuity="$now_focus"
fi

# ─────────────────────────────────────────────────────────────────
# OUTPUT - Contextual priority
# ─────────────────────────────────────────────────────────────────
# Critical context (≥80%): Warning takes priority
# Normal: Show everything

if [[ "$context_pct" -ge 80 ]]; then
    # CRITICAL - Context warning takes priority
    ctx_display="\033[31m⚠ ${token_display} ${context_pct}%\033[0m"
    output="$ctx_display"
    [[ -n "$git_info" ]] && output="$output | $git_info"
    [[ -n "$now_focus" ]] && output="$output | $now_focus"
elif [[ "$context_pct" -ge 60 ]]; then
    # WARNING - Yellow context
    ctx_display="\033[33m${token_display} ${context_pct}%\033[0m"
    output="$ctx_display"
    [[ -n "$git_info" ]] && output="$output | $git_info"
    [[ -n "$continuity" ]] && output="$output | $continuity"
else
    # NORMAL - Green, show full continuity
    ctx_display="\033[32m${token_display} ${context_pct}%\033[0m"
    output="$ctx_display"
    [[ -n "$git_info" ]] && output="$output | $git_info"
    [[ -n "$continuity" ]] && output="$output | $continuity"
fi

echo -e "$output"
