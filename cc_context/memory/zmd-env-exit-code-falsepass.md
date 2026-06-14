---
name: zmd-env-exit-code-falsepass
description: zmd 坑——PowerShell 里 `& ".venv\Scripts\python.exe" xxx; Write-Host "exit: $LASTEXITCODE"` venv 不存在时 & 失败但 Write-Host 把整条洗成 exit 0;判断脚本通过必须看脚本自身输出, 不能只看 exit code
metadata:
  node_type: memory
  type: project
  originSessionId: 01ce64d2-c550-4722-ba4f-1042a3935678
---

- **坑(实测踩过):** PowerShell 里 `& ".venv\Scripts\python.exe" xxx; Write-Host "exit: $LASTEXITCODE"` 这种写法,venv 不存在时 `&` 失败但 Write-Host 把整条命令洗成 exit 0,看起来像通过。**判断"脚本通过"必须看到脚本自己的输出**(如 "P1.2 proof obligation check passed"),不能只看 exit code。

相关:[[zmd-checkout-env]]
