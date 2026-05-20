param(
    [string]$SuiteOutput = ".codex_test_logs/parallelism_benchmark/priority_acceptance_normal.json",
    [switch]$DryRun
)

. "$PSScriptRoot\_exact_runner_common.ps1"

$arguments = @(
    "temp_scripts/benchmark_parallelism.py",
    "--suite-kind", "production-acceptance",
    "--suite-output", $SuiteOutput,
    "--process-priority", "normal"
)

Invoke-ExactRepoPython -Arguments $arguments -DryRun:$DryRun
