# Known unsolved issue: boundary_storage_port × perimeter trap

## 现象描述

`boundary_storage_port` × 46 个 facility, 每个 1×3 footprint, **必须沿
grid 边界放置** (外侧朝外, 内侧朝内, 中间夹 1 cell). 46 × 3 = 138 cells 锁
死在 perimeter 上.

Grid perimeter = 70 × 4 - 4 (角去重) = 276 cells.

→ **138 / 276 = 50% perimeter cell 锁定**.

## 为什么是 trap

### Trap 1: ghost rectangle 跟 boundary port mutual exclusion

ghost rectangle (max_lex 解的产物, area 400-600) 在 grid 内部或贴边. 若
ghost 占某一边:
- ghost 27×15 沿 north edge → north edge 可用长度 = 68 - 27 = 41 cells
- 但 north edge 还要塞 12 个 boundary_storage_port × 3 cell = 36 cell
- 实际 north edge 利用率 = 36 / 41 = **87.8%**, 几乎填满
- 任何 boundary port 位置 ±1 cell 偏差都让 north edge 装不下

### Trap 2: boundary port 跨 4 edge 的均衡分布

46 个 boundary_storage_port 跨 4 edge:
- 平均每 edge ~12 个 = 36 cell
- 若分布不均, 某 edge 塞 15+ 个 → 45 cell, 一边 70 cell, 加 ghost 占
  10+ cell, edge 撞 boundary
- 实测哪种 instance assignment 让 edge 均衡: source-of-truth 没指定, 是
  optimizer 自由

### Trap 3: boundary port × ghost rect corner

ghost rect corner 是 (anchor_x, anchor_y), 若 anchor 贴边 (e.g.
anchor_x = 0), corner cell 是 perimeter cell, 同时是 ghost 的 cell.
boundary port 不能占这个 cell (因为 ghost forbid), 但 boundary port 候
选 pose 池可能 list 这个 cell — pose pool filter 必须 ghost-aware.

→ 这是 cand C `ghost_filtered_count = 10710` (从 80K pose pool 滤掉 10K
overlapping ghost) 的来源.

### Trap 4: boundary port 的 IO direction × pose 限制

外侧朝外 + 内侧朝内 ≈ "port direction 跟 boundary edge 强耦合". 每
boundary_storage_port 通常只有 2-3 pose 跟某 edge 兼容 (vs 普通
facility 8-12 pose).

134 个 boundary_storage_port pose total (cand C Phase 2 v3 实测) /
46 facility = 平均 2.9 pose / facility. 比 manufacturing 类 ~10 pose
少 ~3x.

## 实测撞这个 trap 的 verdict

- **Cand C v3 160/266 inst RMP 0 iter INFEASIBLE**: bootstrap 给 218
  /324 column cover all inst individually 仍 LP infeasible. 关键是
  boundary port 134 pose 池跟 ghost-filtered cell 形成的 partition
  contradiction.
- **B1 Phase 4 routing convergence**: front_blocked ~500-610 ports, 其
  中 boundary port 占 ~150 (46 × 3-4 / pose × routing). boundary port
  跟 perimeter 强耦合时 routing graph cut 强.
- **Path 15 PGW-UB Phase 0**: top5_cov 0.046 vs target 0.55, blocked_owners
  276-327 vs ≤120. blocked_owners 跟 boundary port 强相关.

## 跟 B 设计的关系

B 设计的 **port_exposure cut family** 直接编码 boundary port direction
× perimeter cell exposure:

```
对 facility i 是 boundary_storage_port, 外侧 port at (x, 0) facing N,
front cell (x, -1) 必须 grid boundary (即外界, 不是 facility 占用),
内侧 port at (x, 1) facing S, front cell (x, 2) 必须 free.
```

LP partition framework (cand C) **不能 natural 表达** "perimeter 是 grid
边界" 这层 (因为 LP variable 是 cell-level λ, perimeter 不是 LP var, 是
geometry).

B 的 state machine + bitset 能直接编码: perimeter cell mask 是 fixed
bitset, port_exposure cut family resolve 时 mask & operation.

## 还没解的部分

1. **boundary port × ghost corner 的 pose filter**: 实施层细节, cand C
   `ghost_filtered_count = 10710` 已部分 cover. B 实施需要复用 + 验证
2. **boundary port 跨 edge 均衡**: 是否需要新 cut 强制 each edge port
   count ≤ edge length capacity? 这是潜在 第 6 类 cut?
3. **boundary port × 内侧 routing**: port 内侧 belt 必须能 route 到内
   commodity sink. routing constraint 跟 boundary port 强耦合, oracle
   需要专门 cert path

## Stress test 视角

构造恶魔构型起点之一: 46 个 boundary port 在 4 edge 分布**最不均**的
配置 + ghost rect 占据该 edge 大部分. 验 5 cut family 能否识别 infeasibility.

可能的反例: ghost = 27×15 占 north edge 整段, 加 boundary port 分布如
north=20, south=14, east=6, west=6. north edge 实际占用 27 (ghost) + 60
(20 port × 3) = 87 > 70 edge length → infeasible. 但 5 cut family 哪类
能识别?

- region capacity (R = north edge perimeter): cap_R = 70, used = 87, cut
  triggered ✅
- port_exposure: 每 port 单独 check, 不识别 aggregate over-capacity
- cutset: 不直接 cover
- component_reach: 不直接 cover
- pattern_nogood: 需要 sub-problem cert 才能产

→ 看起来 region capacity cut 能 cover. 但如果 ghost 占 27 cell 但 boundary
port 分布是 16/12/9/9 = 总 138, north edge = 16 × 3 + 27 = 75 > 70, **越
微小越难识别**, region capacity 的 cap_R 计算需要 ghost-aware.

计算需要超过简单累加 (e.g. cap_R 需要 dynamic 跟 placement 配合调).
