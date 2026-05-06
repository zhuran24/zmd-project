param(
    [string]$ProjectRoot = "",
    [string]$CampaignState = "E:\phase3b_workspaces\endfield_phase3b_b5_anchor_presolve_off_1h_no_warm_start_v2_20260419\data\checkpoints\exact_campaign_state.json",
    [string]$Candidate = "67x13",
    [string]$AnchorIndices = "124",
    [ValidateRange(1.0, 1000000.0)]
    [double]$TimeLimitSeconds = 300.0,
    [ValidateRange(1, 128)]
    [int]$WorkerCount = 1,
    [ValidateRange(1, 2147483647)]
    [int]$RandomSeed = 1,
    [ValidateRange(-1, 100)]
    [int]$LinearizationLevel = 0,
    [ValidateRange(1, 1000000)]
    [int]$BlockSize = 64,
    [string]$BlockTemplates = "protocol_storage_box",
    [ValidateSet("final_target", "selected_block", "selected_block_active_guard", "selected_block_active_guard_grouped_xy", "selected_block_active_guard_joined_xy")]
    [string]$BlockGeometry = "final_target",
    [ValidateSet("bounds", "delta")]
    [string]$SelectedIntervalEncoding = "bounds",
    [switch]$AllBlockTemplates,
    [string]$OutputDir = ".artifacts\phase3b_forced_anchor_proto_reduction_block64_low_encoding_anchor_probe",
    [string]$LogPath = ".codex_test_logs\phase3b\block_element_presolve_traces\block64_low_encoding_anchor_probe.log",
    [switch]$NoWrite,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = $repoRoot
}
$projectPath = [System.IO.Path]::GetFullPath($ProjectRoot)
$campaignPath = [System.IO.Path]::GetFullPath($CampaignState)
$pythonCommand = "python"
$scriptPath = Join-Path $repoRoot "scripts\build_phase3b_forced_anchor_proto_reduction.py"

function Resolve-UnderProject {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,
        [Parameter(Mandatory = $true)]
        [string]$MaybeRelative
    )

    if ([System.IO.Path]::IsPathRooted($MaybeRelative)) {
        return [System.IO.Path]::GetFullPath($MaybeRelative)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $BasePath $MaybeRelative))
}

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

$resolvedOutputDir = Resolve-UnderProject -BasePath $projectPath -MaybeRelative $OutputDir
$resolvedLogPath = Resolve-UnderProject -BasePath $projectPath -MaybeRelative $LogPath
$blockTemplateScope = "templates_" + (($BlockTemplates -replace "[^A-Za-z0-9]+", "_").Trim("_"))
if ([string]::IsNullOrWhiteSpace($blockTemplateScope) -or $blockTemplateScope -eq "templates_") {
    $blockTemplateScope = "templates_unspecified"
}
if ($AllBlockTemplates) {
    $blockTemplateScope = "all_templates"
}

$blockGeometryScope = "geometry_" + (($BlockGeometry -replace "[^A-Za-z0-9]+", "_").Trim("_"))
$selectedIntervalScope = "interval_" + (($SelectedIntervalEncoding -replace "[^A-Za-z0-9]+", "_").Trim("_"))

$solverProfile = [ordered]@{
    profile_id = "block$($BlockSize)_$($blockTemplateScope)_$($blockGeometryScope)_$($selectedIntervalScope)_low_encoding_fixed_$($WorkerCount)w"
    search_branching = "fixed"
    cp_model_probing_level = 0
    symmetry_level = 0
    worker_count = $WorkerCount
    hint_conflict_limit = 0
    random_seed = $RandomSeed
    boolean_encoding_level = 0
    max_domain_size_for_linear2_expansion = 0
    max_domain_size_when_encoding_eq_neq_constraints = 0
    cp_model_presolve = $true
    randomize_search = $false
    log_search_progress = $true
    log_to_stdout = $true
    cp_model_use_sat_presolve = $false
    find_clauses_that_are_exactly_one = $false
    presolve_use_bva = $false
}
if ($LinearizationLevel -ge 0) {
    $solverProfile["linearization_level"] = $LinearizationLevel
    $solverProfile["profile_id"] = "block$($BlockSize)_$($blockTemplateScope)_$($blockGeometryScope)_$($selectedIntervalScope)_low_encoding_linearization$($LinearizationLevel)_fixed_$($WorkerCount)w"
}
$solverProfileJson = $solverProfile | ConvertTo-Json -Compress

$effectiveEnv = @{
    "EXACT_POWER_FAMILY_LOOKUP_ENCODING" = "linear_shell_guards"
    "EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING" = "linear_minmax"
    "EXACT_POWER_COVERAGE_WITNESS_ENCODING" = "block_element"
    "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY" = $BlockGeometry
    "EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE" = ([string]$BlockSize)
    "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES" = $BlockTemplates
    "EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING" = $SelectedIntervalEncoding
    "PYTHONPATH" = "."
}
if ($AllBlockTemplates) {
    $effectiveEnv["EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES"] = ""
}

$arguments = @(
    $scriptPath,
    "--project-root", $projectPath,
    "--campaign-state", $campaignPath,
    "--candidate", $Candidate,
    "--anchor-indices", $AnchorIndices,
    "--time-limit-seconds", ([string]$TimeLimitSeconds),
    "--worker-count", ([string]$WorkerCount),
    "--variants", "base",
    "--solver-profile-json", $solverProfileJson,
    "--output-dir", $resolvedOutputDir
)
if ($NoWrite) {
    $arguments += "--no-write"
}

Write-Host "Phase 3B block-size low-encoding anchor probe"
Write-Host "Diagnostic semantics: forced-anchor probe, not proof source"
Write-Host ("Project root:   {0}" -f $projectPath)
Write-Host ("Campaign state: {0}" -f $campaignPath)
Write-Host ("Candidate:      {0}" -f $Candidate)
Write-Host ("Anchor indices: {0}" -f $AnchorIndices)
Write-Host ("Time limit:     {0} seconds" -f $TimeLimitSeconds)
Write-Host ("Output dir:     {0}" -f $resolvedOutputDir)
Write-Host ("Log path:       {0}" -f $resolvedLogPath)
Write-Host ("Solver profile: {0}" -f $solverProfileJson)
Write-Host ("Command:        {0}" -f (Format-ExactCommand -Executable $pythonCommand -Arguments $arguments -EnvOverrides $effectiveEnv))

if ($DryRun) {
    return
}

if (-not (Test-Path -LiteralPath $projectPath)) {
    throw "Project root does not exist: $projectPath"
}
if (-not (Test-Path -LiteralPath (Join-Path $projectPath "main.py"))) {
    throw "Project root does not look like the project root; missing main.py: $projectPath"
}
if (-not (Test-Path -LiteralPath $campaignPath)) {
    throw "Campaign state does not exist: $campaignPath"
}
if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "Missing proto-reduction script: $scriptPath"
}
if (-not (Get-Command $pythonCommand -ErrorAction SilentlyContinue)) {
    throw "Python executable 'python' was not found on PATH."
}

New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($resolvedLogPath)) | Out-Null

$savedEnv = @{}
foreach ($key in $effectiveEnv.Keys) {
    $savedEnv[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
}

try {
    foreach ($key in $effectiveEnv.Keys) {
        [Environment]::SetEnvironmentVariable($key, $effectiveEnv[$key], "Process")
    }
    $stdoutPath = "$resolvedLogPath.stdout.tmp"
    $stderrPath = "$resolvedLogPath.stderr.tmp"
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue

    $process = Start-Process `
        -FilePath $pythonCommand `
        -ArgumentList (ConvertTo-ProcessArgumentString -Arguments $arguments) `
        -WorkingDirectory $projectPath `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath
    $exitCode = $process.ExitCode

    $stdoutText = ""
    $stderrText = ""
    if (Test-Path -LiteralPath $stdoutPath) {
        $stdoutText = [System.IO.File]::ReadAllText($stdoutPath)
    }
    if (Test-Path -LiteralPath $stderrPath) {
        $stderrText = [System.IO.File]::ReadAllText($stderrPath)
    }
    $combinedOutput = $stdoutText
    if (-not [string]::IsNullOrWhiteSpace($stderrText)) {
        $combinedOutput = $combinedOutput + "`n[stderr]`n" + $stderrText
    }
    [System.IO.File]::WriteAllText(
        $resolvedLogPath,
        $combinedOutput,
        [System.Text.UTF8Encoding]::new($false)
    )
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue

    $combinedOutput -split "`r?`n" | Select-Object -Last 40 | ForEach-Object { Write-Host $_ }
    if ($exitCode -ne 0) {
        throw "Command failed with exit code $exitCode. See log: $resolvedLogPath"
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
