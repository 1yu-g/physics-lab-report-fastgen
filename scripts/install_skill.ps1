param(
    [string]$Destination = "$env:USERPROFILE\.codex\skills\physics-lab-report-fastgen"
)

$ErrorActionPreference = "Stop"
$source = Split-Path -Parent $PSScriptRoot

if (Test-Path -LiteralPath $Destination) {
    throw "Destination already exists: $Destination"
}

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
foreach ($name in @("SKILL.md", "agents", "scripts", "references", "requirements.txt")) {
    Copy-Item -LiteralPath (Join-Path $source $name) -Destination $Destination -Recurse
}
Write-Output "Installed to $Destination"
