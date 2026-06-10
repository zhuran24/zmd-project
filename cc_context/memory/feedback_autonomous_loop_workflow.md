---
name: autonomous-loop-workflow
description: 用户离开前下指令"做完所有能做的，做完自己删 cron"时的标准工作流
type: feedback
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

> ⚠️ **2026-05-27 起部分废弃**: 硬编码 **1min 心跳 hook** 已于 commit `959b6de` 移除, **无自动心跳/cron fire**。(注: `.claude/settings.json` 现非空 —— 后来 [[github-backup]] 又加了 `SessionEnd` WIP-backup hook 跑 `cc_wip_backup.ps1`; 那是退出兜底备份, 不是心跳, 不每分钟 fire。早先此处写的 `{"hooks":{}}` 字面已过时。) 本工作流 (尤其「设 1min cron 心跳」一步) 仅在用户明确再次下「设置 1min 心跳」指令时适用, **不再作 autopilot 默认**。其余 (大表 inline / 每 stage 独立 commit / 阻塞转下一项 / 做完自删 cron) 仍有效。见 phase-1-2-progress。

用户 2026-05-08 在去睡前下了一个明确的工作流指令：
> "你设置一个一分钟心跳然后把现在能做的工作全做了，等下你先列个大表，做完之后你自己把心跳删了，整个流程你记一下"

**Why:** 用户希望在"audit 充分 + 系统配置就绪 + 真正能并行做事"的窗口里，让我自主跑完一批确定性高的工程任务，他离开期间不被打扰，但又能通过 cron 心跳查到进度。这跟"放开手脚但要审查"+"按 ROI 自己排序"两条 memory 一起，构成完整 autopilot 模式。

**How to apply (流程模板):**

1. **CronCreate 1 min `* * * * *` recurring**（不是 5m / 10m，用户明确要 1 min。每次 fire 给一个 progress checkpoint，但 fire 本身不阻塞工作）
2. **列大表**（inline 在对话里，**不写 .md 文件**），格式：
   ```
   | Tier | # | 项 | 工时估 | 状态 (⏳/🔄/✓/⚠) |
   ```
   按 ROI 序：性能 verify → spike → 实施 → 测试 → cleanup → memory + CronDelete
3. **每个 Tier 独立 audit + 实施**，遇阻塞别硬上：
   - "Linux campaign state 缺失 → cross-OS 不可比"这种**承认 limitation 转下一项**比硬跑 fake data 强
   - 涉及 cross-module fallback ladder / certified_exact 边界 → 留 stage deferred 别一次性吃完
4. **commit + preflight gate hook 自动跑**，stage 之间 commit 不 batch
5. **完成或卡住后**：写一条 memory 记 workflow（这条），CronDelete 心跳，简短最终报告
6. **不动 working copy 残留**（用户没明说让我清的 modified files 留着等他决定）

**坑点总结（这一 session 踩过的）:**

- **集中 1-2hr 工作 + 1 min cron 兼容**：cron 不阻塞工作，让 wave 跑等待时间被 cron fire 平摊。但**真集中工作**（数据流 audit + 多 module fix）不要被 cron 打断状态——每个 Bash call 是独立 shell，记得 `cd ~/claude-pj/zmd && source .venv/bin/activate` 前缀
- **跨 OS 第一次跑**：常踩 psutil API field 不一致（Windows `.private` vs Linux `.uss`）这种坑，跑一次全 pytest 暴露问题
- **git hook +x bit 被 7z extract 丢了**：跨 fs (NTFS→ext4) file mode 不通用，手动 `chmod +x .git/hooks/pre-commit`
- **hook 里 `python` 走 PATH = system Python**（不是 venv），需要改 hook 用 `.venv/bin/python` 才能 import ortools
- **escalation 不要怕**：stage 3 fallback ladder 跨模块 + 漏一处破 certified_exact = 真高风险，"escalate 等用户决策"比硬上更稳；但 escalation 必须给**具体论证**（不是"风险大"经验判断），按 `feedback_autopilot_with_review_gate` 已记
- **Linux 实测比 Windows 快**：本 session 数据点 = pytest 全套 Windows 6:00 vs Linux 4:00 (-33%)；preflight 核心测 Windows 2.4s vs Linux 0.7s (-71%)。⚠️ "CachyOS BORE + zram + jemalloc 默认致快" 是 **best-guess 非证实** —— 跨机硬件/OS/FS 多变量混杂、未单变量隔离 (per [[no-causal-claim-from-n1]]), 原始数字诚实当"数据点"看即可, 别把因果说死

**Anti-pattern（不要做的）:**

- ❌ 把 1 min cron 当任务调度器（每分钟开新 work），实际它是**进度追踪器**
- ❌ 卡在 escalation 永久挂等用户（如果是"能 ROI 0 但实施清晰"的 stage，自己做完 + commit 标 deferred 比卡着等好）
- ❌ Cron 死循环不删（"自己删 cron"是 user 明确指令的一部分，做完必删，不然下次 session 进来还在 fire）
- ❌ 一次 commit 吃多 stage（每 stage 独立 commit + preflight 兜底，bug 出来 git bisect 才好用）

## 链 (补连 2026-06-02 全覆盖审计 wnyzl1iwk)
- [[no-sleep-loop-for-goal-hook]] — /goal hook 别 sleep loop
