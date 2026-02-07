$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$DesktopDir = Join-Path $ScriptDir 'desktop'
if (!(Test-Path $DesktopDir)) {
  throw "Brak katalogu desktop: $DesktopDir"
}
Set-Location $DesktopDir

npm install
npm run dev
