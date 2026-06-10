# 启动 GPT 外发自动化专用浏览器 (独立 profile + CDP 9222)。
# 已在跑则直接报告就绪。首次使用需要在弹出的窗口里手动登录 chatgpt.com 一次,
# 之后 cookie 长期有效, dispatch_gpt_task.py 复用这个实例。
# Chromium 系浏览器都支持 CDP: -Browser edge 用 Edge (本机自带), 默认 chrome。
# 注意 Edge/Chrome 各用各的 profile 目录, 切换浏览器要重新登录一次。
param([ValidateSet("chrome", "edge")][string]$Browser = "chrome")

$port = 9222
$profileDir = "C:\Users\22957\.zmd_gpt_automation_profile_$Browser"
if ($Browser -eq "chrome" -and -not (Test-Path $profileDir) -and (Test-Path "C:\Users\22957\.zmd_gpt_automation_profile")) {
    $profileDir = "C:\Users\22957\.zmd_gpt_automation_profile"  # 沿用首版 chrome profile (已登录)
}

function Test-Cdp {
    try {
        $r = Invoke-WebRequest "http://localhost:$port/json/version" -UseBasicParsing -TimeoutSec 3
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

if (Test-Cdp) {
    Write-Host "CDP already up on port $port — automation Chrome is ready."
    exit 0
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
$chrome = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $chrome) {
    Write-Host "FATAL: $Browser executable not found in standard locations."
    exit 1
}

$firstRun = -not (Test-Path $profileDir)
Start-Process $chrome -ArgumentList @(
    "--remote-debugging-port=$port",
    "--user-data-dir=$profileDir",
    "--no-first-run",
    "--no-default-browser-check",
    "https://chatgpt.com"
)

$deadline = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $deadline) {
    if (Test-Cdp) {
        Write-Host "Automation Chrome started, CDP up on port $port."
        if ($firstRun) {
            Write-Host "FIRST RUN: log in to chatgpt.com manually in the new window once; the session persists afterwards."
        }
        exit 0
    }
    Start-Sleep -Milliseconds 500
}
Write-Host "FATAL: Chrome started but CDP port $port did not come up."
exit 1
