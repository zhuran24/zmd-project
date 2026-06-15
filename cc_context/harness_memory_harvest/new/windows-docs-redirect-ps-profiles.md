---
name: windows-docs-redirect-ps-profiles
description: 本机「文档」文件夹重定向到 C:\22957\document；PowerShell profile 都在那里，别写 C:\Users\22957\Documents
metadata: 
  node_type: memory
  type: user
  originSessionId: 211fa020-3b43-4d44-976c-04549cfa39d0
---

本机 Windows「文档」文件夹被重定向到 `C:\22957\document`（不是默认的 `C:\Users\22957\Documents`）。

- PowerShell 7 profile: `C:\22957\document\PowerShell\Microsoft.PowerShell_profile.ps1`
- PowerShell 5.1 profile: `C:\22957\document\WindowsPowerShell\Microsoft.PowerShell_profile.ps1`（已有 node/fnm/conda 环境配置，追加内容别覆盖）
- 写到 `C:\Users\22957\Documents\...` 的文件不会被任何 shell 读取（2026-06-10 实际踩过：先写错位置后删除重写）。

两个 profile 里都定义了 `cc` 函数 = `claude --dangerously-skip-permissions`（不带 --chrome，因为 Chrome 集成已在 /chrome 菜单设为 "Enabled by default"）。
