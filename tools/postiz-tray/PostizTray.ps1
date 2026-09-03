# Remote Pay Guide - Postiz tray launcher
# Windows PowerShell 5.1 compatible; intentionally ASCII-only for reliable decoding.

$ErrorActionPreference = 'Stop'

$PostizDir = 'C:\postiz-docker-compose'
$RunnerDir = 'C:\actions-runner'
$InstallDir = 'C:\RemotePayGuide-tools'
$RunnerLog = Join-Path $InstallDir 'runner.log'
$PostizUrl = 'http://localhost:4007'
$DockerDesktopExe = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
$DockerCliExe = 'C:\Program Files\Docker\Docker\DockerCli.exe'

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Open-Postiz {
    Start-Process $PostizUrl
}

function Test-DockerEngine {
    try {
        & docker info *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Test-Postiz {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $PostizUrl -TimeoutSec 4
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
    } catch {
        return $false
    }
}

function Get-RunnerProcesses {
    try {
        return @(Get-Process -Name 'Runner.Listener','Runner.Worker' -ErrorAction SilentlyContinue)
    } catch {
        return @()
    }
}

function Test-Runner {
    try {
        return (@(Get-Process -Name 'Runner.Listener' -ErrorAction SilentlyContinue).Count -gt 0)
    } catch {
        return $false
    }
}

function Show-TrayMessage([string]$title, [string]$message, [System.Windows.Forms.ToolTipIcon]$icon = [System.Windows.Forms.ToolTipIcon]::Info) {
    if ($script:NotifyIcon) {
        $script:NotifyIcon.BalloonTipTitle = $title
        $script:NotifyIcon.BalloonTipText = $message
        $script:NotifyIcon.BalloonTipIcon = $icon
        $script:NotifyIcon.ShowBalloonTip(4000)
    }
}

function Wait-DockerEngine([int]$seconds = 120) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        [System.Windows.Forms.Application]::DoEvents()
        if (Test-DockerEngine) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Wait-Postiz([int]$seconds = 120) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        [System.Windows.Forms.Application]::DoEvents()
        if (Test-Postiz) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Start-DockerIfNeeded {
    if (Test-DockerEngine) {
        $script:DockerStartedByTray = $false
        return
    }

    if (-not (Test-Path $DockerDesktopExe)) {
        throw "Docker Desktop was not found at $DockerDesktopExe"
    }

    $script:DockerStartedByTray = $true
    $script:NotifyIcon.Text = 'Postiz - starting Docker'
    Show-TrayMessage 'Postiz' 'Starting Docker Desktop...'
    Start-Process -FilePath $DockerDesktopExe | Out-Null

    if (-not (Wait-DockerEngine 120)) {
        throw 'Docker Engine did not become ready within 120 seconds.'
    }
}

function Start-PostizIfNeeded {
    if (-not (Test-Path $PostizDir)) {
        throw "Postiz folder was not found at $PostizDir"
    }

    $script:NotifyIcon.Text = 'Postiz - starting containers'
    Push-Location $PostizDir
    try {
        & docker compose up -d
        if ($LASTEXITCODE -ne 0) { throw 'docker compose up -d failed.' }
    } finally {
        Pop-Location
    }

    if (-not (Wait-Postiz 120)) {
        throw 'Postiz did not become reachable on localhost:4007 within 120 seconds.'
    }
}

function Start-RunnerIfNeeded {
    if (Test-Runner) {
        return
    }

    $runCmd = Join-Path $RunnerDir 'run.cmd'
    if (-not (Test-Path $runCmd)) {
        throw "GitHub Actions runner was not found at $runCmd"
    }

    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    }
    Remove-Item $RunnerLog -Force -ErrorAction SilentlyContinue

    $script:NotifyIcon.Text = 'Postiz - starting runner'
    $command = "call `"$runCmd`" >> `"$RunnerLog`" 2>&1"
    Start-Process -FilePath $env:ComSpec -ArgumentList '/d','/c',$command -WorkingDirectory $RunnerDir -WindowStyle Hidden | Out-Null

    $deadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $deadline) {
        [System.Windows.Forms.Application]::DoEvents()
        if (Test-Runner) { return }
        Start-Sleep -Seconds 1
    }

    $details = ''
    if (Test-Path $RunnerLog) {
        try {
            $tail = @(Get-Content $RunnerLog -Tail 20 -ErrorAction SilentlyContinue)
            if ($tail.Count -gt 0) { $details = "`n`nRunner log:`n" + ($tail -join "`n") }
        } catch {}
    }
    throw ('GitHub Actions runner did not start within 45 seconds.' + $details)
}

function Stop-Runner {
    foreach ($proc in @(Get-RunnerProcesses)) {
        try {
            & taskkill.exe /PID $proc.Id /T /F *> $null
        } catch {
            try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
        }
    }
}

function Stop-Postiz {
    if (-not (Test-Path $PostizDir)) { return }
    Push-Location $PostizDir
    try {
        & docker compose stop *> $null
    } catch {
    } finally {
        Pop-Location
    }
}

function Stop-DockerIfOwned {
    if (-not $script:DockerStartedByTray) { return }
    try {
        if (Test-Path $DockerCliExe) {
            & $DockerCliExe -Shutdown *> $null
        }
    } catch {}
}

function Show-Status {
    $docker = if (Test-DockerEngine) { 'ON' } else { 'OFF' }
    $postiz = if (Test-Postiz) { 'ON' } else { 'OFF' }
    $runner = if (Test-Runner) { 'ON' } else { 'OFF' }
    Show-TrayMessage 'Postiz status' "Docker: $docker`nPostiz: $postiz`nRunner: $runner"
}

function Stop-AllAndExit {
    if ($script:Stopping) { return }
    $script:Stopping = $true
    $script:NotifyIcon.Text = 'Postiz - stopping'
    Show-TrayMessage 'Postiz' 'Stopping Runner and Postiz...'

    try { Stop-Runner } catch {}
    try { Stop-Postiz } catch {}
    try { Stop-DockerIfOwned } catch {}

    $script:NotifyIcon.Visible = $false
    [System.Windows.Forms.Application]::ExitThread()
}

# Single instance. Double-clicking the desktop shortcut again simply opens Postiz.
$createdNew = $false
$script:Mutex = New-Object System.Threading.Mutex($true, 'RemotePayGuide_PostizTray', [ref]$createdNew)
if (-not $createdNew) {
    Open-Postiz
    exit 0
}

$script:DockerStartedByTray = $false
$script:Stopping = $false
$script:NotifyIcon = New-Object System.Windows.Forms.NotifyIcon
$script:NotifyIcon.Icon = [System.Drawing.SystemIcons]::Application
$script:NotifyIcon.Text = 'Postiz - starting'
$script:NotifyIcon.Visible = $true

$menu = New-Object System.Windows.Forms.ContextMenuStrip
$openItem = $menu.Items.Add('Open Postiz')
$statusItem = $menu.Items.Add('Status')
[void]$menu.Items.Add('-')
$exitItem = $menu.Items.Add('Exit All')

$openItem.add_Click({ Open-Postiz })
$statusItem.add_Click({ Show-Status })
$exitItem.add_Click({ Stop-AllAndExit })
$script:NotifyIcon.ContextMenuStrip = $menu
$script:NotifyIcon.add_DoubleClick({ Open-Postiz })

try {
    Start-DockerIfNeeded
    Start-PostizIfNeeded
    Start-RunnerIfNeeded

    $script:NotifyIcon.Text = 'Postiz - ready'
    Show-TrayMessage 'Postiz ready' 'Postiz and GitHub Runner are running. Right-click this tray icon to Exit All.'
    Open-Postiz

    [System.Windows.Forms.Application]::Run()
} catch {
    $message = $_.Exception.Message
    Show-TrayMessage 'Postiz startup failed' $message ([System.Windows.Forms.ToolTipIcon]::Error)
    [System.Windows.Forms.MessageBox]::Show($message, 'Postiz startup failed', 'OK', 'Error') | Out-Null
    try { Stop-Runner } catch {}
    try { Stop-DockerIfOwned } catch {}
} finally {
    if ($script:NotifyIcon) {
        $script:NotifyIcon.Visible = $false
        $script:NotifyIcon.Dispose()
    }
    if ($menu) { $menu.Dispose() }
    if ($script:Mutex) {
        try { $script:Mutex.ReleaseMutex() } catch {}
        $script:Mutex.Dispose()
    }
}
