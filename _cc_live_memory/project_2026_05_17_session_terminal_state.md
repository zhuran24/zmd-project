---
name: 2026-05-17-session-terminal-state
description: "2026-05-17 session 终态 (压缩 context 前): 整天进展 = L15 set-packing prover ❌ + Step D power_coverage 锁瓶颈 + GPT v10/v11 review packaging + Phase 0 lazy power completion ❌ + Phase 3 deletion core ❌ → L16 ❌. 用户决策走 B1 (pose-bool master rewrite). 14 lever 全 verdict. B1 起步前. 5 commit: 905a64d / bad3a9c / 5d37321 / b40bbe9 / 202bf09. Working tree clean."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

## 2026-05-17 session 整天进展

### 上半场 (跟 GPT 互动)

1. **L15 set-packing prover ❌** (commit `bad3a9c`): GPT 推荐的 set-packing branch-and-bound prover paradigm 攻错层. minimum set-packing 核心 CP-SAT 几秒搞定 (corner 2.3s INFEASIBLE, interior 7s feasible 8w), 真瓶颈在 master 多余约束 (port/power/connector/boundary).

2. **Step D power_coverage 锁瓶颈** (commit `905a64d`): layer-by-layer isolation 实测 — `skip_power_coverage=True` 后 master.solve 65.9s 完整 2 LBBD iter (vs 30 min UNKNOWN); 加 +132% vars + 90% constraints; 真瓶颈精确锁到 `_add_geometric_power_coverage_constraints` (`src/models/exact_coordinate_master.py:5327`).

3. **GPT v10 + v11 review packaging** (zip `~/linwin_share/zmd_code_v10.zip`, SHA `2e2f23ce...`): 5.8 MB 8 文件含 PROMPT.md + findings/ + code.tar.xz at HEAD `905a64d`. GPT v11 详细计划书 (Lazy Power Completion 架构).

### 下半场 (实施 GPT v11)

4. **Phase 0 mini-PoC ❌** (commit `5d37321`): 加 `EXACT_LAZY_POWER_COMPLETION` flag (PROJECT_LOCK L4b), master skip coverage 但留 pole slot. 27×15 anchor (22,28) master.solve **81.8s OPTIMAL** (vs production 30 min UNKNOWN — master 端方向真对). 但 completion subproblem INFEASIBLE 134/220 uncovered. Loose nogood cut 10 iter 134→133 stuck 7 iter, 0 收敛.

5. **Phase 3 deletion-based core minimizer ❌** (commit `202bf09`): `scripts/phase3_core_minimizer.py` linear deletion + powered-first order (实测 non-powered-first 浪费 oracle). cut size 220→6 (-97%), 6 iter 134→125→133→133→133→123 振荡不收敛. Instance-level Benders cut 在 problem geometry 下 fundamental 不够.

6. **L16 ❌** (`lever_verdicts.md`, commit `b40bbe9` + `202bf09`): Phase 0 + Phase 3 综合 verdict 死. master 端 paradigm 对, cut 端 instance-level 不够. 跟 [[highs-rewrite-blocker]] 同根因.

### 用户决策

7. **走 B1: pose-bool master rewrite** (3-4 day verdict, 6-9 day full). Memory: [[b1-pose-bool-master-rewrite-plan]]. 关键正信号 = Step B 7.2s FEASIBLE.

## 累计 lever verdict 总账

| Lever | 类型 | Verdict |
|---|---|---|
| L1-L10 | 工程优化 / paradigm 早期 | ❌ |
| L11 | 牺牲严格性 | 🟡 用户拒绝 |
| L12 v8 anchor slicing | GPT 算法错估 | ❌ |
| L13 v10 witness preflight | GPT 前提错估 | ❌ |
| L14 weighted occupancy | 数学能力上限 | ❌ |
| L15 set-packing prover | paradigm 攻错层 | ❌ |
| **L16 lazy power completion** | **master 端 ✓ cut 端 ❌** | ❌ |
| B1 pose-bool master rewrite | 待试 | **🟡 起步前** |

14 ❌ + 1 待试 + 1 用户拒绝 = 16 条 lever 状态全清.

## 5 个 commit 这一天

- `905a64d` Step D layer isolation: 真瓶颈锁到 power_coverage encoding
- `bad3a9c` 归档 GPT L15 set-packing prover paradigm PoC verdict ❌
- `5d37321` Phase 0 mini-PoC: Lazy Power Completion 架构 NO-GO (loose cut 10 iter 不收敛)
- `b40bbe9` docs: 加 L16 lazy power completion phase 0 verdict 到 lever 表
- `202bf09` Phase 3 deletion-based core minimizer + tight cut trial: L16 ❌ verdict 死路

## 关键 trap / 反复掉的坑

1. **Step D `skip_power_coverage=True` 数据 misleading**: `_calculate_power_pole_slot_upper_bound` 在 skip=True 时早退, pole slot 完全不创建. Step D vars=24824 是 NO POLE SLOT 的 baseline; 真 lazy completion 模式 (skip coverage + 留 pole slot) vars=54616 +30K. GPT v11 计划书 26K vars 阈值是错估.

2. **Minimizer deletion order**: 第一版 non-powered-first 浪费 oracle (boundary_port 删后 layout 仍 INFEASIBLE, 跟 power coverage 无关). 改 powered-first 才暴露真 core 6-instance.

3. **m.solve() 0.0s INFEASIBLE 数据无效** (L15 中间发现): isolated build 没 fully wire model, presolve fold 到空. 之前差点据此 verdict L15 死. 救场: realize 数据无效 + 跑完整 LBBD pipeline 数据.

4. **Monitor 悬空**: trial 3 被 kill 后 monitor `b3mfk6ani` 一直等 grep, 50 min 超时 release. 不影响 work, 但 conversation 会看到悬空 timeout notification. 不当用户输入.

## B1 起步前 working tree state

```
git log -5 --oneline:
202bf09 Phase 3 deletion-based core minimizer + tight cut trial: L16 ❌ verdict 死路
b40bbe9 docs: 加 L16 lazy power completion phase 0 verdict 到 lever 表
5d37321 Phase 0 mini-PoC: Lazy Power Completion 架构 NO-GO
bad3a9c 归档 GPT L15 set-packing prover paradigm PoC verdict: ❌
905a64d Step D layer isolation: 真瓶颈锁到 power_coverage encoding
```

Working tree clean. 当前 branch master. 没 PR.

## 下次接续路径

1. 读 [[b1-pose-bool-master-rewrite-plan]] 拿 entry points + Phase 1-5
2. 开始 Phase 1: 写 pose-bool master core 实现
3. 复用 `docs/research/setpacking_prover_poc_20260517/poc_minimum_setpacking.py` (Step B PoC)
4. Phase 5 verdict trial 在 27×15 anchor (22,28), 目标 < 60s feasible (类比 Step B 7s)

## 链

- [[l16-lazy-power-completion-phase0]] — L16 完整 verdict
- [[l15-setpacking-prover-dead]] — L15 ❌ + Step B 数据
- [[b1-pose-bool-master-rewrite-plan]] — B1 完整 plan
- [[30gb-real-culprit-power-coverage]] — power_coverage 是真大头
- [[2026-05-16-session-final-state]] — 上一 session 终态
- [[work-time-estimates]] — Claude pace 估时
- `docs/lever_verdicts.md` — 完整 lever 表
- `~/linwin_share/zmd_code_v10.zip` SHA `2e2f23ce...` — GPT v10/v11 input
