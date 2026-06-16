param(
    [string]$WorkspaceRoot = "E:\phase3b_workspaces\endfield_phase3b_b5_anchor_presolve_off_diagnostic",
    [double]$CampaignHours = 0.25,
    [int]$MaxAttempts = 1,
    [double]$MasterSeconds = 300.0,
    [double]$BindingSeconds = 30.0,
    [double]$RoutingSeconds = 30.0,
    [int]$BendersMaxIter = 1,
    [int]$WallTimeoutSeconds = 1200,
    [switch]$ResumeCampaign,
    [switch]$DisableMasterWarmStart,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$runner = Join-Path $PSScriptRoot "run_phase3b_b5_anchor_sprint.ps1"
if (-not (Test-Path -LiteralPath $runner)) {
    throw "Missing B5A runner: $runner"
}

$runnerArgs = @(
    "-ExecutionPolicy", "Bypass",
    "-File", $runner,
    "-WorkspaceRoot", $WorkspaceRoot,
    "-CampaignHours", ([string]$CampaignHours),
    "-MaxAttempts", ([string]$MaxAttempts),
    "-MasterSeconds", ([string]$MasterSeconds),
    "-BindingSeconds", ([string]$BindingSeconds),
    "-RoutingSeconds", ([string]$RoutingSeconds),
    "-BendersMaxIter", ([string]$BendersMaxIter),
    "-FrontierProbeMaxAnchors", "256",
    "-BoundaryPortPrecheckMaxAnchors", "256",
    "-MandatoryRectanglePrecheckMaxAnchors", "256",
    "-MandatoryRectanglePrecheckTimeBudgetSeconds", "180",
    "-CoordinateValidationPrecheckMaxAnchors", "0",
    "-CoordinateValidationPrecheckSeconds", "2",
    "-GhostAwareCoordinateValidationMaxAnchors", "8",
    "-GhostAwareCoordinateValidationSeconds", "10",
    "-FailedAnchorSampleLimit", "128",
    "-MasterSearchProfile", "exact_coordinate_guided_branching_v4",
    "-MasterSearchBranching", "fixed",
    "-DisableMasterPresolve",
    "-MasterCpModelProbingLevel", "0",
    "-MasterSymmetryLevel", "0",
    "-MasterHintConflictLimit", "0",
    "-WallTimeoutSeconds", ([string]$WallTimeoutSeconds)
)
if ($ResumeCampaign) {
    $runnerArgs += "-ResumeCampaign"
}
if ($DisableMasterWarmStart) {
    $runnerArgs += "-DisableMasterWarmStart"
}
if ($DryRun) {
    $runnerArgs += "-DryRun"
}

& powershell @runnerArgs
