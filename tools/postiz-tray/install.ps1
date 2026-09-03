# Remote Pay Guide - install Postiz tray launcher
# Run once in Windows PowerShell.

$ErrorActionPreference = 'Stop'

$InstallDir = 'C:\RemotePayGuide-tools'
$TrayScript = Join-Path $InstallDir 'PostizTray.ps1'
$RawUrl = 'https://raw.githubusercontent.com/linrui2442-blip/remote-pay-guide/main/tools/postiz-tray/PostizTray.ps1'
$Desktop = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $Desktop 'Postiz.lnk'
$PowerShellExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path 'C:\postiz-docker-compose')) {
    throw 'C:\postiz-docker-compose was not found.'
}
if (-not (Test-Path 'C:\actions-runner\run.cmd')) {
    throw 'C:\actions-runner\run.cmd was not found.'
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

Write-Host 'Downloading Postiz tray launcher...'
Invoke-WebRequest -UseBasicParsing -Uri $RawUrl -OutFile $TrayScript

# Re-save as UTF-8 with BOM for Windows PowerShell 5.1 compatibility.
$text = [System.IO.File]::ReadAllText($TrayScript, [System.Text.Encoding]::UTF8)
$utf8Bom = New-Object System.Text.UTF8Encoding($true)
[System.IO.File]::WriteAllText($TrayScript, $text, $utf8Bom)

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($ShortcutPath)
$shortcut.TargetPath = $PowerShellExe
$shortcut.Arguments = "-NoLogo -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$TrayScript`""
$shortcut.WorkingDirectory = $InstallDir
$shortcut.Description = 'Open Postiz, Docker, and the GitHub Actions runner in the system tray'
$shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,13"
$shortcut.Save()

Write-Host ''
Write-Host 'Installed successfully.'
Write-Host "Desktop shortcut: $ShortcutPath"
Write-Host "Tray launcher:    $TrayScript"
Write-Host ''
Write-Host 'Double-click the Postiz desktop shortcut to start.'
Write-Host 'Right-click the tray icon and choose Exit All to stop Runner and Postiz.'
