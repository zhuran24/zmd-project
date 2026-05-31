---
name: windows-handoff-env
description: "2026-05-30 接手到 Windows 机器. 仓库 clone 到 D:\\追光\\zmd, venv 用 .venv\\Scripts\\python.exe (Windows 布局, Python 3.13.13 + ortools 9.15.6755 精确锁版), 414 cut 测试全过 (3.93s). prod-scale (266 inst/~280K pose/30-47GB RAM/168h campaign) 这台跑不了, 要回原 Linux CachyOS 主机. CC memory canonical slug 见正文."
metadata:
  node_type: memory
  type: project
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

> **本条 = Windows 环境落点的稳定 reference** (路径/venv/能力边界)。项目「当前 phase/交接状态」的单一 living 源是 [[windows-ninth-review-pending]], 不在本条 (per [[memory-currency-protocol]])。
> **更新 (2026-05-31)**: 仓库已从 `D:\追光\zmd\zmd` 上移一层到仓库根 `D:\追光\zmd`; CC memory canonical slug = `D-----zmd` (确认无误, 旧 `D-----zmd-zmd` 副本 obsolete)。

2026-05-30 zhuran24 → 朋友接手, 落到 Windows 11 机器(原项目是 Linux/CachyOS 重度调优的)。

**环境落点**:
- 仓库: `D:\追光\zmd`(从 `repo.bundle` clone, master HEAD `959b6de`, 工作树干净)
- venv: `D:\追光\zmd\.venv\Scripts\python.exe`(Windows 布局, **不是** Unix `.venv/bin/`)
- Python 3.13.13(winget user-scope, `C:\Users\Lenovo\AppData\Local\Programs\Python\Python313\`)。项目要 3.13, **别用 3.14**(json stdlib 坑)
- 依赖: `requirements.lock.txt` 精确版(ortools==9.15.6755)在 Windows cp313 直接装通, import 全 OK
- 健康基线: `.venv\Scripts\python.exe -m pytest src/tests/cuts/ -q` = **414 passed**(3.93s)
- CC memory slug = `D-----zmd`(项目路径 `D:\追光\zmd` 每个非字母数字字符→`-`, 不折叠); 117 条 handoff memory 已接到 `~/.claude/projects/D-----zmd/memory/`

**这台机器能做 / 不能做**:
- 能: P1.3A 设计、cut 测试、小规模/单 anchor/toy validation、Phase 0 cheap gate、全部 soundness 单测
- 不能: prod-scale 收敛验证(266 inst × ~280K pose, ~30-47GB RAM, jemalloc, P-core pin, 168h campaign)—— 要回原 Linux 主机

**setup.sh Windows 注意**: 它的 venv 用 `.venv/bin/` + slug 用 Unix path, 两处 Windows 不适用; 接手是手动做的(clone + 手算 slug 接 memory + Windows venv)。

**Why**: 这台 Windows 是新接手的 dev 环境, 路径/能力边界跟原 Linux 机不同, 非显然。
**How to apply**: 在这台跑命令用 `D:\追光\zmd\.venv\Scripts\python.exe`; 需要 prod-scale 跑时提醒用户回 Linux 主机。relate [[p1-3a-design-phase]]。
