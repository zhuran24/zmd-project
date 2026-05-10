# loop_heartbeat.ps1 — Claude Code /loop 看门狗
# 用法：在另一个 PowerShell 窗口运行此脚本
#       powershell -ExecutionPolicy Bypass -File scripts\loop_heartbeat.ps1
#
# 原理：
#   1. Claude 每次 loop 迭代、以及每个大操作前后都会更新 .artifacts/loop_heartbeat.json
#   2. 本脚本每 60 秒检查一次心跳文件
#   3. 如果心跳超过 15 分钟没更新，认为卡住了
#   4. 找到 Claude 桌面端窗口，发送 Escape 取消卡住 → 输入 /loop 恢复

param(
    [int]$CheckIntervalSeconds = 60,
    [int]$StaleThresholdSeconds = 900,   # 15 分钟没心跳就认为卡了
    [string]$HeartbeatPath = "",
    [string]$TargetWindowTitle = "zmd"   # Claude 桌面端窗口标题关键词
)

Add-Type -AssemblyName System.Windows.Forms

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32Loop {
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    public const int SW_RESTORE = 9;
}
"@

if (-not $HeartbeatPath) {
    $HeartbeatPath = Join-Path "D:\claude pj\zmd" ".artifacts\loop_heartbeat.json"
}

function Get-HeartbeatAge {
    if (-not (Test-Path $HeartbeatPath)) {
        return [int]::MaxValue
    }
    $lastWrite = (Get-Item $HeartbeatPath).LastWriteTime
    return [int]((Get-Date) - $lastWrite).TotalSeconds
}

function Find-ClaudeWindow {
    # 优先找 Claude 桌面端（进程名 Claude 或 claude）
    $candidates = Get-Process | Where-Object {
        $_.MainWindowHandle -ne [IntPtr]::Zero -and
        $_.MainWindowTitle -and (
            $_.MainWindowTitle -match $TargetWindowTitle -or
            $_.ProcessName -match "^[Cc]laude$"
        )
    }
    if ($candidates) {
        return ($candidates | Select-Object -First 1)
    }
    return $null
}

function Send-LoopToTerminal {
    $proc = Find-ClaudeWindow
    if (-not $proc) {
        Write-Host "  [!] 找不到 Claude 窗口（进程名含 'claude' 或标题含 '$TargetWindowTitle'）"
        return $false
    }

    $hwnd = $proc.MainWindowHandle
    Write-Host "  [>] 找到窗口: $($proc.ProcessName) (PID=$($proc.Id))"
    Write-Host "  [>] 标题: '$($proc.MainWindowTitle)'"

    # 激活窗口
    [Win32Loop]::ShowWindow($hwnd, [Win32Loop]::SW_RESTORE) | Out-Null
    Start-Sleep -Milliseconds 300
    [Win32Loop]::SetForegroundWindow($hwnd) | Out-Null
    Start-Sleep -Milliseconds 500

    # Escape 取消可能的卡住状态或弹出框
    [System.Windows.Forms.SendKeys]::SendWait("{ESCAPE}")
    Start-Sleep -Seconds 1

    # 再按一次 Escape 确保回到输入框
    [System.Windows.Forms.SendKeys]::SendWait("{ESCAPE}")
    Start-Sleep -Seconds 1

    # 输入 /loop 并回车
    [System.Windows.Forms.SendKeys]::SendWait("/loop{ENTER}")

    Write-Host "  [>] 已发送 /loop"
    return $true
}

# === 主循环 ===
Write-Host "========================================"
Write-Host " Claude Code Loop 看门狗"
Write-Host "========================================"
Write-Host " 心跳文件: $HeartbeatPath"
Write-Host " 检查间隔: ${CheckIntervalSeconds}s"
Write-Host " 超时阈值: ${StaleThresholdSeconds}s ($(([int]($StaleThresholdSeconds/60)))min)"
Write-Host " 目标窗口: 进程名=claude 或 标题含'${TargetWindowTitle}'"
Write-Host "========================================"
Write-Host ""

# 启动时检查一下能不能找到窗口
$testProc = Find-ClaudeWindow
if ($testProc) {
    Write-Host "[启动] Claude 窗口已找到: '$($testProc.MainWindowTitle)'"
} else {
    Write-Host "[启动] 暂未找到 Claude 窗口，等待启动..."
}
Write-Host ""

$recoveryCount = 0

while ($true) {
    $now = Get-Date -Format "HH:mm:ss"
    $age = Get-HeartbeatAge

    if ($age -eq [int]::MaxValue) {
        Write-Host "[$now] 心跳文件不存在 — 等待 Claude 启动 /loop ..."
    }
    elseif ($age -gt $StaleThresholdSeconds) {
        $recoveryCount++
        $ageMin = [math]::Round($age / 60, 1)
        Write-Host "[$now] !! 心跳超时 (${ageMin}min) — 第 ${recoveryCount} 次恢复尝试"
        $sent = Send-LoopToTerminal
        if ($sent) {
            Write-Host "[$now] 恢复指令已发送，等待 3 分钟后再检查..."
            Start-Sleep -Seconds 180
            continue
        } else {
            Write-Host "[$now] 恢复失败，1 分钟后重试..."
        }
    }
    else {
        $ageMin = [math]::Round($age / 60, 1)
        Write-Host "[$now] OK — 心跳 ${ageMin}min 前更新"
    }

    Start-Sleep -Seconds $CheckIntervalSeconds
}
