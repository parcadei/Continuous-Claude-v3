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
# Use PPID as unique session ID since CLAUDE_SESSION_ID isn't set by Claude Code
session_id="${CLAUDE_SESSION_ID:-$PPID}"
echo "$context_pct" > "/tmp/claude-context-pct-${session_id}.txt"

# ─────────────────────────────────────────────────────────────────
# RESOURCES - RAM and agent limits for resource management hooks
# ─────────────────────────────────────────────────────────────────
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Support mock values for testing
if [[ -n "$MOCK_FREE_MEM_MB" ]]; then
    free_mem="$MOCK_FREE_MEM_MB"
else
    # Get system memory info
    resources=$(bash "$script_dir/get-resources.sh" 2>/dev/null || echo '{"freeMemMB": 4096, "totalMemMB": 16384}')
    free_mem=$(echo "$resources" | jq -r '.freeMemMB // 4096')
fi

# Calculate max agents: (freeRAM - 2GB safety) / 500MB per agent
safety_mb=2048
per_agent_mb=500
max_agents=$(( (free_mem - safety_mb) / per_agent_mb ))
# Clamp to [1, 20]
[[ "$max_agents" -lt 1 ]] && max_agents=1
[[ "$max_agents" -gt 20 ]] && max_agents=20

# Support mock values for testing
if [[ -n "$MOCK_ACTIVE_AGENTS" ]]; then
    active_agents="$MOCK_ACTIVE_AGENTS"
else
    # Get active agent count via Python coordination DB
    active_agents=$(uv run python -c "
from scripts.agentica.coordination import CoordinationDB
print(CoordinationDB().get_global_running_count())
" 2>/dev/null || echo "0")
fi

# Write resources JSON for downstream hooks
echo "{\"freeMemMB\": $free_mem, \"activeAgents\": $active_agents, \"maxAgents\": $max_agents, \"contextPct\": $context_pct}" > "/tmp/claude-resources-${session_id}.json"

# ─────────────────────────────────────────────────────────────────
# RESOURCE DISPLAY - Show RAM and agent count when utilization >= 50%
# Format: RAM:4G Ag:5/8 with color coding
# ─────────────────────────────────────────────────────────────────
resource_display=""
if [[ "$active_agents" -gt 0 && "$max_agents" -gt 0 ]]; then
    utilization=$((active_agents * 100 / max_agents))
    if [[ "$utilization" -ge 50 ]]; then
        # Format RAM in GB (rounded)
        ram_gb=$((free_mem / 1024))

        # Color code based on utilization
        # Green: <50% (but we only show if >=50%)
        # Yellow: 50-79%
        # Red: >=80%
        if [[ "$utilization" -ge 80 ]]; then
            resource_display="\033[31mRAM:${ram_gb}G Ag:${active_agents}/${max_agents}\033[0m"
        else
            resource_display="\033[33mRAM:${ram_gb}G Ag:${active_agents}/${max_agents}\033[0m"
        fi
    fi
fi

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
# CONTINUITY - Phase progress + Current focus (what you'd forget)
# ─────────────────────────────────────────────────────────────────

# Find most recent ledger file (check multiple locations)
ledger=""

# 1. Check thoughts/ledgers/ (primary location)
if [[ -d "$project_dir/thoughts/ledgers" ]]; then
    ledger=$(ls -t "$project_dir"/thoughts/ledgers/CONTINUITY_CLAUDE-*.md 2>/dev/null | head -1)
fi

# 2. Check root directory (older pattern, fallback)
if [[ -z "$ledger" ]]; then
    ledger=$(ls -t "$project_dir"/CONTINUITY_CLAUDE-*.md 2>/dev/null | head -1)
fi

# Try phase progress script first (for multi-phase implementations)
phase_progress=""
if [[ -x "$script_dir/phase-progress-status.sh" ]]; then
    phase_progress=$(CLAUDE_PROJECT_DIR="$project_dir" bash "$script_dir/phase-progress-status.sh" 2>/dev/null || true)
fi

# Fall back to simple Now: extraction if no phase progress
last_done=""
now_focus=""

if [[ -z "$phase_progress" && -n "$ledger" ]]; then
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

    # Clean up markdown formatting and [->] marker
    now_focus=$(echo "$now_focus" | sed 's/\[[-\>→]*\][[:space:]]*//' | sed 's/\*\*//g')

    # Truncate based on whether we have last_done
    if [[ -n "$last_done" ]]; then
        [[ ${#now_focus} -gt 25 ]] && now_focus="${now_focus:0:23}.."
    else
        [[ ${#now_focus} -gt 40 ]] && now_focus="${now_focus:0:38}.."
    fi
fi

# Build continuity string: phase progress > "✓ Last → Now" > just "Now"
continuity=""
if [[ -n "$phase_progress" ]]; then
    continuity="$phase_progress"
elif [[ -n "$last_done" && -n "$now_focus" ]]; then
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
    [[ -n "$resource_display" ]] && output="$output | $resource_display"
    [[ -n "$now_focus" ]] && output="$output | $now_focus"
elif [[ "$context_pct" -ge 60 ]]; then
    # WARNING - Yellow context
    ctx_display="\033[33m${token_display} ${context_pct}%\033[0m"
    output="$ctx_display"
    [[ -n "$git_info" ]] && output="$output | $git_info"
    [[ -n "$resource_display" ]] && output="$output | $resource_display"
    [[ -n "$continuity" ]] && output="$output | $continuity"
else
    # NORMAL - Green, show full continuity
    ctx_display="\033[32m${token_display} ${context_pct}%\033[0m"
    output="$ctx_display"
    [[ -n "$git_info" ]] && output="$output | $git_info"
    [[ -n "$resource_display" ]] && output="$output | $resource_display"
    [[ -n "$continuity" ]] && output="$output | $continuity"
fi

echo -e "$output"
