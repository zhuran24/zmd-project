# 让 dispatch 脚本可连的浏览器就绪 (CDP 9222)。
# 默认 = 用户日常 Edge 主实例 (2026-06-11 owner 裁决: 不搞独立 profile, 已登录零配置)。
#   Edge 已带端口在跑 → 直接报就绪;
#   Edge 在跑但没带端口 → 温和关窗 (等同点 X, 会话可恢复) → 带 9222 重启并恢复标签;
#   Edge 没在跑 → 直接带端口启动。
# -Isolated 切回独立 profile 模式 (chrome/edge 二选一, 首次需手动登录) 备用。

# -App = 第三托底通道: ChatGPT 桌面 App (Electron) 带 CDP 9224 启动。
# 必须用 Invoke-CommandInDesktopPackage 以 MSIX 包身份启动 — 裸跑 WindowsApps
# 里的 exe 会因 Windows.Storage.ApplicationData.get_Current 拿不到包上下文
# 而主进程崩溃弹 "A JavaScript error occurred in the main process"。
param(
    [switch]$Isolated,
    [switch]$App,
    [ValidateSet("chrome", "edge")][string]$Browser = "edge"
)

$port = if ($App) { 9224 } else { 9222 }

function Test-Cdp {
    try {
        $r = Invoke-WebRequest "http://localhost:$port/json/version" -UseBasicParsing -TimeoutSec 3
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

if (Test-Cdp) {
    Write-Host "CDP already up on port $port — browser is ready."
    exit 0
}

function Find-Exe([string[]]$candidates) {
    $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if ($App) {
    $pkg = Get-AppxPackage OpenAI.ChatGPT-Desktop
    if (-not $pkg) { Write-Host "FATAL: ChatGPT desktop app not installed."; exit 1 }
    $running = Get-Process ChatGPT -ErrorAction SilentlyContinue
    if ($running) {
        Write-Host "ChatGPT app is running without the debug port — closing to restart with it..."
        $running | ForEach-Object { $null = $_.CloseMainWindow() }
        Start-Sleep -Seconds 3
        Get-Process ChatGPT -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    Invoke-CommandInDesktopPackage -PackageFamilyName $pkg.PackageFamilyName -AppId "ChatGPT" `
        -Command (Join-Path $pkg.InstallLocation "app\ChatGPT.exe") `
        -Args "--remote-debugging-port=$port"
} elseif (-not $Isolated) {
    $edge = Find-Exe @(
        "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    )
    if (-not $edge) { Write-Host "FATAL: msedge.exe not found."; exit 1 }

    $running = Get-Process msedge -ErrorAction SilentlyContinue
    if ($running) {
        Write-Host "Edge is running without the debug port — closing windows gracefully to restart with it..."
        $running | ForEach-Object { $null = $_.CloseMainWindow() }
        $deadline = (Get-Date).AddSeconds(15)
        while ((Get-Date) -lt $deadline -and (Get-Process msedge -ErrorAction SilentlyContinue)) {
            Start-Sleep -Milliseconds 500
        }
        # Edge 的「启动加速」后台常驻进程没有主窗口, graceful 关不掉 — 强制清掉
        Get-Process msedge -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    Start-Process $edge -ArgumentList "--remote-debugging-port=$port", "--restore-last-session"
} else {
    $profileDir = "C:\Users\22957\.zmd_gpt_automation_profile_$Browser"
    if ($Browser -eq "chrome" -and -not (Test-Path $profileDir) -and (Test-Path "C:\Users\22957\.zmd_gpt_automation_profile")) {
        $profileDir = "C:\Users\22957\.zmd_gpt_automation_profile"
    }
    $candidates = if ($Browser -eq "edge") {
        @(
            "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        )
    } else {
        @(
            "C:\Program Files\Google\Chrome\Application\chrome.exe",
            "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
        )
    }
    $exe = Find-Exe $candidates
    if (-not $exe) { Write-Host "FATAL: $Browser executable not found."; exit 1 }
    $firstRun = -not (Test-Path $profileDir)
    Start-Process $exe -ArgumentList @(
        "--remote-debugging-port=$port",
        "--user-data-dir=$profileDir",
        "--no-first-run",
        "--no-default-browser-check",
        "https://chatgpt.com"
    )
    if ($firstRun) {
        Write-Host "FIRST RUN (isolated profile): log in to chatgpt.com manually once in the new window."
    }
}

$deadline = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $deadline) {
    if (Test-Cdp) {
        Write-Host "Browser ready, CDP up on port $port."
        exit 0
    }
    Start-Sleep -Milliseconds 500
}
Write-Host "FATAL: browser started but CDP port $port did not come up."
exit 1
