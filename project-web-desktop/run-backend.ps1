param(
  [int]$Port = 8765,
  [switch]$NoVenv
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$BackendDir = Join-Path $ScriptDir 'backend'
if (!(Test-Path $BackendDir)) {
  throw "Brak katalogu backend: $BackendDir"
}
Set-Location $BackendDir

$Py = 'python'
if (-not $NoVenv) {
  $VenvDir = Join-Path $BackendDir '.venv'
  if (!(Test-Path $VenvDir)) {
    & $Py -m venv .venv
  }
  $Py = Join-Path $VenvDir 'Scripts\\python.exe'
  if (!(Test-Path $Py)) {
    throw "Brak interpretera venv: $Py"
  }
}

& $Py -m pip install -r requirements.txt
& $Py -m uvicorn app:app --reload --port $Port
