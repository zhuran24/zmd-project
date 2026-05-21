# 266 Mandatory facility breakdown (硬实测分布)

数据来自 `data/preprocessed/mandatory_exact_instances.json` (commit 5469885).

## Facility type 分布

| Facility type | 数量 | footprint | % 占总 cell | 备注 |
|---|---|---|---|---|
| `manufacturing_3x3` | 132 | 3×3 = 9 cells | 1188 cells (24.2%) | 最多, crusher/refinery/assembler/separator/centrifuge/heater 等 |
| `manufacturing_5x5` | 49 | 5×5 = 25 cells | 1225 cells (25.0%) | 大型 manufacturing (含液罐 / 反应炉) |
| `boundary_storage_port` | 46 | 1×3 = 3 cells | 138 cells (2.8%) | **必须贴 grid 边界 (perimeter)** |
| `manufacturing_6x4` | 38 | 6×4 = 24 cells | 912 cells (18.6%) | 中型 manufacturing |
| `protocol_core` | 1 | varies | ~16-25 cells | 1 个, 中央 hub |
| **Total** | **266** | — | **~3479 cells (71%)** | mandatory footprint 总占用 |

## 关键 geometric 数据

- **Grid total**: 70×70 = **4900 cells**
- **Mandatory footprint**: **~3479 cells** = **~71%**
- **Belt / power_pole / connector / ghost rectangle cell 共享剩 ~1421 cells**
- **Boundary perimeter cells**: 70×4 - 4 = **276 cells** (4 边)
- **46 boundary_storage_port × 3 cells = 138 cells** 必须占在 perimeter 上
  → boundary occupancy = **138 / 276 = 50.0%** (一半 perimeter 被 boundary
  storage port 锁定)

## 利用率 stress

不止 mandatory facility 占 4900 cells 中的 71%. 还要:
- power_pole coverage (每 facility 需要 ≥ 1 个 power_pole 在 coverage radius
  内, power_pole 自己占 1 cell)
- belt routing (port → port 路径占 cell)
- connector (manufacturing facility 间的 IO 接驳)
- ghost rectangle (max_lex objective 要求, 占 ~400-600 cell 留空)

实际 effective utilization ≥ **96%** in 高 ghost area candidate (e.g. ghost
27×15 = 405 cells 留空 → free cells = 4900 - 405 = 4495 → mandatory + belt +
pole 等约 4300 cell 都要塞进这 4495 个 free cell, 利用率 = 4300 / 4495 =
95.7%).

## 单 facility footprint = pose 数推算

每 facility 有 4 个 orientation × 2-3 port_mode = 8-12 个 pose. footprint
大 → pose 数 × pose 占用 grid cell 数 都大. 实测 pose_data_count 总数:

- `manufacturing_3x3` (132 个 × ~10 pose) = ~1320 pose
- `manufacturing_5x5` (49 × ~8 pose) = ~392 pose
- `boundary_storage_port` (46 × ~3-4 pose, 因为受限 perimeter side) = ~150 pose
- `manufacturing_6x4` (38 × ~10 pose) = ~380 pose
- `protocol_core` (1 × varies) = ~5-10 pose
- **每 mandatory group 总 pose** ≈ 2200-2300

加上 power_pole pose 数 (residual_optional, 总池 ~5000) + ro_{t,p} (protocol
storage box etc.) → master 总 pose vars ≈ **285K** (实测 27×15 anchor).

## 5 类 facility 各自 IO / port 特征

| Facility | input ports | output ports | port direction constraint |
|---|---|---|---|
| `manufacturing_3x3` | 1-2 个 | 1-2 个 | 4 side 任一 |
| `manufacturing_5x5` | 2-3 个 | 1-2 个 | 4 side 任一 |
| `boundary_storage_port` | 1 个 (外界入) | 1 个 (内界出) 或反 | **外侧必须贴 perimeter, 内侧朝内** |
| `manufacturing_6x4` | 2 个 | 1-2 个 | 4 side 任一 |
| `protocol_core` | varies | varies | 中央 hub |

`boundary_storage_port` 的 "外侧朝外" 是 **geometric hard constraint** — 不
是 routing soft preference. 这制约了 46 个 facility 的可能 pose 集 (每个只能
4-6 个 pose 而不是通常的 8-12 个), 也是 v3 cand C 在 160/266 inst RMP 0 iter
INFEASIBLE 的几何根因.

## 跟 5 cut family 的潜在 mapping

| Facility class | 潜在对应 cut family |
|---|---|
| `manufacturing_3x3` × 132 同质 | 强 symmetry-lifted cut 机会 (同 footprint + 同 IO spec → cluster-wise no-good) |
| `manufacturing_5x5` × 49 + `manufacturing_6x4` × 38 | region capacity cut + pattern no-good |
| `boundary_storage_port` × 46 | perimeter port exposure cut (强制贴边的 capacity constraint) |
| `protocol_core` × 1 | 没 symmetry, 当 pattern fixed seed |
| ghost rect candidate 区域 | cutset cut + component reachability cut |

详 design 5 cut family 定义见 `03_B_DESIGN_DETAILS/5_cut_family_definitions.md`.
