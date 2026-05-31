---
name: v7-review-package-landed
description: "2026-05-16 v7 review 包打完给 GPT Pro: 完整 dev timeline (8 path + 7 SUPPLEMENT) + 干净代码 + 严密推理链 0 主动性. 同 session 完成 12 commit cleanup + 670 文件 phase3b 物理重组. 8 条 lever 全 verdict, Path 8 (GPT-5.5 Pro ghost-anchor slicing) 是唯一未试 + 严格性兼容路径."
metadata:
  type: project
  originSessionId: f961efc3-93a4-4068-a05d-b7f8f4592d35
---

**2026-05-16 v7 review 包 final state**:

`/home/zhuran24/linwin_share/zmd_code_v7.zip` (9.4 MB, 77 files) — 待 GPT Pro reply.

## 包结构 (严格按用户"0 主动性 + 严密时间线"要求)

```
INDEX.md                  顶层导航
code.tar.xz               干净项目代码 (排除 .venv/.artifacts/_codex_archive/...)
bin/7zz                   解压工具
dev_timeline/
  ├── path_01-08/         8 条开发路径完整时间线
  │   各含: timeline.md + 0-N 个 SUPPLEMENT_*.md + related_code/
  ├── 7 个 SUPPLEMENT:
  │   - Path 1: early_windows_phase + p1_24_oom_inflection
  │   - Path 3: phase3c_roadmap_audit + p2_14_dumper_nested_cpsat_hang
  │   - Path 5: d_step1_seed_acquisition
  │   - Path 7: codex_era_and_phase3c_strategy + review_pkg_v3_v4_lessons
  └── Path 8 = GPT-5.5 Pro ghost-anchor slicing (唯一未试)
```

每个 timeline 严格按 "**情境 → 推理 (含隐含子假设) → 动作 → 实测数据 → 失败原因 + 主观推理误区** → 留下产物 → 后续" 排列. 不跳逻辑. 不放推荐 / "下一步该怎么做". 纯历史事实.

## 同 session 12 commit cleanup (c5c57af → 2ec6b32)

- c5c57af lever_verdicts (主线 lever L1-L11 总账)
- 1a280dd env_variable_index (100+ EXACT_* env 11 组)
- 3bb3dbb 3 个 5000+ 行文件 docstring 目录索引
- 59496cc .gitignore + 移除意外 submodule
- eb8eef3 README 状态地图
- 239240f 5 个 Codex-era 永远 skip 测试加 docstring
- 0ad6250 phase3b_module_index (670 文件分类)
- 7b46367 整理 1-7 第二轮 (test docstring + adapter README + SCIP/HiGHS STATUS + CHANGELOG + memory)
- c1a8e23 cleanup_session_20260516 summary
- 03a57e6 归档 5 hint trials 数据 (11 MB)
- **e4bad28 phase3b 670 文件物理重组** (866 files, 5263 ins / 5381 del; agent 解 7 个 sed/path surprise; 2207 pytest pass = baseline 一致)
- 2ec6b32 summary 补 final 数据

整理动作 1-8 全完成. 2207 passed + 60 skipped (baseline 一致, 验证无 regression).

## D step 2 hint trial 完整数据 (2026-05-16 session 上半)

5 个 trial × 全 UNKNOWN, 包括 blueprint exact match 27×15:

| trial | master_seconds | workers | profile | 27×15 结果 |
|---|---|---|---|---|
| 4 | 600 | 1 | default | UNKNOWN |
| 5 | 600 | 1 | ghost_first_v1 | UNKNOWN |
| 7 | 3600 (1h+) | 8 满载 (758% CPU) | default | UNKNOWN |

3 axis (时间 ×6, worker ×8, profile 切换) **全 saturation**, **master 内在难度对该 candidate 不能 prove**. Telemetry verified: 266 mandatory × 3 = 798 AddHint 一次不多. Integration 完美, master 解不动跟 hint 无关.

## 8 条 lever 完整 verdict

| Lever | 状态 |
|---|---|
| L1 RAM 优化 | ❌ 死路, -57% RAM but 0 FEASIBLE 不变 |
| L2 求解器重写 (HiGHS/SCIP) | ❌ 死路, LP-MIP 不适合 dense linear |
| L3 OR-Tools 内置参数 | ❌ marginal, default 已近 local optimal |
| L4 EXACT_POWER_PLACEMENT 重开 | ❌ PROJECT_LOCK 禁 |
| L5 OR-Tools 9.16 | ❌ 不值得等 |
| L6 AI sidecar | 🟡 搁置 long-term |
| L7 community hint | ❌ integration 完美 master 解不动 |
| L8 search profile 切换 | ❌ 不影响 |
| L9 objective relaxation | ❌ 假设错 (master 本来就是 feasibility) |
| L10 加长 master_seconds + workers 8 | ❌ 不影响 |
| L11 hard constraint | 🟡 未试 (牺牲严格性, 用户拒绝) |
| **Path 8 GPT-5.5 Pro ghost-anchor slicing** | 🟡 **唯一未试 + 严格性兼容**, GPT 给完整 v3 patch 但下载链接全过期, 从未本地 reconstruct + 实测 |

## Path 8 关键 caveat (给 GPT 看)

GPT-5.5 Pro 给的 ghost-anchor disjunctive decomposition 数学 sound + PROJECT_LOCK 兼容 + 工程合理. 但**未验证**:
1. RAM 减多少未知 (大头若 facility 部分则只减 20-40%, 不是 50%+)
2. Wall-time 可能涨 (per-anchor solve × N anchor)
3. Slice cuts 不跨 anchor 复用 (LBBD 信息浪费)

最小版本: 50-100 行核心改动 + 1 test + 30-60 min 本地实测 RAM. 工作量轻, 但 ROI 不确定.

## 下个 session 的 immediate next step

1. **等 GPT Pro 对 v7 包的 reply** — 可能给新方向 (Path 8 变种 / 新 paradigm / 我们没想到的 lever)
2. **如果 GPT 没新方向**, 自己写 Path 8 最小版本 50-100 行 + 实测 RAM 30-60 min
3. **如果 Path 8 实测 RAM 减 ≥30%** → backport GPT v2/v3 production 装饰 (resume manifest 等)
4. **如果 Path 8 也死** → 进 long-term option (L6 AI sidecar + AI cut + verifier) 或者退回放弃严格性

## Memory 链

- [[d-step2-hint-landed]] — D step 2 hint integration 详细 (同 session 已写)
- [[2026-05-15-ram-session-misdirected]] — RAM 路径死路 lesson
- [[30gb-real-culprit-power-coverage]] — 30 GB 真大头 = worker propagation
- [[gpt-anchor-slicing-proposal]] — Path 8 详细 (GPT-5.5 Pro v1/v2/v3 完整方案)
- [[rewrite-path-exhausted]] — 重写路径全死路
- [[p1-24-oom-blocked]] — P1 #24 OOM 教训 + 硬件方向排除
- [[p2-14-dumper-path-blocked]] — P2 #14 master 嵌套 CP-SAT timeout 真因
- [[cleanup-preserve-clarify]] — 整理原则 (这次 cleanup 严格遵守)
- [[clarity-over-brevity]] — 沟通规则 (本次 timeline 严格遵守)
