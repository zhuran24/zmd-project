<#
.SYNOPSIS
    Crash-resume accumulation loop for Phase 3B exact solver.

.DESCRIPTION
    Runs the solver with built-in defaults (8/8/4/8) in a loop.
    Each iteration uses --resume-campaign to pick up where the last crash left off.
    Dual purpose: (1) accumulate campaign progress, (2) collect AI training data.

    The solver will crash every ~10-15 min due to 48 GiB RAM ceiling.
    Memory guardian kills it if system available RAM < 4 GiB.
    Between crashes, 90 second cooldown to let memory fully reclaim.

.PARAMETER MaxIterations
    Maximum number of crash-resume cycles (default: 200, ~30-50 hours of wall time).

.PARAMETER CooldownSeconds
    Seconds to wait between crashes for memory reclaim (default: 30).

.PARAMETER Profile
    Tuning profile to use (default: accumulation_builtin_24h).

.EXAMPLE
    .\scripts\run_accumulation_loop.ps1
    .\scripts\run_accumulation_loop.ps1 -MaxIterations 50
    .\scripts\run_accumulation_loop.ps1 -CooldownSeconds 60
#>

param(
    [int]$MaxIterations = 200,
    [int]$CooldownSeconds = 90,
    [string]$Profile = "accumulation_builtin_24h"
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path "$ProjectRoot\main.py")) {
    Write-Error "Cannot find project root (main.py not found)"
    exit 1
}

Set-Location $ProjectRoot
$startTime = Get-Date
$totalCandidates = 0
$totalCrashes = 0
$totalOomKills = 0

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Phase 3B Accumulation Loop" -ForegroundColor Cyan
Write-Host "  Profile: $Profile" -ForegroundColor Cyan
Write-Host "  Max iterations: $MaxIterations" -ForegroundColor Cyan
Write-Host "  Cooldown: ${CooldownSeconds}s" -ForegroundColor Cyan
Write-Host "  Started: $($startTime.ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor Cyan
Write-Host "  Press Ctrl+C to stop gracefully" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

for ($iter = 1; $iter -le $MaxIterations; $iter++) {
    $iterStart = Get-Date
    $runId = "accum_iter_{0:D4}" -f $iter
    $elapsed = (Get-Date) - $startTime

    Write-Host "--- Iteration $iter / $MaxIterations ---" -ForegroundColor Green
    Write-Host "  Run ID: $runId"
    Write-Host "  Wall time elapsed: $($elapsed.ToString('hh\:mm\:ss'))"
    Write-Host "  Total candidates so far: $totalCandidates"
    Write-Host "  Total crashes: $totalCrashes | OOM kills: $totalOomKills"
    Write-Host ""

    # Run the solver via tuning profile runner (collects telemetry automatically)
    python scripts/run_phase3b_local_tuning_profile.py `
        --profile $Profile `
        --run-id $runId `
        --timeout-seconds 3600 `
        --sample-interval-seconds 1.0

    $exitCode = $LASTEXITCODE
    $iterDuration = (Get-Date) - $iterStart

    # Read the run summary to extract stats
    $summaryPath = ".artifacts\phase3b_local_13900ks_tuning_20260430\$runId\run_summary.json"
    if (Test-Path $summaryPath) {
        try {
            $summary = Get-Content $summaryPath -Raw | ConvertFrom-Json
            $status = $summary.status
            $duration = [math]::Round($summary.duration_seconds, 1)
            $peakRss = [math]::Round($summary.telemetry_summary.peak_total_rss_bytes / 1GB, 1)

            Write-Host "  Status: $status | Duration: ${duration}s | Peak RSS: ${peakRss} GiB" -ForegroundColor $(if ($status -eq "completed") { "Green" } else { "Red" })
        } catch {
            Write-Host "  (Could not parse run summary)" -ForegroundColor Yellow
            $status = "unknown"
        }
    } else {
        Write-Host "  (No run summary found)" -ForegroundColor Yellow
        $status = "unknown"
    }

    # Track stats
    if ($status -eq "failed" -or $status -eq "timeout") {
        $totalCrashes++
    }

    # Check raw log for OOM kill
    $rawLogPath = ".codex_test_logs\phase3b\local_13900ks_tuning_20260430\$runId\raw.log"
    if (Test-Path $rawLogPath) {
        $logTail = Get-Content $rawLogPath -Tail 20 -ErrorAction SilentlyContinue
        if ($logTail -match "MEMORY GUARDIAN") {
            $totalOomKills++
            Write-Host "  [MEMORY GUARDIAN triggered]" -ForegroundColor Magenta
        }
    }

    # Check campaign state for candidate count
    $campaignPath = "data\checkpoints\exact_campaign_state.json"
    if (Test-Path $campaignPath) {
        try {
            $campaign = Get-Content $campaignPath -Raw | ConvertFrom-Json
            if ($campaign.PSObject.Properties["candidates"]) {
                $totalCandidates = ($campaign.candidates.PSObject.Properties | Measure-Object).Count
            }
        } catch {
            # ignore parse errors
        }
    }

    # If the campaign completed normally (all candidates done), we're done!
    if ($exitCode -eq 0 -and $status -eq "completed") {
        Write-Host ""
        Write-Host "Campaign completed normally after $iter iterations!" -ForegroundColor Green
        Write-Host "Total wall time: $((Get-Date) - $startTime)" -ForegroundColor Green
        break
    }

    # Cooldown between crashes
    if ($iter -lt $MaxIterations) {
        # Adaptive cooldown: short floor for OS cleanup, then poll until memory is reclaimed
        $minFloor = 10
        $maxWait = $CooldownSeconds
        Write-Host "  Cooling down (min ${minFloor}s, max ${maxWait}s, target free RAM 25 GiB)..." -ForegroundColor DarkGray
        Start-Sleep -Seconds $minFloor
        $cdStart = Get-Date
        while ($true) {
            $freeGB = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB, 1)
            $waited = ((Get-Date) - $cdStart).TotalSeconds + $minFloor
            if ($freeGB -ge 25) {
                Write-Host "    ready: ${freeGB} GiB free after ${waited}s" -ForegroundColor DarkGray
                break
            }
            if ($waited -ge $maxWait) {
                Write-Host "    timeout: ${freeGB} GiB free after ${waited}s (proceeding anyway)" -ForegroundColor Yellow
                break
            }
            Start-Sleep -Seconds 3
        }
    }

    Write-Host ""
}

# Final summary
$totalElapsed = (Get-Date) - $startTime
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Accumulation Loop Finished" -ForegroundColor Cyan
Write-Host "  Total iterations: $iter" -ForegroundColor Cyan
Write-Host "  Total wall time: $($totalElapsed.ToString('hh\:mm\:ss'))" -ForegroundColor Cyan
Write-Host "  Total candidates evaluated: $totalCandidates" -ForegroundColor Cyan
Write-Host "  Total crashes: $totalCrashes" -ForegroundColor Cyan
Write-Host "  Total OOM kills: $totalOomKills" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
