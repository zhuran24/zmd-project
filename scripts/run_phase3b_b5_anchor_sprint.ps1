param(
    [string]$WorkspaceRoot = "E:\phase3b_workspaces\endfield_phase3b_b5_anchor_20260417",
    [double]$CampaignHours = 1.0,
    [int]$MaxAttempts = 2,
    [double]$MasterSeconds = 30.0,
    [double]$BindingSeconds = 30.0,
    [double]$RoutingSeconds = 30.0,
    [int]$BendersMaxIter = 1,
    [ValidateRange(0, 1000000)]
    [int]$FrontierProbeMaxAnchors = 256,
    [ValidateRange(0, 1000000)]
    [int]$BoundaryPortPrecheckMaxAnchors = 256,
    [ValidateRange(0, 1000000)]
    [int]$MandatoryRectanglePrecheckMaxAnchors = 256,
    [ValidateRange(0.0, 1000000.0)]
    [double]$MandatoryRectanglePrecheckTimeBudgetSeconds = 180.0,
    [ValidateRange(0, 1000000)]
    [int]$CoordinateValidationPrecheckMaxAnchors = 0,
    [ValidateRange(0.0, 1000000.0)]
    [double]$CoordinateValidationPrecheckSeconds = 2.0,
    [ValidateRange(0, 1000000)]
    [int]$GhostAwareCoordinateValidationMaxAnchors = 8,
    [ValidateRange(0.0, 1000000.0)]
    [double]$GhostAwareCoordinateValidationSeconds = 10.0,
    [ValidateRange(0.0, 1000000.0)]
    [double]$GhostAwarePoseOrderValidationSeconds = 2.0,
    [ValidateRange(0, 1000000)]
    [int]$FailedAnchorSampleLimit = 128,
    [ValidateSet("exact_coordinate_guided_branching_v4", "exact_coordinate_ghost_after_counts_v1", "exact_coordinate_ghost_first_v1")]
    [string]$MasterSearchProfile = "exact_coordinate_guided_branching_v4",
    [ValidateSet("fixed", "automatic", "portfolio")]
    [string]$MasterSearchBranching = "fixed",
    [ValidateSet("default", "selected_block_block64_all_templates", "joined_xy_block64_all_templates")]
    [string]$FormulationProfile = "default",
    [switch]$EnableGhostAwareNoSolvePrechecks,
    [switch]$DisableMasterPresolve,
    [int]$MasterCpModelProbingLevel = -1,
    [int]$MasterSymmetryLevel = -1,
    [int]$MasterHintConflictLimit = -1,
    [switch]$DisableMasterWarmStart,
    [int]$WallTimeoutSeconds = 0,
    [switch]$ResumeCampaign,
    [switch]$ValidateWorkspaceOnly,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$workspacePath = [System.IO.Path]::GetFullPath($WorkspaceRoot)
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonCommand = "python"

function Format-ExactCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [hashtable]$EnvOverrides = @{}
    )

    $parts = @()
    foreach ($entry in ($EnvOverrides.GetEnumerator() | Sort-Object Name)) {
        $parts += "$($entry.Name)=$($entry.Value)"
    }
    $parts += $Executable
    foreach ($argument in $Arguments) {
        if ($argument -match '[\s"]') {
            $escaped = $argument.Replace('"', '\"')
            $parts += "`"$escaped`""
        } else {
            $parts += $argument
        }
    }
    return ($parts -join " ")
}

function ConvertTo-ProcessArgumentString {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $parts = @()
    foreach ($argument in $Arguments) {
        if ($argument -match '[\s"]') {
            $escaped = $argument.Replace('\', '\\').Replace('"', '\"')
            $parts += "`"$escaped`""
        } else {
            $parts += $argument
        }
    }
    return ($parts -join " ")
}

function Test-FileContainsAll {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string[]]$Markers
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $text = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    foreach ($marker in $Markers) {
        if (-not $text.Contains($marker)) {
            return $false
        }
    }
    return $true
}

$arguments = @(
    "main.py",
    "--mode", "certified_exact",
    "--campaign-hours", ([string]$CampaignHours),
    "--max-attempts", ([string]$MaxAttempts),
    "--master-seconds", ([string]$MasterSeconds),
    "--binding-seconds", ([string]$BindingSeconds),
    "--routing-seconds", ([string]$RoutingSeconds),
    "--benders-max-iter", ([string]$BendersMaxIter),
    "--master-search-profile", $MasterSearchProfile,
    "--parallel-processes", "1",
    "--process-priority", "normal",
    "--frontier-probe-mode", "auto"
)

if ($ResumeCampaign) {
    $arguments += "--resume-campaign"
}
if ($DisableMasterWarmStart) {
    $arguments += "--disable-master-warm-start"
}

if ($WallTimeoutSeconds -le 0) {
    $attemptCountForTimeout = [Math]::Max(1, $MaxAttempts)
    $iterationCountForTimeout = [Math]::Max(1, $BendersMaxIter)
    $coordinateValidationBudgetSeconds = [Math]::Max(0.0, $CoordinateValidationPrecheckSeconds) * [Math]::Max(0, $CoordinateValidationPrecheckMaxAnchors)
    $ghostAwareCoordinateValidationBudgetSeconds = [Math]::Max(0.0, $GhostAwareCoordinateValidationSeconds) * [Math]::Max(0, $GhostAwareCoordinateValidationMaxAnchors)
    $ghostAwarePoseOrderValidationBudgetSeconds = [Math]::Max(0.0, $GhostAwarePoseOrderValidationSeconds) * [Math]::Max(0, $GhostAwareCoordinateValidationMaxAnchors)
    $stageBudgetSeconds = (
        [Math]::Max(0.0, $MasterSeconds) +
        [Math]::Max(0.0, $BindingSeconds) +
        [Math]::Max(0.0, $RoutingSeconds) +
        [Math]::Max(0.0, $MandatoryRectanglePrecheckTimeBudgetSeconds) +
        $coordinateValidationBudgetSeconds +
        $ghostAwareCoordinateValidationBudgetSeconds +
        $ghostAwarePoseOrderValidationBudgetSeconds
    ) * $iterationCountForTimeout * $attemptCountForTimeout
    $campaignWallBudgetSeconds = ($CampaignHours * 3600.0) + 300.0
    $WallTimeoutSeconds = [int][Math]::Ceiling([Math]::Min($campaignWallBudgetSeconds, $stageBudgetSeconds + 300.0))
}

$effectiveEnv = @{
    "EXACT_CP_SAT_WORKERS" = "1"
    "EXACT_FRONTIER_PROBE_MAX_ANCHORS" = ([string]$FrontierProbeMaxAnchors)
    "EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS" = ([string]$BoundaryPortPrecheckMaxAnchors)
    "EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS" = ([string]$MandatoryRectanglePrecheckMaxAnchors)
    "EXACT_MANDATORY_RECTANGLE_PRECHECK_TIME_BUDGET_SECONDS" = ([string]$MandatoryRectanglePrecheckTimeBudgetSeconds)
    "EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS" = ([string]$CoordinateValidationPrecheckMaxAnchors)
    "EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS" = ([string]$CoordinateValidationPrecheckSeconds)
    "EXACT_GHOST_AWARE_COORDINATE_VALIDATION_MAX_ANCHORS" = ([string]$GhostAwareCoordinateValidationMaxAnchors)
    "EXACT_GHOST_AWARE_COORDINATE_VALIDATION_SECONDS" = ([string]$GhostAwareCoordinateValidationSeconds)
    "EXACT_GHOST_AWARE_POSE_ORDER_VALIDATION_SECONDS" = ([string]$GhostAwarePoseOrderValidationSeconds)
    "EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT" = ([string]$FailedAnchorSampleLimit)
    "EXACT_MASTER_SEARCH_BRANCHING" = $MasterSearchBranching
    "PYTHONPATH" = "."
}

if ($FormulationProfile -eq "selected_block_block64_all_templates") {
    $effectiveEnv["EXACT_POWER_FAMILY_LOOKUP_ENCODING"] = "linear_shell_guards"
    $effectiveEnv["EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING"] = "linear_minmax"
    $effectiveEnv["EXACT_POWER_COVERAGE_WITNESS_ENCODING"] = "block_element"
    $effectiveEnv["EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY"] = "selected_block"
    $effectiveEnv["EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE"] = "64"
    $effectiveEnv["EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES"] = ""
}
if ($FormulationProfile -eq "joined_xy_block64_all_templates") {
    $effectiveEnv["EXACT_POWER_FAMILY_LOOKUP_ENCODING"] = "linear_shell_guards"
    $effectiveEnv["EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING"] = "linear_minmax"
    $effectiveEnv["EXACT_POWER_COVERAGE_WITNESS_ENCODING"] = "block_element"
    $effectiveEnv["EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY"] = "selected_block_active_guard_joined_xy"
    $effectiveEnv["EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE"] = "64"
    $effectiveEnv["EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES"] = ""
}

if ($EnableGhostAwareNoSolvePrechecks) {
    $effectiveEnv["EXACT_GHOST_OVERLAP_FORCED_DOMAIN_PRECHECK"] = "true"
    $effectiveEnv["EXACT_SIGNATURE_MONOTONIC_FORCED_LABEL_PRECHECK"] = "true"
}

if ($DisableMasterPresolve) {
    $effectiveEnv["EXACT_MASTER_CP_MODEL_PRESOLVE"] = "false"
}
if ($MasterCpModelProbingLevel -ge 0) {
    $effectiveEnv["EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] = ([string]$MasterCpModelProbingLevel)
}
if ($MasterSymmetryLevel -ge 0) {
    $effectiveEnv["EXACT_MASTER_SYMMETRY_LEVEL"] = ([string]$MasterSymmetryLevel)
}
if ($MasterHintConflictLimit -ge 0) {
    $effectiveEnv["EXACT_MASTER_HINT_CONFLICT_LIMIT"] = ([string]$MasterHintConflictLimit)
}

Write-Host ("Repo root:      {0}" -f $repoRoot)
Write-Host ("Workspace root: {0}" -f $workspacePath)
Write-Host ("Command:        {0}" -f (Format-ExactCommand -Executable $pythonCommand -Arguments $arguments -EnvOverrides $effectiveEnv))
Write-Host ("Stage budgets:  master={0}s binding={1}s routing={2}s benders_iter={3} max_attempts={4} master_profile={5} master_branching={6}" -f $MasterSeconds, $BindingSeconds, $RoutingSeconds, $BendersMaxIter, $MaxAttempts, $MasterSearchProfile, $MasterSearchBranching)
Write-Host ("Master params:  disable_presolve={0} cp_model_probing={1} symmetry={2} hint_conflict_limit={3}" -f ([bool]$DisableMasterPresolve), $MasterCpModelProbingLevel, $MasterSymmetryLevel, $MasterHintConflictLimit)
Write-Host ("Formulation:    profile={0}" -f $FormulationProfile)
Write-Host ("Diagnostic semantics: B5A bounded workspace sprint; formulation profiles are not proof source, not production readiness, and not candidate elimination.")
Write-Host ("No-solve prechecks: ghost_aware={0}" -f ([bool]$EnableGhostAwareNoSolvePrechecks))
Write-Host ("Precheck caps:  frontier_probe={0} boundary_port={1} mandatory_rectangle={2} mandatory_rectangle_time_budget={3}s coordinate_validation={4} coordinate_validation_seconds={5}s failed_anchor_samples={6}" -f $FrontierProbeMaxAnchors, $BoundaryPortPrecheckMaxAnchors, $MandatoryRectanglePrecheckMaxAnchors, $MandatoryRectanglePrecheckTimeBudgetSeconds, $CoordinateValidationPrecheckMaxAnchors, $CoordinateValidationPrecheckSeconds, $FailedAnchorSampleLimit)
Write-Host ("Warm-start caps: ghost_aware_coordinate_validation={0} ghost_aware_coordinate_validation_seconds={1}s ghost_aware_pose_order_validation_seconds={2}s" -f $GhostAwareCoordinateValidationMaxAnchors, $GhostAwareCoordinateValidationSeconds, $GhostAwarePoseOrderValidationSeconds)
Write-Host ("Wall timeout:   {0} seconds" -f $WallTimeoutSeconds)

if ($DryRun -and -not $ValidateWorkspaceOnly) {
    return
}

if (-not (Test-Path -LiteralPath $workspacePath)) {
    throw "Workspace root does not exist: $workspacePath"
}

$mainPath = Join-Path $workspacePath "main.py"
if (-not (Test-Path -LiteralPath $mainPath)) {
    throw "Workspace root does not look like the project root; missing main.py: $mainPath"
}

if ($workspacePath -eq $repoRoot) {
    throw "Refusing to run B5A anchor sprint in the repo main path; use a workspace copy."
}

$workspaceExactCoordinateMaster = Join-Path $workspacePath "src\models\exact_coordinate_master.py"
if ($FormulationProfile -eq "joined_xy_block64_all_templates") {
    $supportsJoinedXy = Test-FileContainsAll `
        -Path $workspaceExactCoordinateMaster `
        -Markers @(
            "selected_block_active_guard_joined_xy",
            "cover_choice_joined_x__",
            "joined_xy_target_channel_count"
        )
    if (-not $supportsJoinedXy) {
        $messageTemplate = (
            "Requested -FormulationProfile joined_xy_block64_all_templates, but workspace source does not support joined-XY. " +
            "workspace_exact_coordinate_master={0}. Refresh/create a workspace from the current repo before rerunning B5A."
        )
        throw ($messageTemplate -f $workspaceExactCoordinateMaster)
    }
    $repoExactCoordinateMaster = Join-Path $repoRoot "src\models\exact_coordinate_master.py"
    if ((Test-Path -LiteralPath $repoExactCoordinateMaster) -and (Test-Path -LiteralPath $workspaceExactCoordinateMaster)) {
        $repoHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $repoExactCoordinateMaster).Hash
        $workspaceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $workspaceExactCoordinateMaster).Hash
        Write-Host ("Formulation provenance: repo_exact_coordinate_master_sha256={0} workspace_exact_coordinate_master_sha256={1} source_matches_repo={2}" -f $repoHash, $workspaceHash, ($repoHash -eq $workspaceHash))
    }
}

if ($EnableGhostAwareNoSolvePrechecks) {
    $workspaceMasterModel = Join-Path $workspacePath "src\models\master_model.py"
    $supportsGhostOverlap = Test-FileContainsAll `
        -Path $workspaceMasterModel `
        -Markers @(
            "EXACT_GHOST_OVERLAP_FORCED_DOMAIN_PRECHECK",
            "evaluate_ghost_overlap_forced_domain_conflict"
        )
    $supportsSignatureMonotonic = Test-FileContainsAll `
        -Path $workspaceMasterModel `
        -Markers @(
            "EXACT_SIGNATURE_MONOTONIC_FORCED_LABEL_PRECHECK",
            "evaluate_signature_monotonic_forced_label_conflict"
    )
    if (-not ($supportsGhostOverlap -and $supportsSignatureMonotonic)) {
        $messageTemplate = (
            "Requested -EnableGhostAwareNoSolvePrechecks, but workspace source does not support all requested prechecks. " +
            "ghost_overlap_forced_domain={0}; signature_monotonic_forced_label={1}; workspace_master_model={2}. " +
            "Refresh/create a workspace from the current repo before rerunning B5A."
        )
        $message = $messageTemplate -f `
            $supportsGhostOverlap, $supportsSignatureMonotonic, $workspaceMasterModel
        throw $message
    }
    $repoMasterModel = Join-Path $repoRoot "src\models\master_model.py"
    if ((Test-Path -LiteralPath $repoMasterModel) -and (Test-Path -LiteralPath $workspaceMasterModel)) {
        $repoHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $repoMasterModel).Hash
        $workspaceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $workspaceMasterModel).Hash
        Write-Host ("Source provenance: repo_master_model_sha256={0} workspace_master_model_sha256={1} source_matches_repo={2}" -f $repoHash, $workspaceHash, ($repoHash -eq $workspaceHash))
    }
}

if ($ValidateWorkspaceOnly) {
    Write-Host ("Workspace validation: passed for {0}" -f $workspacePath)
    return
}

if (-not (Get-Command $pythonCommand -ErrorAction SilentlyContinue)) {
    throw "Python executable 'python' was not found on PATH."
}

$savedEnv = @{}
foreach ($key in $effectiveEnv.Keys) {
    $savedEnv[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
}

try {
    foreach ($key in $effectiveEnv.Keys) {
        [Environment]::SetEnvironmentVariable($key, $effectiveEnv[$key], "Process")
    }

    Push-Location $workspacePath
    try {
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $pythonCommand
        $startInfo.Arguments = ConvertTo-ProcessArgumentString -Arguments $arguments
        $startInfo.WorkingDirectory = $workspacePath
        $startInfo.UseShellExecute = $false

        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $startInfo
        if (-not $process.Start()) {
            throw "Failed to start B5A anchor sprint process."
        }
        $completed = $process.WaitForExit([int]($WallTimeoutSeconds * 1000))
        if (-not $completed) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            & $pythonCommand `
                (Join-Path $repoRoot "scripts\mark_phase3b_campaign_interrupted.py") `
                --project-root $workspacePath `
                --reason "b5a_wall_timeout" `
                --detail ("B5A runner exceeded wall timeout of {0} seconds." -f $WallTimeoutSeconds)
            throw "B5A anchor sprint exceeded wall timeout of $WallTimeoutSeconds seconds."
        }
        $process.WaitForExit()
        $process.Refresh()
        $exitCode = $process.ExitCode
    } finally {
        Pop-Location
    }

    if ($exitCode -ne 0) {
        throw "Command failed with exit code $exitCode."
    }
} finally {
    foreach ($key in $effectiveEnv.Keys) {
        $previousValue = $savedEnv[$key]
        if ($null -eq $previousValue) {
            [Environment]::SetEnvironmentVariable($key, $null, "Process")
        } else {
            [Environment]::SetEnvironmentVariable($key, $previousValue, "Process")
        }
    }
}
