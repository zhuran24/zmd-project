param(
    [double]$CampaignHours = 168.0,
    [switch]$ResumeCampaign,
    [switch]$DryRun
)

. "$PSScriptRoot\_exact_runner_common.ps1"

$arguments = @(
    "main.py",
    "--mode", "certified_exact",
    "--campaign-hours", ([string]$CampaignHours),
    "--parallel-processes", "4",
    "--process-priority", "high",
    "--frontier-probe-mode", "auto"
)

if ($ResumeCampaign) {
    $arguments += "--resume-campaign"
}

Invoke-ExactRepoPython `
    -Arguments $arguments `
    -EnvOverrides @{ "EXACT_CP_SAT_WORKERS" = "4" } `
    -DryRun:$DryRun
