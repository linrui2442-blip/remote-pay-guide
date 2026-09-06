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

function Normalize-ProxyUrl([string]$Value) {
    if (-not $Value) { return $null }
    $trimmed = $Value.Trim()
    if ($trimmed -match '^[a-zA-Z][a-zA-Z0-9+.-]*://') {
        return $trimmed
    }
    return "http://$trimmed"
}

function Get-WindowsUserProxy {
    try {
        $settings = Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction Stop
        if (-not $settings.ProxyEnable -or -not $settings.ProxyServer) {
            return $null
        }

        $raw = [string]$settings.ProxyServer
        if ($raw -notmatch '=') {
            $url = Normalize-ProxyUrl $raw
            return @{ http = $url; https = $url }
        }

        $parts = @{}
        foreach ($entry in ($raw -split ';')) {
            if ($entry -match '^\s*([^=]+)=(.+)$') {
                $parts[$matches[1].Trim().ToLowerInvariant()] = Normalize-ProxyUrl $matches[2]
            }
        }

        $httpProxy = $parts['http']
        $httpsProxy = $parts['https']
        if (-not $httpsProxy) { $httpsProxy = $httpProxy }
        if (-not $httpProxy) { $httpProxy = $httpsProxy }
        if (-not $httpProxy -and -not $httpsProxy) { return $null }
        return @{ http = $httpProxy; https = $httpsProxy }
    }
    catch {
        return $null
    }
}

function Configure-ProxyEnvironment {
    if ($env:HTTP_PROXY -or $env:HTTPS_PROXY) {
        Write-Host "Proxy: using existing HTTP_PROXY/HTTPS_PROXY environment settings."
        return
    }

    $proxy = Get-WindowsUserProxy
    if (-not $proxy) {
        Write-Host "Proxy: no enabled Windows user proxy detected."
        return
    }

    if ($proxy.http) {
        $env:HTTP_PROXY = $proxy.http
        $env:http_proxy = $proxy.http
    }
    if ($proxy.https) {
        $env:HTTPS_PROXY = $proxy.https
        $env:https_proxy = $proxy.https
    }

    $noProxy = '127.0.0.1,localhost,::1'
    $env:NO_PROXY = $noProxy
    $env:no_proxy = $noProxy
    Write-Host "Proxy: inherited Windows user proxy for backend API access."
}

Require-Command "python" "Install Python 3.11+ and reopen PowerShell."
Require-Command "npm.cmd" "Install Node.js LTS and reopen PowerShell."

Configure-ProxyEnvironment

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
        & npm.cmd install
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
    "npm.cmd run dev -- --host 127.0.0.1"
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
