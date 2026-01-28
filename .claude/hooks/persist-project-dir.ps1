# SessionStart hook: Persist CLAUDE_PROJECT_DIR to CLAUDE_ENV_FILE
# This makes the project dir available to all subsequent commands
# Uses current directory since hooks run in the project directory

# Debug log
$debugLog = "$env:TEMP\claude-hook-debug.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $debugLog -Value "[$timestamp] [persist-project-dir] CLAUDE_ENV_FILE=$($env:CLAUDE_ENV_FILE) PWD=$(Get-Location)"

if ($env:CLAUDE_ENV_FILE) {
    $projectDir = (Get-Location).Path
    Add-Content -Path $env:CLAUDE_ENV_FILE -Value "`$env:CLAUDE_PROJECT_DIR = `"$projectDir`""
    Add-Content -Path $debugLog -Value "[$timestamp] [persist-project-dir] Wrote to $($env:CLAUDE_ENV_FILE)"
}

# Output valid JSON for hook system
Write-Output '{"result":"continue"}'
