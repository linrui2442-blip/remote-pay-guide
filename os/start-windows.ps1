param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$osDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $osDir
$frontendDir = Join-Path $osDir "frontend"
$requirements = Join-Path $osDir "backend\requirements.txt"

function Require-Command([string]$Name, [string]$InstallHint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name was not found. $InstallHint"
    }
}

Require-Command "python" "Install Python 3.11+ and reopen PowerShell."
Require-Command "npm" "Install Node.js LTS and reopen PowerShell."

if (-not $env:YOUTUBE_OAUTH_CLIENT_ID) {
    $env:YOUTUBE_OAUTH_CLIENT_ID = Read-Host "YouTube OAuth Client ID"
}

if (-not $env:YOUTUBE_OAUTH_CLIENT_SECRET) {
    $secureSecret = Read-Host "YouTube OAuth Client Secret" -AsSecureString
    $secretPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureSecret)
    try {
        $env:YOUTUBE_OAUTH_CLIENT_SECRET = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPtr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPtr)
    }
}

if (-not $env:YOUTUBE_OAUTH_REDIRECT_URI) {
    $env:YOUTUBE_OAUTH_REDIRECT_URI = "http://localhost:5173/oauth/youtube/callback"
}

if (-not $SkipInstall) {
    Write-Host "Installing backend dependencies..."
    & python -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Backend dependency installation failed."
    }

    Write-Host "Installing frontend dependencies..."
    Push-Location $frontendDir
    try {
        & npm install
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend dependency installation failed."
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host "Starting Remote Pay Guide OS backend..."
Start-Process -FilePath "powershell.exe" -WorkingDirectory $repoRoot -ArgumentList @(
    "-NoExit",
    "-Command",
    "python -m uvicorn main:app --app-dir os/backend --host 127.0.0.1 --port 8000"
)

Write-Host "Starting Remote Pay Guide OS frontend..."
Start-Process -FilePath "powershell.exe" -WorkingDirectory $frontendDir -ArgumentList @(
    "-NoExit",
    "-Command",
    "npm run dev -- --host 127.0.0.1"
)

Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "Remote Pay Guide OS is starting."
Write-Host "Frontend: http://localhost:5173"
Write-Host "Backend:  http://localhost:8000"
Write-Host "OAuth callback: $env:YOUTUBE_OAUTH_REDIRECT_URI"
Write-Host ""
Write-Host "OAuth credentials were set only for this launcher process and its child processes; they were not written to the repository."
