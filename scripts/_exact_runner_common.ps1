Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Worker precedence reminder:
# stage-specific EXACT_*_CP_SAT_WORKERS > EXACT_CP_SAT_WORKERS > built-in defaults.
# main.py prints the resolved profile at solver startup.
# Memory / parallel-process guidance lives in docs/parallel_configuration.md.

function Get-ExactRepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
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

function Invoke-ExactRepoPython {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [hashtable]$EnvOverrides = @{},

        [switch]$DryRun
    )

    $repoRoot = Get-ExactRepoRoot
    $pythonCommand = "python"
    if (-not (Get-Command $pythonCommand -ErrorAction SilentlyContinue)) {
        throw "Python executable 'python' was not found on PATH."
    }

    $effectiveEnv = @{}
    foreach ($key in $EnvOverrides.Keys) {
        $effectiveEnv[[string]$key] = [string]$EnvOverrides[$key]
    }
    $effectiveEnv["PYTHONPATH"] = "."

    Write-Host ("Repo root: {0}" -f $repoRoot)
    Write-Host ("Command:   {0}" -f (Format-ExactCommand -Executable $pythonCommand -Arguments $Arguments -EnvOverrides $effectiveEnv))

    if ($DryRun) {
        return
    }

    $savedEnv = @{}
    foreach ($key in $effectiveEnv.Keys) {
        $savedEnv[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
    }

    try {
        foreach ($key in $effectiveEnv.Keys) {
            [Environment]::SetEnvironmentVariable($key, $effectiveEnv[$key], "Process")
        }

        Push-Location $repoRoot
        try {
            & $pythonCommand @Arguments
            $exitCode = $LASTEXITCODE
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
}
