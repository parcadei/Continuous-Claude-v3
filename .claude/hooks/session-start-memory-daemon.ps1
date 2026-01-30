# SessionStart Hook - Auto-start Memory Extraction Daemon (Windows)
# Starts the memory daemon (singleton - one per machine, not per project)

$OPC_DIR = if ($env:CLAUDE_OPC_DIR) { $env:CLAUDE_OPC_DIR } else { "$env:USERPROFILE\.claude" }
$DAEMON_SCRIPT = Join-Path $OPC_DIR "scripts\core\memory_daemon.py"

# Check if daemon script exists
if (-not (Test-Path $DAEMON_SCRIPT)) {
    Write-Output '{"result":"continue"}'
    exit 0
}

# Check OPC directory
if (-not (Test-Path $OPC_DIR)) {
    Write-Output '{"result":"continue"}'
    exit 0
}

# Check if daemon is already running
Push-Location $OPC_DIR
try {
    $env:PYTHONPATH = "."
    $STATUS = uv run python scripts/core/memory_daemon.py status 2>$null

    if ($STATUS -match "Running: Yes") {
        Write-Output '{"result":"continue"}'
        exit 0
    }

    # Start daemon (daemonizes itself)
    uv run python scripts/core/memory_daemon.py start 2>$null

    # Brief wait for daemon to initialize
    Start-Sleep -Milliseconds 500

} finally {
    Pop-Location
}

Write-Output '{"result":"continue"}'
