---
name: phase3a-ip-delivery-readme-cleanup
description: "Phase 3A IndustrialPlanner delivery line 已冻结, README 第一屏过期; Phase 3B 核心代码完工后改 README + 修 audit 撞墙"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**当前状态 (2026-05-14)**:

- Phase 3A IndustrialPlanner single-base delivery line 已冻结 (release `r20260416`)
- 但 README 第一屏 (项目根 `README.md`) 还把它当 user-facing 主入口推荐, 包括 `scripts/audit_industrial_planner_single_base_delivery_surface_alignment.py`
- 这个 audit 工具有**设计闭环漏洞**: 读 `.artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.{json,md,txt}` 当 baseline, 但 `.artifacts/` 全 gitignored → 任何新 clone / CI / 外部审查环境 (GPT v4 沙盒就撞了) 跑就 exit 2
- 开发阶段确认**没有外部用户依赖** IP delivery 入口 (Endfield 玩家社区不直接用我们的仓库; vendored IP snapshot 是单向的)

**决定**: 选项 D — 等 Phase 3B 核心代码完工后:

1. README 第一屏改成 Phase 3B exact proof 当前 runbook (`python main.py --campaign-hours 168.0 ...`)
2. IP delivery 那一屏移到 `docs/` 作为 "历史交付线参考" 章节
3. `audit_industrial_planner_single_base_delivery_surface_alignment.py` 撞墙问题一并解 — 推荐做法: artifacts 缺时 graceful skip + 文档说明先跑 `build_industrial_planner_single_base_delivery_release.py`

**Why 不现在做**:

- 这是外围交付层, 不影响核心 exact proof
- Phase 3B 进行中, 改 README 第一屏要等 phase 完成才能定稿
- 当前 GPT v4 audit 撞墙是外部审查环境问题, 不影响开发

**触发时机**: 168h campaign 跑完 + Phase 3B 拿到 `search_exhausted_all_candidates` certified close 后, 做 release 收尾时一起改.

**相关文件 (到时候改)**:
- `README.md` (项目根, 第一屏)
- `docs/` (新建一个 phase3a 历史交付线参考)
- `scripts/audit_industrial_planner_single_base_delivery_surface_alignment.py` (graceful skip)
- 可选: `scripts/build_industrial_planner_single_base_delivery_release.py` 入口文档化

跟 [[phase3b-progress]], [[keep-review-process-light]] 关联.
