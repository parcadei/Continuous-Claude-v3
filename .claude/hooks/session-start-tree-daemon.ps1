# SessionStart Hook - Auto-start Knowledge Tree Daemon (Windows)
# Starts the tree daemon for the current project directory.

$PROJECT_DIR = (Get-Location).Path
$OPC_DIR = if ($env:CLAUDE_OPC_DIR) { $env:CLAUDE_OPC_DIR } else { "$env:USERPROFILE\continuous-claude\opc" }
$DAEMON_SCRIPT = Join-Path $OPC_DIR "scripts\core\tree_daemon.py"

# Check if daemon script exists
if (-not (Test-Path $DAEMON_SCRIPT)) {
    Write-Output '{"result":"continue"}'
    exit 0
}

# Check OPC directory exists
if (-not (Test-Path $OPC_DIR)) {
    Write-Output '{"result":"continue"}'
    exit 0
}

# Check if daemon is already running for this project
Push-Location $OPC_DIR
try {
    $env:PYTHONPATH = "."
    $STATUS = & uv run python scripts/core/tree_daemon.py --project "$PROJECT_DIR" --status 2>$null

    if ($STATUS -match "running") {
        Write-Output '{"result":"continue"}'
        exit 0
    }

    # Start daemon in background (suppress output)
    Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run", "python", "scripts/core/tree_daemon.py", "--project", "$PROJECT_DIR", "--background" -RedirectStandardOutput "NUL" -RedirectStandardError "NUL"
} catch {
    # Ignore errors - daemon is non-critical
} finally {
    Pop-Location
}

Write-Output '{"result":"continue"}'
