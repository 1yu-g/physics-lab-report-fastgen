param(
    [string]$Destination = "$env:USERPROFILE\.codex\skills\physics-lab-report-fastgen",
    [switch]$Update
)

$ErrorActionPreference = "Stop"
$source = Split-Path -Parent $PSScriptRoot
$items = @("SKILL.md", "agents", "scripts", "references", "requirements.txt", "requirements-analysis.txt", "requirements-ocr.txt", "requirements-figures.txt", "requirements-extended.txt", "requirements-complex.txt")

if ((Test-Path -LiteralPath $Destination) -and -not $Update) {
    throw "Destination already exists: $Destination (use -Update to refresh project files)"
}
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
foreach ($name in $items) {
    $from = Join-Path $source $name
    if (Test-Path -LiteralPath $from -PathType Leaf) {
        Copy-Item -LiteralPath $from -Destination (Join-Path $Destination $name) -Force
        continue
    }
    Get-ChildItem -LiteralPath $from -File -Recurse | ForEach-Object {
        $relative = $_.FullName.Substring($from.Length).TrimStart('\', '/')
        $target = Join-Path (Join-Path $Destination $name) $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    }
}
Write-Output "Installed to $Destination"
