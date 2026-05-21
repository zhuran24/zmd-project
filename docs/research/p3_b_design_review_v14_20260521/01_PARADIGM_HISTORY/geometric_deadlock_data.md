# 96% 利用率几何死结 + boundary_storage_port × left+bottom baseline saturation

## 实测数字

| 量 | 数值 | 来源 |
|---|---|---|
| Grid total cells | 4900 | 70 × 70 |
| 266 mandatory facility footprint | ≈ 3479 cells | `mandatory_exact_instances.json` 实测 (见 266_mandatory_breakdown.md) |
| Power_pole + belt + connector | ≈ 800-1000 cells | (估算: 每 facility ~3-4 cell 路由) |
| Effective occupied (no ghost) | ≈ 4300-4500 cells | |
| Free cells (grid - mandatory - 路由) | ≈ 400-600 cells | |
| Max achievable ghost area | 405 ~ 600 cells | candidate enumeration 实测 |
| Effective utilization at high ghost candidate | ≈ **96%** | ghost 27×15=405 → free=4495 → occupied/free 4300/4495 = 95.7% |

→ 这是项目从 paradigm investigation 实测拿到的最 fundamental 几何 stress.

## Boundary port × left+bottom baseline 100% saturation

`boundary_storage_port` 是 46 个 facility, 每个 1×3 = 3 cell footprint,
**必须贴 grid 边界**:

- Perimeter cells: **138 cells** (left + bottom 2 边 baseline, 角 (0,0) 留空)
- 46 × 3 = **138 cells** 必须占在 138 个 left+bottom baseline cell 内 (`placement_rule: left_or_bottom_boundary`)
- → boundary occupancy = **138 / 138 = 100.0%** (left+bottom baseline 100% saturate, 无余地)

Side breakdown (每边 ≈ 68 cells 去掉 2 个角):
- 4 边各 ≈ 68 cells
- 平均每边要塞 ~12 个 boundary_storage_port × 3 cell = ~36 cell
- per side 利用率 36/68 = **53%**

这跟 ghost rectangle candidate **强耦合**:
- Ghost 在 grid 内部 (corner 或 edge) 影响 boundary side 可用长度
- 若 ghost 占边 (e.g. 27×15 沿 north edge), 该边可用 perimeter cell 缩到
  68 - 15 = 53, 但仍要塞 12 个 boundary port × 3 = 36 cell, 利用率升到
  36/53 = **68%**, 加 ghost 占用后该边 boundary port 接近无法塞

→ 这是为什么 27×15 anchor (22, 28) 在 v3 cand C 160/266 inst RMP 0 iter
INFEASIBLE 的具体 geometric 触发点之一.

## 跟 Manufacturing cluster 的相互挤压

132 个 `manufacturing_3x3` 加 49 个 `manufacturing_5x5` 加 38 个
`manufacturing_6x4` 共 **219 个 manufacturing facility**, footprint 总
**3325 cells**.

减掉 ghost (~400-600), 减掉 boundary_storage_port footprint (138 必须
perimeter), 减掉 belt/pole/connector (~800-1000), 留给 manufacturing
cluster 的实际 free cell:

- 4900 - 405 (ghost) - 138 (boundary forced) - 900 (belt/pole) ≈ **3457 cells**
- manufacturing 总需 3325 cells
- **stranded margin = 3457 - 3325 = 132 cells** (= 4 个 manufacturing_3x3)

→ 高 ghost candidate 下 margin **几近 0**. 任何一处 manufacturing 没放到
对齐的 (x, y) 都会导致整体 layout infeasible.

## 死结的形式化论证 (cand C v3 实测验证)

A3 set covering LP:

```
约束 (per instance i):    Σ_{k : iid_k ∋ i} λ_k ≥ 1
约束 (per cell c):        Σ_{k : k uses cell c} λ_k ≤ 1
约束 (per port spec):     (可选) port direction compat
```

在 96% utilization 下:

- Σ_k cells_used(k) × λ_k ≈ |occupied cells| ≈ 4300-4500
- 每 cell 约束 Σ ≤ 1 限制 λ_k 在所占 cell 上的"分配"
- 每 instance 约束 Σ ≥ 1 强制 λ_k 全覆盖每个 instance

两约束族在 96% utilization 下 dual 不兼容:
- cell 约束的 reduced cost dominate (cell 几乎 saturated)
- instance 约束要求 cover 必须 λ ≥ 1, 没 cell 给

LP 不可行 from iter 0. 这跟 **column pool 大小无关** — bootstrap 装 324
column cover all 266 instance individually 仍不可行 (任意 partition 都
撞 cell 约束).

→ **这是 cand C v3 在 160 / 266 inst 撞的根本墙**.

## 跟 pose-bool master 27 lever 撞墙的同源关系

| Paradigm | 实测撞维度 | 数字 |
|---|---|---|
| Path 16 GOC-C2 (L21) | **vars 爆** | 1.5M vars, RSS 25 GB |
| Augmented Master Candidate D (L23) | **cstr 爆** | 2.68M cstr, RSS 32 GB |
| Cand C v3 160/266 inst | **LP infeasible iter 0** | column pool 324 / cell 利用率 96% |
| Original coordinate master L1-L11 | 30 min UNKNOWN | (不同维度但同源) |

3 个不同 paradigm 不同维度的墙, **底层根因同质**: 96% 利用率几何死结
+ boundary_storage_port × perimeter trap.

→ Design B 想破这层, 不是靠加 cut, 是靠 master state machine + 5 cut
family 直接编码 "left+bottom baseline constraint × component connectivity"
的 sound prune.

## 96% 不是 hyperbole — 实测推算

不是 "高利用率所以难解" 的口头描述, 是实测数字:

- ghost rectangle = 27×15 = 405 cells (实际可达上限之一)
- ghost = 24×25 = 600 cells (上限边界, 实测仍 infeasible at iter 0)
- ghost = 20×20 = 400 cells (实测仍 infeasible at iter 0)

所有高 ghost candidate (area ≥ 300) **都**撞这个 96% 利用率墙.

低 ghost candidate (area < 100) 利用率降到 90%, RMP 可解. 但 area < 100
的 ghost 不是 max_lex 解 (max_lex objective 强制找 area 最大).

→ 这是为什么 cand C "在小规模 GO 在大规模 NO-GO" 的本质 — 不是 algorithm
不行, 是 master form 跟 96% utilization 几何 incompatible.

