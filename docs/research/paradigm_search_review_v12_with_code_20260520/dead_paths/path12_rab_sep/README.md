# Path 12 — RAB-SEP (Routing-Aware Binding Separator)

## 当时项目情况

B1 Phase 6 path-1/path-2 全死后. 16 lever 累积. GPT review v1 给新 paradigm.

## 为什么走这条路

GPT v1 plan: binding-side 前置过滤 (port front-free + component-consistent) + clear-deficit cert (owner_pose + blocker_poses) 反馈 master. paradigm 在 binding-side 抽 routing-aware cert tight → master no-good cut.

## 实验过程

实施 (commits `7616eb2` + `0fc947d` + `559be9c`):
- `src/models/routing_binding_context.py` 新建
- `src/models/binding_subproblem.py` 加 filter
- `src/search/benders_loop.py` empty_domain branch cert

Phase 5 multi-anchor trial: 8 anchor × max_iter=10, master_seconds=180.

## 实验结果

cert tight (median 3, p90 4-5 远 < 60 阈值) 但 **8/8 anchor UNPROVEN**. master 加 200+ cert 后系统性给 routing-infeasible layouts.

## 经验跟教训 (含瓶颈理解更新)

- **paradigm 端到端 land ✅ 但 breakthrough ❌**.
- **Root cause**: cert 切空间太局部. master 加 cert 后选 layout L2 — L1 cert tight 不 imply L2 routing-feasible.
- binding-side **必要条件**前移 paradigm 不够 sufficient.
- **瓶颈理解更新**: cut 是 necessary 不 sufficient — 这是 paradigm investigation 首次 explicit 认识到这点.

## code/

- `code/` 含 routing_binding_context.py 实施
- 实施: `shared_infra/src/search/benders_loop.py` empty_domain branch + `shared_infra/src/models/binding_subproblem.py` filter
