---
name: windows-handoff-env
description: "**(历史快照, 2026-05-30 初次 Linux→Windows 接手; 路径/venv/slug/基线均已 superseded, 当前 Windows 环境现状见 zmd-checkout-env)** 2026-05-30 接手到 Windows 机器. 仓库 clone 到 D:\\追光\\zmd, venv 用 .venv\\Scripts\\python.exe (Windows 布局, Python 3.13.13 + ortools 9.15.6755 精确锁版), 414 cut 测试全过 (3.93s). prod-scale (266 inst/~280K pose/30-47GB RAM/168h campaign) 这台跑不了, 要回原 Linux CachyOS 主机. CC memory canonical slug 见正文."
metadata:
  node_type: memory
  type: project
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

> **⚠️ 历史快照 (2026-05-30 初次接手), 环境细节已整体 superseded —— 当前 Windows 环境现状一律见 [[zmd-checkout-env]]**: 本条记的 `D:\追光\zmd` / `.venv\Scripts\python.exe` / Python 3.13.13 / slug `D-----zmd` / `C:\Users\Lenovo` / 414 cut 基线**全部已失效**。现状: 仓库 `C:\claude pj\zmd_pj`、**无 .venv** (用 `C:\Program Files\Python313` 的 `python`)、slug `C--claude-pj-zmd-pj`、用户目录 `C:\Users\22957`、cut 测试已 463。下方正文仅留作初次接手的历史记录, **别当现行操作指令照搬**。整条里唯一仍有效的稳定结论 = 「prod-scale 要回原 Linux CachyOS 主机」这条能力边界。
> **本条原定位 = Windows 环境落点的稳定 reference** (路径/venv/能力边界)。项目「当前 phase/交接状态」的单一 living 源是 [[windows-ninth-review-pending]], 不在本条 (per [[memory-currency-protocol]])。
> **更新 (2026-05-31)**: 仓库已从 `D:\追光\zmd\zmd` 上移一层到仓库根 `D:\追光\zmd`; CC memory canonical slug = `D-----zmd` (确认无误, 旧 `D-----zmd-zmd` 副本 obsolete)。**根因**: `zmd\zmd` 子目录曾产生 `D-----zmd` vs `D-----zmd-zmd` 两个 slug 副本 (dual-slug 分叉), 上移到仓库根是为让 **项目 + memory + session 三者对齐**解开死结。**以后在 `D:\追光\zmd` 开 CC 即自动加载 CLAUDE.md + memory, 不用再 cd zmd** —— 注意 CC **不会**自动加载子目录的项目文件, 必须在项目根启动。

2026-05-30 zhuran24 → 朋友接手, 落到 Windows 11 机器(原项目是 Linux/CachyOS 重度调优的)。

**环境落点**:
- 仓库: `D:\追光\zmd`(2026-05-30 从 `repo.bundle` clone, bundle 已删; 接手快照 HEAD `959b6de`, **现状 HEAD 见 git log** —— 本 session 后续有 GitHub备份/结构整理等多个 commit, 别拿 959b6de 当现状)
- venv: `D:\追光\zmd\.venv\Scripts\python.exe`(Windows 布局, **不是** Unix `.venv/bin/`)。**venv 含绝对路径, 跨目录迁移会失效** —— 须 rename 旧的为 `.venv_broken` 挪开, 在新根 fresh 重建 (本 session 迁移后这么修的, 重建后 pytest cuts 414 passed 确认没伤项目)
- shell 工具链: bash = Git Bash 5.2 / git 2.51
- Python 3.13.13(winget user-scope, `C:\Users\Lenovo\AppData\Local\Programs\Python\Python313\`)。项目要 3.13, **别用 3.14**(json stdlib 坑)
- 依赖: `requirements.lock.txt` 精确版(ortools==9.15.6755)在 Windows cp313 直接装通, import 全 OK
- 健康基线: `.venv\Scripts\python.exe -m pytest src/tests/cuts/ -q` = **414 passed**(3.93s)
- CC memory slug = `D-----zmd`(项目路径 `D:\追光\zmd` 每个非字母数字字符→`-`, 不折叠); memory 在 `~/.claude/projects/D-----zmd/memory/` (接手时 117 条, 2026-06-01 重构后增长中; 精确数易过时, 以实际 ls 为准)
- **本机无全局 `C:\Users\Lenovo\.claude\CLAUDE.md`** (不存在); standing 规则 (如 default-opus) 记进**项目** CLAUDE.md (`D:\追光\zmd\CLAUDE.md`, 工作时自动加载那个), 仅需跨所有项目生效才另建全局

**这台机器能做 / 不能做**:
- 能: P1.3A 设计、cut 测试、小规模/单 anchor/toy validation、Phase 0 cheap gate、全部 soundness 单测
- 不能: prod-scale 收敛验证(266 inst × ~280K pose, ~30-47GB RAM, jemalloc, P-core pin, 168h campaign)—— 要回原 Linux 主机

**setup.sh Windows 注意**: 它的 venv 用 `.venv/bin/` + slug 用 Unix path, 两处 Windows 不适用; 接手是手动做的(clone + 手算 slug 接 memory + Windows venv)。

**Why**: 这台 Windows 是新接手的 dev 环境, 路径/能力边界跟原 Linux 机不同, 非显然。
**How to apply**: ⚠️ 本条路径/venv 已 superseded —— 当前 Windows 环境跑命令见 [[zmd-checkout-env]] (无 .venv, 用 `C:\Program Files\Python313` 的 `python`); 本条只保留「需要 prod-scale 跑时提醒用户回原 Linux CachyOS 主机」这条能力边界仍有效。relate [[p1-3a-design-phase]] [[zmd-checkout-env]]。
