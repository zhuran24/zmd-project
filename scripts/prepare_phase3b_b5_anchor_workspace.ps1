param(
    [string]$TargetRoot = "E:\phase3b_workspaces\endfield_phase3b_b5_anchor_20260417",
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$targetPath = [System.IO.Path]::GetFullPath($TargetRoot)
$targetParent = Split-Path -Parent $targetPath

function Write-DriveSummary {
    Get-PSDrive -PSProvider FileSystem |
        Where-Object { $_.Name -in @("C", "D", "E") } |
        Sort-Object Name |
        ForEach-Object {
            Write-Host ("Drive {0}: free={1:N2}GB used={2:N2}GB" -f $_.Name, ($_.Free / 1GB), ($_.Used / 1GB))
        }
}

Write-Host ("Source root: {0}" -f $sourceRoot)
Write-Host ("Target root: {0}" -f $targetPath)
Write-DriveSummary

if (Test-Path -LiteralPath $targetPath) {
    throw "Target workspace already exists; refusing to overwrite: $targetPath"
}

if ($DryRun) {
    Write-Host "Dry run: would create parent directory and copy the current project to the target workspace."
    return
}

if (-not (Test-Path -LiteralPath $targetParent)) {
    New-Item -ItemType Directory -Path $targetParent | Out-Null
}

Copy-Item -LiteralPath $sourceRoot -Destination $targetPath -Recurse -Container
Write-Host ("Workspace prepared: {0}" -f $targetPath)
