#!/bin/bash
# Install Continuous Claude globally to ~/.claude/
# This enables all features in any project, not just this repo.
#
# Usage: ./install-global.sh
#
# ⚠️  WARNING: This script REPLACES the following directories:
#   ~/.claude/skills/     - Replaced entirely
#   ~/.claude/agents/     - Replaced entirely
#   ~/.claude/rules/      - Replaced entirely
#   ~/.claude/hooks/      - Replaced entirely
#   ~/.claude/scripts/    - Files added/overwritten
#   ~/.claude/plugins/braintrust-tracing/ - Replaced
#   ~/.claude/settings.json - Replaced (backup created)
#
# ✓ Preserved:
#   ~/.claude/.env        - Not touched if exists
#   ~/.claude/cache/      - Not touched
#   ~/.claude/state/      - Not touched
#
# Safe to run multiple times - settings.json is backed up before overwrite.
# If you have custom skills/agents/rules, copy them to a safe location first.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GLOBAL_DIR="$HOME/.claude"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo ""
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│  Continuous Claude - Global Installation                    │"
echo "└─────────────────────────────────────────────────────────────┘"
echo ""
echo "This will install to: $GLOBAL_DIR"
echo ""
echo "⚠️  WARNING: The following will be REPLACED:"
echo "   • ~/.claude/skills/     (all skills)"
echo "   • ~/.claude/agents/     (all agents)"
echo "   • ~/.claude/rules/      (all rules)"
echo "   • ~/.claude/hooks/      (all hooks)"
echo "   • ~/.claude/settings.json (backup created)"
echo ""
echo "✓ PRESERVED (not touched):"
echo "   • ~/.claude/.env"
echo "   • ~/.claude/cache/"
echo "   • ~/.claude/state/"
echo ""
echo "📦 A full backup will be created at ~/.claude-backup-<timestamp>"
echo ""

# Check for --yes flag to skip prompt
if [[ "${1:-}" != "--yes" && "${1:-}" != "-y" ]]; then
    read -p "Continue with installation? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
fi

echo ""
echo "Installing Continuous Claude to $GLOBAL_DIR..."
echo ""

# Install uv if not present (required for learnings hook)
if ! command -v uv &> /dev/null; then
    echo "Installing uv (Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Add to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"
    echo "✓ uv installed"
    echo ""
fi

# Install qlty if not present (required for code quality checks)
if ! command -v qlty &> /dev/null && [ ! -f "$HOME/.qlty/bin/qlty" ]; then
    echo "Installing qlty (code quality toolkit)..."
    curl -fsSL https://qlty.sh/install.sh | bash
    # Add to PATH for this session
    export PATH="$HOME/.qlty/bin:$PATH"
    echo "✓ qlty installed"
    echo ""
elif command -v qlty &> /dev/null || [ -f "$HOME/.qlty/bin/qlty" ]; then
    echo "✓ qlty already installed"
    echo ""
fi

# Install MCP runtime package globally (makes mcp-exec, mcp-generate available everywhere)
echo "Installing MCP runtime package globally..."
cd "$SCRIPT_DIR"
uv tool install . --force --quiet 2>/dev/null || {
    echo "⚠️  Could not install MCP package globally. Run manually:"
    echo "   cd $SCRIPT_DIR && uv tool install . --force"
}
echo "✓ MCP commands installed: mcp-exec, mcp-generate, mcp-discover"
echo "  (available in ~/.local/bin/)"
echo ""

# Create global dir if needed
mkdir -p "$GLOBAL_DIR"

# Full backup of existing .claude directory
BACKUP_DIR="$HOME/.claude-backup-$TIMESTAMP"
if [ -d "$GLOBAL_DIR" ] && [ "$(ls -A "$GLOBAL_DIR" 2>/dev/null)" ]; then
    echo "Creating full backup at $BACKUP_DIR..."
    cp -r "$GLOBAL_DIR" "$BACKUP_DIR"
    echo "Backup complete. To restore: rm -rf ~/.claude && mv $BACKUP_DIR ~/.claude"
    echo ""
fi

# Copy directories (overwrite)
echo "Copying skills..."
rm -rf "$GLOBAL_DIR/skills"
cp -r "$SCRIPT_DIR/.claude/skills" "$GLOBAL_DIR/skills"

echo "Copying agents..."
rm -rf "$GLOBAL_DIR/agents"
cp -r "$SCRIPT_DIR/.claude/agents" "$GLOBAL_DIR/agents"

echo "Copying rules..."
rm -rf "$GLOBAL_DIR/rules"
cp -r "$SCRIPT_DIR/.claude/rules" "$GLOBAL_DIR/rules"

echo "Copying hooks..."
rm -rf "$GLOBAL_DIR/hooks"
cp -r "$SCRIPT_DIR/.claude/hooks" "$GLOBAL_DIR/hooks"
# Remove source files (only dist needed for runtime)
rm -rf "$GLOBAL_DIR/hooks/src" "$GLOBAL_DIR/hooks/node_modules" "$GLOBAL_DIR/hooks/*.ts" 2>/dev/null || true

echo "Copying scripts..."
mkdir -p "$GLOBAL_DIR/scripts"
cp "$SCRIPT_DIR/scripts/"*.py "$GLOBAL_DIR/scripts/" 2>/dev/null || true
cp "$SCRIPT_DIR/.claude/scripts/"*.sh "$GLOBAL_DIR/scripts/" 2>/dev/null || true
cp "$SCRIPT_DIR/init-project.sh" "$GLOBAL_DIR/scripts/" 2>/dev/null || true
cp "$SCRIPT_DIR/scripts/artifact_schema.sql" "$GLOBAL_DIR/scripts/" 2>/dev/null || true

echo "Copying MCP config..."
cp "$SCRIPT_DIR/mcp_config.json" "$GLOBAL_DIR/mcp_config.json"
echo "  → Global MCP servers available in all projects"
echo "  → Project configs override/extend global (config merging)"

echo "Copying plugins..."
mkdir -p "$GLOBAL_DIR/plugins"
cp -r "$SCRIPT_DIR/.claude/plugins/braintrust-tracing" "$GLOBAL_DIR/plugins/" 2>/dev/null || true

# Copy settings.json (use project version as base)
echo "Installing settings.json..."
cp "$SCRIPT_DIR/.claude/settings.json" "$GLOBAL_DIR/settings.json"

# Create .env if it doesn't exist
if [ ! -f "$GLOBAL_DIR/.env" ]; then
    echo "Creating .env template..."
    cp "$SCRIPT_DIR/.env.example" "$GLOBAL_DIR/.env"
    echo ""
    echo "IMPORTANT: Edit ~/.claude/.env and add your API keys:"
    echo "  - BRAINTRUST_API_KEY (for session tracing)"
    echo "  - PERPLEXITY_API_KEY (for web search)"
    echo "  - etc."
else
    echo ".env already exists (not overwritten)"
fi

# Create required cache directories
mkdir -p "$GLOBAL_DIR/cache/learnings"
mkdir -p "$GLOBAL_DIR/cache/insights"
mkdir -p "$GLOBAL_DIR/cache/agents"
mkdir -p "$GLOBAL_DIR/cache/artifact-index"
mkdir -p "$GLOBAL_DIR/state/braintrust_sessions"

echo ""
echo "Installation complete!"
echo ""

# Check for global MCP servers that could pollute projects
CLAUDE_JSON="$HOME/.claude.json"
if [ -f "$CLAUDE_JSON" ] && command -v jq &> /dev/null; then
    GLOBAL_MCP_COUNT=$(jq -r '.mcpServers // {} | keys | length' "$CLAUDE_JSON" 2>/dev/null || echo "0")
    if [ "$GLOBAL_MCP_COUNT" -gt 0 ]; then
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "⚠️  GLOBAL MCP SERVERS DETECTED"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "Found $GLOBAL_MCP_COUNT global MCP servers in ~/.claude.json:"
        jq -r '.mcpServers // {} | keys[]' "$CLAUDE_JSON" 2>/dev/null | sed 's/^/  • /'
        echo ""
        echo "These servers are inherited by ALL projects and can cause"
        echo "skills to use unexpected tools (e.g., /onboard using 'beads')."
        echo ""
        echo "Recommended: Remove global MCP servers and configure them"
        echo "per-project in each project's .mcp.json instead."
        echo ""
        read -p "Remove global MCP servers from ~/.claude.json? [y/N] " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # Backup first
            cp "$CLAUDE_JSON" "$CLAUDE_JSON.backup.$TIMESTAMP"
            echo "Backup created: $CLAUDE_JSON.backup.$TIMESTAMP"

            # Remove only the mcpServers key, preserve everything else
            jq 'del(.mcpServers)' "$CLAUDE_JSON" > "$CLAUDE_JSON.tmp"
            mv "$CLAUDE_JSON.tmp" "$CLAUDE_JSON"
            echo "✓ Removed global MCP servers"
            echo ""
            echo "To restore: cp $CLAUDE_JSON.backup.$TIMESTAMP $CLAUDE_JSON"
        else
            echo "Skipped. You can disable specific servers later with: /mcp disable <server>"
        fi
        echo ""
    fi
elif [ -f "$CLAUDE_JSON" ] && ! command -v jq &> /dev/null; then
    # Check if file likely has mcpServers without jq
    if grep -q '"mcpServers"' "$CLAUDE_JSON" 2>/dev/null; then
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "⚠️  NOTE: Global MCP servers may exist in ~/.claude.json"
        echo "   Install 'jq' to auto-remove them, or disable manually:"
        echo "   /mcp disable <server-name>"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
    fi
fi

echo "Features now available in any project:"
echo "  - MCP commands: mcp-exec, mcp-generate (from any directory)"
echo "  - Global MCP config: ~/.claude/mcp_config.json (merged with project)"
echo "  - Continuity ledger (/continuity_ledger)"
echo "  - Handoffs (/create_handoff, /resume_handoff)"
echo "  - TDD workflow (auto-activates on 'implement', 'fix bug')"
echo "  - Session tracing (if BRAINTRUST_API_KEY set)"
echo "  - All skills and agents"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "MCP SERVERS & API KEYS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "The system uses these MCP servers (all optional - features degrade gracefully):"
echo ""
echo "  RepoPrompt     - Token-efficient codebase exploration (/rp-explorer, /onboard)"
echo "                   Get from: https://repoprompt.com"
echo "                   Enable MCP Server in the app settings"
echo ""
echo "  Braintrust     - Session tracing + auto-learnings"
echo "                   Get key: https://braintrust.dev"
echo ""
echo "  Perplexity     - AI-powered web search (/perplexity-search)"
echo "                   Get key: https://perplexity.ai/settings/api"
echo ""
echo "  Firecrawl      - Web scraping (/firecrawl-scrape)"
echo "                   Get key: https://firecrawl.dev"
echo ""
echo "  Morph          - Fast codebase search (/morph-search)"
echo "                   Get key: https://morphllm.com"
echo ""
echo "  Nia            - Library documentation (/nia-docs)"
echo "                   Get key: https://trynia.ai"
echo ""
echo "  GitHub         - GitHub code/issue search (/github-search)"
echo "                   Get key: https://github.com/settings/tokens"
echo ""
echo "  Qlty           - Code quality checks (/qlty-check)"
echo "                   Auto-installed by this script (no API key needed)"
echo ""
echo "Add keys to: ~/.claude/.env"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "FOR EACH PROJECT - Initialize project structure:"
echo ""
echo "  cd /path/to/your/project"
echo "  ~/.claude/scripts/init-project.sh"
echo ""
echo "This creates thoughts/, .claude/cache/, and the Artifact Index"
echo "database so all hooks work immediately."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "To update later, pull the repo and run this script again."
