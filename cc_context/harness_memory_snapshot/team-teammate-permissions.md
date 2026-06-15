---
name: team-teammate-permissions
description: "agent team 里 Claude teammate 的权限模型: 默认继承 lead 的 permission mode + 同一份 settings/OS用户/文件系统/MCP, 无默认沙箱/隔离; 工具集看 agent 类型。对比 codex 成员有 sandbox 护栏、Claude 成员没有。"
metadata: 
  node_type: memory
  type: reference
  originSessionId: edb44864-4cd1-41d1-810d-782242891f4c
---

agent team 里 **Claude teammate 的权限**(2026-06-15 claude-code-guide 查官方文档 agent-teams/sub-agents/permissions/security 四页落实)。前提:`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`(已开)+ v2.1.32+。

## 跟生成它的主会话(lead)默认一致
- **权限模式**:teammate 起始 = **lead 的 permission mode**;lead 跑 bypass(`--dangerously-skip-permissions`)→ **所有 teammate 也 bypass**。**spawn 时不能逐个指定 mode**(只能 spawn 后再单独改某个;无 spawn-time `mode` 参数——这是与「普通子代理有 `permissionMode` frontmatter」最大不同)。
- **权限规则(allow/deny/ask)**:**同一份 settings 共享**,Claude Code 统一执行,非 per-agent。
- **运行身份**:同 OS 用户、同凭证、同文件系统访问范围、同 MCP server、同一本地进程上下文。**默认无沙箱、无 worktree 隔离**,与 lead 共享**同一份 checkout**(故文档警告两 teammate 改同一文件会互相覆盖)。
- CLAUDE.md/项目上下文照常加载。

## 可能与主会话不同
- **工具集**:由 teammate 的 agent 类型/定义 `tools:` 白名单决定 —— general-purpose=全工具;Explore/Plan=只读;自定义(如 `codex`)=定义里那几个 + 强制注入的 `SendMessage`/任务工具。**SendMessage+任务工具对 teammate 总是强制可用**(凌驾白名单)。
- **模型**默认**不继承** lead 的 `/model`(走 `/config` "Default teammate model")。
- **会话历史不带过去**(各自独立 context,只收 spawn prompt)。
- subagent 定义里的 `skills`/`mcpServers` 字段在 **teammate 路径被忽略**(改从 project/user settings 加载);普通子代理路径这俩生效。

## 权限提示去向
teammate 需批准的操作**冒泡给 lead**(不直接弹用户);lead bypass 则直接放行。前台普通子代理=提示透传给用户;后台子代理=**auto-deny** 任何会触发提示的调用。

## 安全关键(对比 codex 成员)
**Claude 成员没有 codex 成员那种 sandbox 护栏**。codex 成员靠 codex 自己的 `sandbox:read-only` 参数摁只读([[codex-cli-as-subagent]]);Claude 成员走 Claude Code 权限系统、**继承 lead 模式**。本机 `skipDangerousModePermissionPrompt:true` + 无 deny 规则 → 主会话若 bypass,每个 Claude 成员同样全权(改本机/跑命令/同 MCP)+ 同 checkout 无隔离。收紧三法:① 用只读类型(Explore/Plan)起;② 显式 `isolation: worktree`;③ 会话别开 bypass。

**未逐字确认的 caveat**:teammate 是否读自定义 agent 定义的 `permissionMode` —— 文档只说 teammate "honors tools allowlist and model"、未提 permissionMode,按「spawn 时 mode=lead's」明文应理解为**不读**;要 100% 坐实需实测。

链:[[codex-cli-as-subagent]](codex 成员的 sandbox 护栏 + 双向通信)。
