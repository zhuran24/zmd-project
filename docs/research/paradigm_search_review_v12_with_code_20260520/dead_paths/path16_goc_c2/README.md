# Path 16 — GOC-C2 (Global Optional-Owner C2 Core)

## 当前项目情况

Path 15 (正向 witness) 死后. 4 paradigm 死. GPT v5 review.

## 为什么走这条路

GPT v5 选路 2 (新 paradigm): GOC-C2. **全图 owner-optional relaxation + virtual terminal + assumption core 抽 master combinatorial nogood cut**. paradigm 设计绕开 PGW-UB 的 "(2) 无 spatial locality" — 全图 core 可跨整张 70×70 grid 分散.

GPT 自报 "绕开 (2) 无 spatial locality" + "不撞 (1) 全局耦合 因为全图建模是 sound 来源".

## 实验过程

2 个 trial:

### Trial v1 实施 bug
production routing precheck 在 master OPTIMAL layout 上 detect front_blocked, 触发 `model.Add(0 == 1)` 短路, 没真 build 全 routing vars. Kill.

### Trial v2 monkey-patch analyze 强返 feasible + active_cells = 全 free_cells
模拟 GOC virtual terminal 最大放宽. anchor 1 跑 30 min 未出数据.

## 实验结果

| metric | GPT plan target | 实测 | 偏差 |
|---|---|---|---|
| routing_vars_p95 | ≤ 180,000 | ~1,500,000 (estimate) | **8x off** |
| peak RSS | ≤ 12 GB | **≥ 25 GB** | **2.1x over** |
| separator_wall_p95 | ≤ 25s | 30 min build 未完成 | TIMEOUT |

CP-SAT model build 30 min 未完成. **Pre2 资源前提直接 fail**.

## 经验跟教训 (含瓶颈理解更新)

- **撞的是 GPT 声称不撞的 (1) 全局耦合**. 全图 multicommodity routing CP-SAT 任何 sound encoding 都需 per (cell, layer, commodity, pattern) BoolVar, vars 1.5M scale 直接撞 47 GB cap.
- **production routing 之所以能跑** (Path 11/14) 是因为 `analyze_exact_routing_domain` 用 routing-precheck 缩 active_cells. GOC paradigm **不能用**这种短路 — 它就要绕过 precheck. 这是 paradigm 设计 vs 资源约束的 fundamental 矛盾.
- **瓶颈理解更新**: 5 paradigm 后 meta-finding 升级到 **3 大类 paradigm framework 都死了** (局部反馈+master cut / 正向 witness+UB / 全图 owner-optional+sufficient core). production scale 全图建模 vars 1.5M+ 必撞 47 GB.
- **GPT v7 Proposition 2 论证产生**: 任何 routing-aware master form 必落 3 类资源 dead end. 这次 + 后续 augmented master 是双次实测 confirm.

## code/

- `code/` 含 paths/16_global_optional_owner_core/phase0_goc_probe.py (~340 LOC trial script)
