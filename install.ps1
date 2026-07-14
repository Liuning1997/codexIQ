$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSCommandPath
$pythonw = (Get-Command pythonw.exe -ErrorAction Stop).Source
$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'Codex Radar Watcher.lnk'

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = '"' + (Join-Path $project 'watcher.py') + '"'
$shortcut.WorkingDirectory = $project
$shortcut.WindowStyle = 7
$shortcut.Description = 'Show Codex Radar while Codex is running'
$shortcut.Save()

$existing = Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" | Where-Object { $_.CommandLine -like '*watcher.py*' } | Select-Object -First 1
if (-not $existing) {
    Start-Process -FilePath $pythonw -ArgumentList ('"' + (Join-Path $project 'watcher.py') + '"') -WorkingDirectory $project -WindowStyle Hidden
}

Write-Output "Installed startup watcher: $shortcutPath"
