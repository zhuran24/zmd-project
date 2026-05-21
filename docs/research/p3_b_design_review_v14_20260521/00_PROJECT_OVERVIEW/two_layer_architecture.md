# Two-layer architecture (outer + inner)

## Problem (1 段重述)

**输入**: 70×70 grid (4900 cells) + 266 mandatory facility instances (固定数
量, 跨多 facility template).

**输出**: 在 grid 上安置全部 266 mandatory facility + 找到最大空白 rectangle
("ghost rectangle"), 使得 ghost 不跟任何 facility 占用 cell 重叠, 且全图所有
facility port 之间 belt 可路由 (multi-commodity flow feasible).

**Objective** (lex order): `max_lex(ghost.area, ghost.min_side)`. Strict
certified exact — 不接受 ε 松弛.

## 两层分解

```
┌─────────────────────────────────────────────────────────┐
│ Outer layer: ghost rectangle candidate enumeration       │
│   每个 candidate = (anchor_x, anchor_y, height, width)   │
│   按 lex(area, min_side) descending 顺序枚举             │
│   每 candidate 调 inner layer 验是否 certified feasible  │
│   first feasible candidate 即 max_lex 解                 │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼ (每 candidate 一次)
┌─────────────────────────────────────────────────────────┐
│ Inner layer: LBBD (Logic-Based Benders Decomposition)    │
│                                                          │
│   ┌────────────────────────────────┐                     │
│   │ Master (CP-SAT, pose-bool form)│                     │
│   │   决: facility placement       │                     │
│   │       + pose 选择              │                     │
│   │       + power_pole coverage    │                     │
│   │   ghost rectangle 当 forbidden │                     │
│   │   cells 区域 (强制空白)        │                     │
│   └────────────────────────────────┘                     │
│                  │ OPTIMAL → layout                      │
│                  ▼                                       │
│   ┌────────────────────────────────┐                     │
│   │ Binding sub-problem (CP-SAT)   │                     │
│   │   选: port → commodity 映射    │                     │
│   │       (每 facility 多种 port   │                     │
│   │        spec 合法绑定)          │                     │
│   └────────────────────────────────┘                     │
│              │ FEASIBLE   │ INFEASIBLE                   │
│              ▼            ▼                              │
│   ┌────────────────────┐  cut → 加回 master              │
│   │ Routing sub-problem│  重 solve master                │
│   │   (CP-SAT or flow) │                                 │
│   │   belt 路径        │                                 │
│   │   multi-commodity  │                                 │
│   │   flow on grid     │                                 │
│   └────────────────────┘                                 │
│        │ FEASIBLE  │ INFEASIBLE                          │
│        ▼           ▼                                     │
│    candidate    cut → 加回 master                        │
│    certified                                             │
│    feasible                                              │
└─────────────────────────────────────────────────────────┘
```

## Outer layer 细节

- 总 candidate 数 ~ O(70^4) = ~24M raw, 经 lex-sort + dedup + ghost area ≥
  threshold filter 剩 ~50-500 个 reachable candidate
- 实测最大可达 ghost area 在 405-600 范围 (27×15 ~ 24×25 等), min_side 通常
  ≥ 10
- candidate 之间没有 share state — 每个 candidate 独立 LBBD 跑

## Inner layer 细节 — 当前 pose-bool master form

master 内部:

```
变量:
  x_{i, p}    BoolVar  per (mandatory_group_id, pose_idx)            # 主变量
  ro_{t, p}   BoolVar  per (required_optional_template, pose_idx)    # protocol_storage_box 等
  pole_{p}    BoolVar  per (power_pole, pose_idx)                    # residual_optional

约束:
  AddExactlyOne(x_{i, *})           # 每 mandatory group 恰好 1 pose
  AddAtMostOne(x_{*,p} : cell c)    # 每 cell 至多 1 pose 占用
  x_{g,p} → ∃ y_{coverer_pole}      # power coverage
  ghost cell ∈ {∅}                  # 强制 ghost 空白
  (env-gated) symmetry / SAC-Hull / port_active 等增强

scale (27×15 anchor):
  vars ≈ 285K
  constraints ≈ 280K
  solve ~50-100s OPTIMAL (8 workers, 180s budget)
```

binding sub-problem: 给 master OPTIMAL layout, 每 facility 多种 port-binding
spec, CP-SAT 选哪些 spec active (覆盖所有 demand commodity). 通常 0.1-1s 出
verdict.

routing sub-problem: 给 master + binding fixed 后, 检查 belt 路径是否 grid
可行 (multi-commodity flow). 一般 30-60s.

## 跟 P3 Design B 关系

Design B 重写的是 **inner layer 的 master + cut store + sub-problem oracle
infrastructure**, 不动 outer layer.  Outer 保留是因为 candidate 枚举本身就
是 max_lex 搜索的正确算法, 没有要 break 的地方.

Inner master 当前是 CP-SAT pose-bool form, B 设计要换成自研 state machine.
sub-problem 端 (binding / routing) 复用现有 oracle, 当 black-box feasibility
检验器使用.

## 资源约束 (来自 PROJECT_LOCK)

- Single machine i9-13900KS + 48 GB DDR5 (4-parallel 模式 12 GB/process)
- 168 h wall budget (single campaign)
- 每 anchor budget: ~600-1000s master + ~30s binding + ~60s routing + ~10s flow
- CPU: 8 P-core (5.6 GHz) + 16 E-core, P-core taskset pin
