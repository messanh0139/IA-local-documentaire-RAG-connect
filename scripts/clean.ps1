Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path

$targets = @(
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "logs",
    "backend\docmind.egg-info",
    "frontend\.next"
)

$pycacheDirs = Get-ChildItem -Path $ProjectRoot -Recurse -Directory -Filter "__pycache__" |
    ForEach-Object { $_.FullName }

foreach ($target in $targets + $pycacheDirs) {
    $candidate = if ([System.IO.Path]::IsPathRooted($target)) {
        $target
    } else {
        Join-Path $ProjectRoot $target
    }
    $resolved = Resolve-Path -LiteralPath $candidate -ErrorAction SilentlyContinue
    if (-not $resolved) {
        continue
    }

    $path = $resolved.Path
    if ($path -eq $root -or -not $path.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove unsafe path: $path"
    }
    Remove-Item -LiteralPath $path -Recurse -Force
}

Write-Host "Workspace cleanup complete."
