---
name: 2026-05-16-session-final-state
description: "2026-05-16 session 终态: GPT 三次出招 (v8 / v10 / L14) 全 verdict 死. 累积 12 条 algorithmic lever 全死路 (L1-L10 + L12 + L13 + L14). 严格性 + 算法层穷尽. 剩下 paradigm-level option: L11 牺牲严格性 (用户拒绝) / L6 AI sidecar long-term / set-packing prover (paradigm 投资) / 改数据 (扩 blueprint + 改 greedy)."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

## Session 终态 (2026-05-16)

主线: GPT Pro 三次出招攻 master.solve UNKNOWN 瓶颈, 全死. 加料 prompt 实测起作用 (L14 GPT 第一次诚实列 caveat 且应验), 但方向 sound 也不破局.

## Session 三个 commit

| Commit | 内容 |
|---|---|
| `634c0bd` | v8 anchor slicing verdict ❌ — 算法错估 (关注 anchor choice 而非 facility placement) |
| `9991843` | v10 witness preflight verdict ❌ — 前提错估 (要求 complete witness 我们没) |
| `36e08a0` | L14 weighted occupancy PoC verdict ❌ — 数学能力上限 (GPT 没错估) |

每个 commit 含 docs/research/{v8,v10,l14}_*_20260516/ 完整数据归档.

## 累积 12 条 lever 全 verdict 死

| Lever | 类型 | 状态 |
|---|---|---|
| L1 RAM 优化 | 工程 | ❌ |
| L2 换 solver (HiGHS / SCIP) | paradigm | ❌ |
| L3 OR-Tools 参数 | 工程 | ❌ marginal |
| L4 power placement 拆 subproblem | 工程 | ❌ PROJECT_LOCK 禁 |
| L5 OR-Tools 9.16 | 等更新 | ❌ 不值得 |
| L6 AI sidecar | paradigm | 🟡 long-term |
| L7 community hint | 工程 | ❌ (D step 2 完整 land 仍 UNKNOWN) |
| L8 search profile 切换 | 工程 | ❌ |
| L9 objective relaxation | 工程 | ❌ |
| L10 加 time + worker | 工程 | ❌ |
| L11 hard constraint | 牺牲严格性 | 🟡 用户拒绝 |
| **L12 v8 anchor slicing** | 算法错估 | ❌ |
| **L13 v10 witness preflight** | 前提错估 | ❌ |
| **L14 weighted occupancy** | 数学能力上限 | ❌ |

## 剩下 paradigm-level option (没一条 light-weight)

1. **Set-packing prover** (GPT 推荐, L14 升级版): branch-and-bound 在 integer 变量搜, LP 当下界. 写 prover 1-2 周 Claude pace, 单 anchor prove wall-clock 几小时-几天, 完整 frontier 几年 wall-clock 物理不可达. PoC 投资 2 周 wall 给 decisive verdict.
2. **L11 牺牲严格性 hard-fix blueprint**: 用户原则上拒绝. 唯一几乎保证拿 incumbent 的路径.
3. **L6 AI sidecar**: 工作量大 + 收益不确定. long-term option.
4. **改数据**: 扩 community blueprint 到 266 个 mandatory facility (用户手加 41 个) + 改 greedy heuristic 尊重 blueprint 空地. 让 L13 / L14 可能复活.
5. **Paradigm shift**: SMT / Z3 + theory plugin / 自己写 propagator / ML 学 cut. 周-月级工作.

## 用户硬约束 (没变)

- 严格性: 必须证全局 max_lex, 不能退化 (L11 拒绝)
- 硬件: 单机 47 GB, 不加机器 / GPU / 云 / 商业 license
- OR-Tools 锁 9.15.6755, 不等 9.16+
- 不准 anecdotal 不可达, 必须形式化证明

## 这次 session 新加 memory

- [[gpt-review-prompt-armor]] — 加料 prompt 三段式 (真瓶颈 / 死路白名单 / 不可达形式化证明要求)
- [[gpt-error-types-taxonomy]] — 区分算法/前提/数学能力 3 种 GPT 错估 type
- [[v8-anchor-slicing-dead]] / [[v10-witness-preflight-dead]] / [[l14-weighted-occupancy-dead]]

## 下次 session 接着什么

1. 用户决定是否投资 set-packing prover PoC (2 周 wall, 决定 paradigm 是否有戏)
2. 或者用户决定接受当前 verdict 转 L11 / 改数据
3. 不要再做 light-weight algorithmic lever (12 条全死, 已穷尽)
4. v9 review 包 (`~/linwin_share/zmd_code_v9.zip`, SHA `79b5d1d7...`) 是 GPT 后续基于的 snapshot, 历史保留

## Pacman freeze 状态

168h campaign freeze 已 unfrozen (5/16 用户解开). 下次跑 168h 之前要重新 freeze (`bash scripts/pacman_campaign_freeze.sh --enable`).

## 链

- [lever verdicts](docs/lever_verdicts.md) — 主线 lever 总账 (12 条死路 + L11/L6 搁置)
- [[d-step2-hint-landed]] — D step 2 baseline 1h UNKNOWN
- [[phase3b-progress]] — Phase 3B 长期进度
