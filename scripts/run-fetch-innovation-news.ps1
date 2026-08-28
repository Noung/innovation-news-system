$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DefaultWorkspaceDir = Split-Path -Parent $ScriptDir
$WorkspaceDir = if ($env:INNOVATION_NEWS_WORKSPACE_DIR) { $env:INNOVATION_NEWS_WORKSPACE_DIR } else { $DefaultWorkspaceDir }

if ($env:INNOVATION_NEWS_ENV_FILE) {
    $EnvFile = $env:INNOVATION_NEWS_ENV_FILE
} elseif (Test-Path (Join-Path $WorkspaceDir '.env')) {
    $EnvFile = Join-Path $WorkspaceDir '.env'
} else {
    # Temporary rollback compatibility for installations that still keep the
    # legacy environment file beside the Python scripts.
    $EnvFile = Join-Path $ScriptDir '.env'
}

$MainScript = if ($env:INNOVATION_NEWS_MAIN_SCRIPT) { $env:INNOVATION_NEWS_MAIN_SCRIPT } else { Join-Path $ScriptDir 'fetch-innovation-news-mysql.py' }
$LogDir = if ($env:INNOVATION_NEWS_LOG_DIR) { $env:INNOVATION_NEWS_LOG_DIR } else { Join-Path $WorkspaceDir 'logs' }
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { 'python' }

$env:INNOVATION_NEWS_WORKSPACE_DIR = $WorkspaceDir
$env:INNOVATION_NEWS_ENV_FILE = $EnvFile

if (-not (Test-Path $EnvFile)) {
    Write-Error "Configuration file not found: $EnvFile"
    exit 78
}

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$LogFile = Join-Path $LogDir 'cron-innovation-news-mysql.log'

& $PythonBin $MainScript *>> $LogFile
exit $LASTEXITCODE
