# 路线 2 (lazy fc cut) — sketch 给用户决策参考

**Status**: 未实施. 路线 1 ❌ dead 后, 用户决策候选之一.

## 思路

路线 1 失败原因: master 端 prebuild 28 万条 "sum(fc at port_cells) >= demand × x_var" 约束, 让 search space 太大解不动.

路线 2: 同 sum >= demand 约束**只对 routing-violated pose lazy 加**, 不 prebuild.

## 工作流

```
iter 1:
  master.solve  → layout L1 (无 fc 约束, baseline 53s OPTIMAL)
  binding.solve → port_specs
  routing.solve / precheck → blocked_ports = [(port_cell, dir, front_cell), ...]
  对每个 blocked_port:
    pose P = identify pose with port at (port_cell, dir) in L1
    add cut: x_var[P] → sum(fc at P's port_cells) >= demand[P]
  master.solve (incremental, +N cuts) → layout L2
  binding.solve → ...
  ...
```

## 关键 hook 点

- `src/search/benders_loop.py:4517-4534` — 现 Phase 5 cell-level cut hook (用 `add_routing_port_blocking_cell_cut`)
- 路线 2 用同 hook, 替 cut form: 从 `sum(port) + sum(blocker) <= 1` (mutual excl) 改成 `sum(fc) >= demand × x_var` (pose-specific demand)
- 实现入口: `PoseBoolExactMasterDelegate.add_routing_port_lazy_demand_cut(...)` (新方法)

## 跟 Phase 5 cell-level cut 的区别

| 维度 | Phase 5 cell cut | 路线 2 lazy demand cut |
|---|---|---|
| Form | `sum(port_pose) + sum(blocker_pose) <= 1` mutual excl | `x_var[P] → sum(fc at P's port_cells) >= demand[P]` |
| 强度 | 弱 (只切一对 (port, blocker)) | 强 (per-pose demand 强制) |
| 跨 pose 泛化 | 是 (整类 pattern) | 不 (per-pose) |
| Phase 5 实测 | 5 iter 1587 cuts 不收敛 | TBD |

## 风险

1. **数量爆**: Phase 5 实测每 iter 500-610 blocked ports → 5 iter ~3000 cuts. 路线 2 同数量级 cuts. master 加 3000 个 sum >= demand 约束跟 prebuild 28 万差几个数量级, 但仍可能让 search space 不收敛.
2. **每 cut 加 fc vars**: lazy 加 cut 时, fc 变量也得 lazy 新建 (port_cells 对应 fc 之前 model 里没有). 增量 model size 复杂.
3. **fc 联动复杂**: fc 约束依赖"所有占 front cell 的 pose vars" — 这是 cross-cell coupling, 加一个 fc 触发联动很多 pose vars 的 propagation. lazy add 可能让 CP-SAT incremental sat 重启很多 search tree.

## 估时 (Claude pace)

- 实施: 2-4 Claude day (~150-300 LOC 加 `add_routing_port_lazy_demand_cut` + 改 benders_loop hook + 测试)
- 实测: 1 trial (30 min wall) 看是否收敛
- 风险 wall: 不收敛, 跟 Phase 5 同结局

## 决策建议

路线 2 是 path-1 失败后**唯一仍在 B1 paradigm 内的 incremental option**. 但**预测概率收敛 < 30%** — 因为:
- master.solve 加约束就慢的 fundamental issue 没解
- 每次反馈 cut 强度无法 generalize 跨布局
- Phase 5 实测同框架 cut 已不收敛

若用户选路线 2 而它不收敛, B1 paradigm 真死路, 项目得 paradigm shift / 接受 verdict / L11.

替代: 直接跳到 paradigm shift (column generation / problem reformulation) 或接受 verdict.
