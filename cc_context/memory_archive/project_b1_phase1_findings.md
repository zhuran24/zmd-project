---
name: b1-phase1-findings
description: "2026-05-17 B1 Phase 1 end-to-end trial 数据 + 代码 audit 发现: master+binding 端到端 PASS (master 52.9s OPTIMAL + binding 0.0s FEASIBLE first solution). routing precheck front_blocked 是 LBBD inner-loop 标准信号需 binding nogood cut, 不是 paradigm 失败. 代码 audit 发现 master_model.py 现有 pose-bool path 已含完整 demand/set_packing/ghost/power_coverage/symmetry/global_valid_inequalities, exact_mode=True 强制走 coordinate_delegate 跳过. Phase 2 真生产 = 加 env flag 在 exact_mode 下绕过 coordinate_delegate. 2 commit: 12f5e64 Phase 0, 237a74b Phase 1."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

## Phase 1 end-to-end trial 数据

prototype 扩展加 PortBindingModel 调用 (`docs/research/b1_pose_bool_phase0_20260517/poc_pose_bool_end_to_end.py`).

27×15 anchor (22,28) interior:

| stage | status | time |
|---|---|---|
| master (pose-bool + power_coverage) | **OPTIMAL** | 52.9s |
| binding first solution | **FEASIBLE** | 0.0s |
| routing precheck | **front_blocked** | < 1s |

**master + binding 端到端 PASS** — 438 instances (266 mandatory + 1 ro + 171 pole) port match 自然成立无 empty domain.

**routing precheck front_blocked** = LBBD inner-loop 标准信号. 第一个 binding solution 经常被 routing reject, 需要加 binding nogood cut 让 binding 选别的 port match 重试. standalone script 没实现这个 inner loop. 不是 paradigm 失败.

## 代码 audit 大发现

`src/models/master_model.py` 现有 **pose-bool path 早已 implemented**, 完整包括:

- `_create_variables` (line 4414): `z_vars[group_id][pose_idx]` BoolVar (pose-bool form)
- `_add_assignment_constraints` (line 4458): `sum z_vars == demand`
- `_add_set_packing_constraints` (line 4502): cell exclusivity
- `_add_ghost_rect_constraints` (line 4509): ghost forbidden
- `_add_power_coverage_constraints` (line 4621): **跟 prototype 数学等价** (`sum(pole_vars[idx] for idx in coverers) >= z_var`)
- `_add_symmetry_breaking_constraints` (line 4658)
- `_add_global_valid_inequalities` (line 4860)
- `_add_search_guidance` (line 4696)

**但 `exact_mode=True` 强制走 coordinate_delegate path** (line 4385-4397), 跳过整个 pose-bool path:
```python
def build(self) -> None:
    if self.exact_mode and self._coordinate_delegate is not None:
        self._coordinate_delegate.model = self.model
        self._coordinate_delegate.build()
        ...
        return
    # 以下 pose-bool path 在 exact_mode 下完全不走
    self._create_variables()
    self._add_assignment_constraints()
    ...
```

## Phase 2 真生产 = 加 env flag 绕过 coordinate_delegate

最简方案: 加 env flag `EXACT_USE_POSE_BOOL_MASTER`. exact_mode=True + env flag on → 走 pose-bool path 而不是 coordinate_delegate.

但**不是 simple bypass** — 现有 LBBD 代码 11+ 处 assume "exact_mode → coordinate_delegate":
- `extract_solution()` line 11670: `if exact_mode and coordinate_delegate is not None` short-circuit
- `add_benders_cut()` line 11737: 同上
- `build_exact_candidate_warm_start()` line 9779: 新 method, 完全建立在 coordinate slot 上
- 多处 `self._coordinate_delegate.<method>` 调用

完整 Phase 2 工作 (估 2-3 Claude day, **修正后 1-2 Claude day**):
1. 加 env flag
2. audit 所有 `if exact_mode and coordinate_delegate is not None` 处, 扩展支持 pose-bool path 或 fall through
3. 写 `build_exact_candidate_warm_start` pose-bool 版 (或证明可跳过)
4. 跑现有 2086 pytest 不 break
5. 跑 LBBD 一次 candidate 端到端

**修正**: 不应该直接 bypass coordinate_delegate 走现有 master_model.py pose-bool path. `probe_existing_pose_bool_path.py` 实测 master_model.py 现有 exploratory + ghost_rect 配置 build() > 4 min 不出 — 未优化. **正确路径**: 写新 `PoseBoolExactMasterDelegate` 平行, 模仿 Phase 0 prototype build 模式 (22s build + 53s solve).

## 已 commit 状态

- `12f5e64` Phase 0: 5 anchor 全 fast verdict (49-53s OPTIMAL × 4 + 20.6s INFEASIBLE × 1)
- `237a74b` Phase 1: end-to-end master+binding PASS, routing 需要 inner loop

Working tree clean. 14 lever 死 + B1 Phase 0/1 GO (Phase 2 待启动).

## ROI 信号

B1 是项目 14 lever 死后第一个 GO verdict. 跟 coordinate-based 30 min UNKNOWN 比快 ~34x. master + binding 端到端跑通是项目突破性进展.

Phase 2 是真生产工作, 应该在新 session 跟用户对齐方向后开始. 单 session push Phase 2 风险:
- master_model.py 是大文件 (11785 行) 改动面大
- exact_mode → coordinate_delegate 假设贯穿 LBBD 代码
- 跑全 2086 pytest 验回归 ~5-10 min
- 改动 break 现有 LBBD test 风险高

## 链

- [[b1-phase0-go]] — Phase 0 完整数据
- [[b1-pose-bool-master-rewrite-plan]] — 完整 plan (Phase 1-5)
- `docs/research/b1_pose_bool_phase0_20260517/` — prototype + 8 trial logs + README
- `docs/lever_verdicts.md` — B1 Phase 0 ✅ 已加入
