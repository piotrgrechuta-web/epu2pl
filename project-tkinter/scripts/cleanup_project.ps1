param(
    [switch]$Apply,
    [int]$KeepBuilds = 8
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

function Ensure-Dir([string]$Path) {
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Move-IfExists([string]$Source, [string]$TargetDir) {
    $items = Get-ChildItem -Path $Source -ErrorAction SilentlyContinue
    if (-not $items) { return @() }
    Ensure-Dir $TargetDir
    $moved = @()
    foreach ($item in $items) {
        $dest = Join-Path $TargetDir $item.Name
        if ($Apply) {
            Move-Item -Path $item.FullName -Destination $dest -Force
        }
        $moved += [PSCustomObject]@{
            Type = if ($item.PSIsContainer) { "dir" } else { "file" }
            Source = $item.FullName
            Destination = $dest
        }
    }
    return $moved
}

function Remove-IfExists([string]$Path) {
    if (Test-Path $Path) {
        if ($Apply) {
            Remove-Item -Path $Path -Recurse -Force
        }
        return $true
    }
    return $false
}

$dirs = @(
    "artifacts",
    "artifacts/builds",
    "artifacts/backups",
    "artifacts/logs",
    "artifacts/debug",
    "artifacts/tmp",
    "data",
    "data/cache",
    "data/epub",
    "data/db"
)
foreach ($d in $dirs) { Ensure-Dir $d }

$report = @()

# Root artifacts
$report += Move-IfExists "*.zip" "artifacts/builds"
$report += Move-IfExists "cache_*.jsonl" "data/cache"
$report += Move-IfExists "*.epub" "data/epub"
$report += Move-IfExists "translator_studio.db.bak-*" "artifacts/backups"
$report += Move-IfExists "translator_studio.db.bak-v*" "artifacts/backups"

# Debug/event artifacts
if (Test-Path "debug") {
    $report += Move-IfExists "debug\*" "artifacts/debug"
}
if (Test-Path "events") {
    $report += Move-IfExists "events\*" "artifacts/logs"
}

# Temporary clutter
$removed = @()
if (Remove-IfExists ".pytest_cache") { $removed += ".pytest_cache" }
if (Remove-IfExists "__pycache__") { $removed += "__pycache__" }
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($Apply) { Remove-Item -Path $_.FullName -Recurse -Force }
    $removed += $_.FullName
}

# Stray zero-byte API-like files in root (e.g. accidental paste)
Get-ChildItem -Path . -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Length -eq 0 -and $_.Name -match "^(AIza|sk-|api[_-]?key)"
} | ForEach-Object {
    $dest = Join-Path "artifacts/tmp" $_.Name
    if ($Apply) { Move-Item -Path $_.FullName -Destination $dest -Force }
    $report += [PSCustomObject]@{
        Type = "file"
        Source = $_.FullName
        Destination = (Resolve-Path $dest).Path
    }
}

# Keep only newest N runtime/build zips
$buildDir = Join-Path $ProjectRoot "artifacts/builds"
$builds = Get-ChildItem -Path $buildDir -File -Filter "*.zip" | Sort-Object LastWriteTime -Descending
if ($builds.Count -gt $KeepBuilds) {
    $toDelete = $builds | Select-Object -Skip $KeepBuilds
    foreach ($b in $toDelete) {
        if ($Apply) { Remove-Item -Path $b.FullName -Force }
        $removed += $b.FullName
    }
}

Write-Host ""
Write-Host "Cleanup mode: $([string]($(if($Apply){'APPLY'} else {'DRY-RUN'})))"
Write-Host "Project root: $ProjectRoot"
Write-Host ""

if ($report.Count -gt 0) {
    Write-Host "Moved items:"
    $report | Sort-Object Source | ForEach-Object {
        Write-Host (" - {0} -> {1}" -f $_.Source, $_.Destination)
    }
} else {
    Write-Host "Moved items: none"
}

if ($removed.Count -gt 0) {
    Write-Host ""
    Write-Host "Removed items:"
    $removed | Sort-Object | ForEach-Object { Write-Host (" - {0}" -f $_) }
}

Write-Host ""
Write-Host "Done."
