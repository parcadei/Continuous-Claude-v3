#!/bin/bash
set -e

# Post-tool-use hook that:
# 1. Tracks edited files and their repos (Edit/Write tools)
# 2. Captures build/test attempts for reasoning-aware VCS (Bash tool)
#
# Reasoning data stored in: .git/claude/branches/<branch>/attempts.jsonl
# This enables future features like enriched PRs and semantic search

# Read tool information from stdin
tool_info=$(cat)

# Extract common data
tool_name=$(echo "$tool_info" | jq -r '.tool_name // empty')
session_id=$(echo "$tool_info" | jq -r '.session_id // empty')
transcript_path=$(echo "$tool_info" | jq -r '.transcript_path // empty')

# ============================================================================
# BASH TOOL HANDLING - Capture build/test attempts for reasoning
# ============================================================================
# Note: tool_name may be "Bash" (hook) or "bash" (transcript) - handle both
if [[ "$tool_name" == "Bash" || "$tool_name" == "bash" ]]; then
    command=$(echo "$tool_info" | jq -r '.tool_input.command // empty')

    # Strip common runner prefixes for matching (uv run, poetry run, etc.)
    stripped_command=$(echo "$command" | sed -E 's/^(uv run |poetry run |pipenv run |pdm run )//; s/^python -m //')

    # Only track build/test commands (skip general bash usage)
    # Use stripped_command for matching (removes uv run, poetry run, etc. prefixes)
    if [[ "$stripped_command" =~ (npm|pnpm|yarn|make|cargo|go|pytest|jest|vitest|bun|swift|xcodebuild|tsc|eslint|prettier).*(build|test|check|lint|compile|typecheck|run\ build|run\ test|run\ check|run\ lint) ]] || \
       [[ "$stripped_command" =~ ^(npm|pnpm|yarn)\ (run\ )?(build|test|check|lint|typecheck)$ ]] || \
       [[ "$stripped_command" =~ ^(make|cargo\ build|cargo\ test|go\ build|go\ test|pytest|jest|vitest) ]]; then

        # Initialize branch-keyed storage
        git_claude_dir="$CLAUDE_PROJECT_DIR/.git/claude"
        current_branch=$(git -C "$CLAUDE_PROJECT_DIR" branch --show-current 2>/dev/null || echo "detached")
        safe_branch=$(echo "$current_branch" | tr '/' '-')
        branch_dir="$git_claude_dir/branches/$safe_branch"
        mkdir -p "$branch_dir"

        # Try multiple field paths for exit code (hook vs transcript format)
        # Claude Code hook uses tool_response.interrupted (false = success)
        exit_code=$(echo "$tool_info" | jq -r '
            .tool_output.exit //
            .tool_response.exit //
            .tool_result.exit //
            .tool_result.exit_code //
            (if .tool_response.interrupted == false then "0" else "unknown" end)
        ')

        # Try multiple field paths for output (truncate to 2000 chars)
        # Claude Code hook uses tool_response.stdout/stderr
        output=$(echo "$tool_info" | jq -r '
            .tool_output.output //
            .tool_response.output //
            .tool_response.stdout //
            .tool_response.stderr //
            .tool_result.output //
            .tool_result.stdout //
            ""
        ' | head -c 2000)

        # FALLBACK: If exit_code unknown, try reading from transcript
        if [[ "$exit_code" == "unknown" ]] && [[ -f "$transcript_path" ]]; then
            exit_code=$(tail -50 "$transcript_path" | \
                jq -r 'select(.tool_name == "bash" and .type == "tool_result") | .tool_output.exit' 2>/dev/null | \
                tail -1)
            output=$(tail -50 "$transcript_path" | \
                jq -r 'select(.tool_name == "bash" and .type == "tool_result") | .tool_output.output' 2>/dev/null | \
                tail -1 | head -c 2000)
        fi

        # Log attempt to branch-keyed JSONL file
        timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        attempts_file="$branch_dir/attempts.jsonl"

        if [[ "$exit_code" != "0" ]] && [[ "$exit_code" != "unknown" ]] && [[ "$exit_code" != "null" ]]; then
            # Log failure with error output
            jq -n \
                --arg ts "$timestamp" \
                --arg type "build_fail" \
                --arg cmd "$command" \
                --arg exit "$exit_code" \
                --arg err "$output" \
                --arg branch "$current_branch" \
                '{timestamp: $ts, type: $type, command: $cmd, exit_code: $exit, error: $err, branch: $branch}' \
                >> "$attempts_file"
        elif [[ "$exit_code" == "0" ]]; then
            # Log success (no error output needed)
            jq -n \
                --arg ts "$timestamp" \
                --arg type "build_pass" \
                --arg cmd "$command" \
                --arg branch "$current_branch" \
                '{timestamp: $ts, type: $type, command: $cmd, branch: $branch}' \
                >> "$attempts_file"
        fi
        # If exit_code still unknown/null, silently skip (don't break the hook)
    fi
    exit 0
fi

# ============================================================================
# EDIT/WRITE TOOL HANDLING - Original tracking logic
# ============================================================================
file_path=$(echo "$tool_info" | jq -r '.tool_input.file_path // empty')

# Skip if not an edit tool or no file path
if [[ ! "$tool_name" =~ ^(Edit|MultiEdit|Write)$ ]] || [[ -z "$file_path" ]]; then
    exit 0  # Exit 0 for skip conditions
fi

# Skip markdown files
if [[ "$file_path" =~ \.(md|markdown)$ ]]; then
    exit 0  # Exit 0 for skip conditions
fi

# Create cache directory in project
cache_dir="$CLAUDE_PROJECT_DIR/.claude/tsc-cache/${session_id:-default}"
mkdir -p "$cache_dir"

# Function to detect repo from file path
detect_repo() {
    local file="$1"
    local project_root="$CLAUDE_PROJECT_DIR"

    # Remove project root from path
    local relative_path="${file#$project_root/}"

    # Extract first directory component
    local repo=$(echo "$relative_path" | cut -d'/' -f1)

    # Common project directory patterns
    case "$repo" in
        # Frontend variations
        frontend|client|web|app|ui)
            echo "$repo"
            ;;
        # Backend variations
        backend|server|api|src|services)
            echo "$repo"
            ;;
        # Database
        database|prisma|migrations)
            echo "$repo"
            ;;
        # Package/monorepo structure
        packages)
            # For monorepos, get the package name
            local package=$(echo "$relative_path" | cut -d'/' -f2)
            if [[ -n "$package" ]]; then
                echo "packages/$package"
            else
                echo "$repo"
            fi
            ;;
        # Examples directory
        examples)
            local example=$(echo "$relative_path" | cut -d'/' -f2)
            if [[ -n "$example" ]]; then
                echo "examples/$example"
            else
                echo "$repo"
            fi
            ;;
        *)
            # Check if it's a source file in root
            if [[ ! "$relative_path" =~ / ]]; then
                echo "root"
            else
                echo "unknown"
            fi
            ;;
    esac
}

# Function to get build command for repo
get_build_command() {
    local repo="$1"
    local project_root="$CLAUDE_PROJECT_DIR"
    local repo_path="$project_root/$repo"

    # Check if package.json exists and has a build script
    if [[ -f "$repo_path/package.json" ]]; then
        if grep -q '"build"' "$repo_path/package.json" 2>/dev/null; then
            # Detect package manager (prefer pnpm, then npm, then yarn)
            if [[ -f "$repo_path/pnpm-lock.yaml" ]]; then
                echo "cd $repo_path && pnpm build"
            elif [[ -f "$repo_path/package-lock.json" ]]; then
                echo "cd $repo_path && npm run build"
            elif [[ -f "$repo_path/yarn.lock" ]]; then
                echo "cd $repo_path && yarn build"
            else
                echo "cd $repo_path && npm run build"
            fi
            return
        fi
    fi

    # Special case for database with Prisma
    if [[ "$repo" == "database" ]] || [[ "$repo" =~ prisma ]]; then
        if [[ -f "$repo_path/schema.prisma" ]] || [[ -f "$repo_path/prisma/schema.prisma" ]]; then
            echo "cd $repo_path && npx prisma generate"
            return
        fi
    fi

    # No build command found
    echo ""
}

# Function to get TSC command for repo
get_tsc_command() {
    local repo="$1"
    local project_root="$CLAUDE_PROJECT_DIR"
    local repo_path="$project_root/$repo"

    # Check if tsconfig.json exists
    if [[ -f "$repo_path/tsconfig.json" ]]; then
        # Check for Vite/React-specific tsconfig
        if [[ -f "$repo_path/tsconfig.app.json" ]]; then
            echo "cd $repo_path && npx tsc --project tsconfig.app.json --noEmit"
        else
            echo "cd $repo_path && npx tsc --noEmit"
        fi
        return
    fi

    # No TypeScript config found
    echo ""
}

# Detect repo
repo=$(detect_repo "$file_path")

# Skip if unknown repo
if [[ "$repo" == "unknown" ]] || [[ -z "$repo" ]]; then
    exit 0  # Exit 0 for skip conditions
fi

# Log edited file
echo "$(date +%s):$file_path:$repo" >> "$cache_dir/edited-files.log"

# Update affected repos list
if ! grep -q "^$repo$" "$cache_dir/affected-repos.txt" 2>/dev/null; then
    echo "$repo" >> "$cache_dir/affected-repos.txt"
fi

# Store build commands
build_cmd=$(get_build_command "$repo")
tsc_cmd=$(get_tsc_command "$repo")

if [[ -n "$build_cmd" ]]; then
    echo "$repo:build:$build_cmd" >> "$cache_dir/commands.txt.tmp"
fi

if [[ -n "$tsc_cmd" ]]; then
    echo "$repo:tsc:$tsc_cmd" >> "$cache_dir/commands.txt.tmp"
fi

# Remove duplicates from commands
if [[ -f "$cache_dir/commands.txt.tmp" ]]; then
    sort -u "$cache_dir/commands.txt.tmp" > "$cache_dir/commands.txt"
    rm -f "$cache_dir/commands.txt.tmp"
fi

# Exit cleanly
exit 0