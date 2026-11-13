# Windows PowerShell entry point: runs setup.sh through Git Bash.
$ErrorActionPreference = "Stop"
$bash = @(
  "$env:ProgramFiles\Git\bin\bash.exe",
  "${env:ProgramFiles(x86)}\Git\bin\bash.exe",
  "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $bash) {
  Write-Host "Git for Windows (Git Bash) is required. Install: winget install Git.Git" -ForegroundColor Red
  exit 1
}
Set-Location $PSScriptRoot
& $bash ./setup.sh
