# 启动 GPT 外发自动化专用 Chrome (独立 profile + CDP 9222)。
# 已在跑则直接报告就绪。首次使用需要在弹出的窗口里手动登录 chatgpt.com 一次,
# 之后 cookie 长期有效, dispatch_gpt_task.py 复用这个实例。

$port = 9222
$profileDir = "C:\Users\22957\.zmd_gpt_automation_profile"

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

$chrome = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $chrome) {
    Write-Host "FATAL: chrome.exe not found in standard locations."
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
