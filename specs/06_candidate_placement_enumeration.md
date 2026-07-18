---
status: CURRENT_CODE_ALIGNED
source_of_truth: src/placement/placement_generator.py, src/placement/occupancy_masks.py, and data/preprocessed/candidate_placements.json
last_verified_against: 2026-07-18 (Batch 3 identity-domain regeneration and Batch 5 physical box geometry)
owner: placement-preprocess
---
# 06 候选摆位枚举与几何降维引擎 (Candidate Placement Enumeration)

## 6.1 文档目的与适用范围

本文档规定了如何将连续的二维网格排布空间，彻底离散化为一个有限的、预计算的**“合法候选摆位集合 (Candidate Placements Set $\mathcal{P}$)”**。

在传统运筹学中，若直接令求解器在连续坐标系内寻找 326 个刚体的 $(x, y)$ 坐标并规避重叠，将引发 $\mathcal{O}(4900^{326})$ 的维数灾难。（此处 326 = 266 必选 + exploratory 参考的 60 可选；**certified_exact 实际可选数为变量 / demand 驱动、无硬 50/10/60 cap**，见 02 章脚注 † 与 07 章 §7.4.1 后 [PROJECT_LOCK 对齐] 注。）
本章的战略是**“几何预计算降维”**：在进入运筹主模型前，利用一段高效的 Python 几何引擎穷举所有合法的平移、旋转与端口模式，将一切越界、死角的废解当场抹杀。最终，底层求解器拿到的不再是空间坐标，而是一道极其纯粹的**“0-1 集合打包单选题 (0-1 Set Packing Problem)”**。

---

## 6.2 模板级候选池映射 (Template-based Pooling)

为极大地压缩内存占用与预处理文件体积，本系统**绝对禁止**为 326 个具体实例（如 51 台等价的精炼炉实例；注：此 326 = 266 必选 + exploratory 参考的 60，见 §6.1 [PROJECT_LOCK 对齐] 注，非 exact 硬数）分别独立生成位置字典。

由于同种模板的设施在物理轮廓与端口几何上完全同构，几何枚举引擎必须且只能按**设施模板 (Facility Template)** 进行扫描。
定义 $\mathcal{T}$ 为全场存在的设施模板集合（例如 `manufacturing_square_3`, `boundary_storage_port`）。
扫描引擎为每个模板 $t \in \mathcal{T}$ 生成一个统一的合法摆位集合 $\mathcal{P}_t$。
在后续 07 章主问题求解器中，任何属于模板 $t$ 的实例 $i$，其候选域直接映射共享为 $\mathcal{P}_i \equiv \mathcal{P}_t$。实例间的标签对称性将由运筹学约束破除。

---

## 6.3 候选摆位 (Placement Candidate) 的数据结构

为了让底层运筹求解器做到“零几何计算 (Zero Geometry Math)”，Python 生成器必须在穷举阶段为每一个合法的位姿 $p$ 提前算好所有的投影点集，并序列化为静态结构。

一个合法的候选摆位对象 `Placement` 必须包含以下结果：
*   **`pose_id`** (String): 唯一标识符，格式严控为 `p_x{x}_y{y}_o{o}_m{m}`（例：`p_x12_y34_o1_mNS`）。
*   **`anchor`** (Dict): 绝对锚点坐标 `{"x": 12, "y": 34}`（依据 02 章左下角锚定法）。
*   **`pose_params`** (Dict): 包含旋转状态 `orientation` ($o \in \{0, 1, 2, 3\}$) 与端口边模式 `port_mode` ($m$)。
*   **`occupied_cells`** (List[Tuple]): 该姿态下本体占据的地面层网格绝对坐标集合 $[(x_1, y_1), \dots]$。用于后续极其关键的 $\sum z_{i,p} \le 1$ 不重叠约束。
*   **`input_port_cells`** (List[Dict]): 提前解算的可用输入端口物理坐标及其接管向外向量。例：`[{"x": 12, "y": 35, "dir": "W"}, ...]`。
*   **`output_port_cells`** (List[Dict]): 提前解算的可用输出端口物理坐标及其接管向外向量。
*   **`power_coverage_cells`** (List[Tuple] | Null): 仅对供电桩有效，提前算好的 $12 \times 12$ 供电覆盖绝对坐标集合（自动裁剪掉溢出地图边界的部分）。

---

## 6.4 几何遍历法则与物理边界 (Traversal & Bounds)

枚举引擎采用四重嵌套循环遍历空间：$x \in [0, 69]$, $y \in [0, 69]$, $o \in \{0, 1, 2, 3\}$, $m \in \text{AllowedModes}$。

### 6.4.1 制造单位 (3x3, 5x5, 6x4) & 协议核心 (9x9) & 协议箱 (3x3)
*   **平移域**：$x \in [0, 70-w], y \in [0, 70-h]$。（$w, h$ 为当前旋转姿态 $o$ 下的包围盒宽与高）。
*   **模式扩展 ($m$)**：
    *   长方形机器 (6x4)：端口强制分布在两条长边上，无需额外模式枚举。
    *   方形机器 (3x3, 5x5)：在每个合法 $(x,y,o)$ 下，必须生成两组正交的端口模式：模式 `NS` (上下边作为出入口) 与模式 `EW` (左右边作为出入口)。
    *   协议箱 (3x3)：与制造机 3×3 **完全同款**实体口形态（一边 3 进/对边 3 出、四种正交端口模式；owner 游戏实测定谳 2026-07-18，权威 `docs/research/rules_audit_20260718/00` §3.1），经标准方形枚举路径生成；"无线"仅存在于箱→仓库段，不影响端口几何。**历史勘误**：旧文的 `omni_wireless` 零口形态（`port_mode="omni"`、闭式 $68 \times 68 = 4624$）是错误认知，已随批 5 废除。

### 6.4.2 供电桩的极简扫描 (2x2)
*   **旋转对称性剪枝**：供电桩为绝对正方形且无实体端口，旋转 $o$ 无物理意义，强制锁定 $o=0$。
*   **越界拦截**：本体占格 $x \in [0, 68], y \in [0, 68]$。
*   **覆盖溢出合法性**：供电桩的 $12 \times 12$ 覆盖域**允许超出 $70 \times 70$ 的边界**。算法生成时直接执行交集截断：$X \in [\max(0, x-5), \min(69, x+6)]$，不会导致该摆位非法。

### 6.4.3 边界仓库存/取货口的特异性锚定 (1x3)
该类设施具有最严苛的物理依附规则，绝不进行全图遍历，必须采用**基线强制锚定法**：
1.  **左侧基线锚定**：固定 $x = 0$。包围盒为竖向 ($1 \times 3$)。$y$ 遍历 $[0, 67]$。端口记录为中间格右侧的 front/带子格 $(1, y+1, \text{E})$（identity 语义：stored 坐标即体外第 1 格）。
2.  **下侧基线锚定**：固定 $y = 0$。包围盒为横向 ($3 \times 1$)。$x$ 遍历 $[0, 67]$。端口记录为中间格上方的 front/带子格 $(x+1, 1, \text{N})$。
*(勘误 2026-07-18：冻结数据实际遍历 $[0, 67]$、含两个拐角 pose（canonical 明确要求保留、两拐角 pose 数据合法），每边 68 个、共 $2 \times 68 = 136$；本 spec 旧文 $[1,66]$/134 是文档错误，数据与 canonical 为准。)*

---

## 6.5 绝对死区剔除法则 (Aggressive Pruning Filters)

在全量生成位姿时，必须应用以下过滤层，将“注定无法连线”的废解当场抹杀，这能削减至少 30% 的无用搜索空间：

### 6.5.1 面壁死锁剔除 (Wall-Facing Port Starvation)
**物理逻辑**：传送带必须占用端口的 routing front cell——**即 port 记录的 stored 坐标格自身**（体外第 1 格；identity 语义，front 错位事故修正 2026-07-18，权威 `docs/research/front_offset_incident_20260718/00`）。真正不可用的是 `(port.x, port.y)` 落到 $70 \times 70$ 网格外。**历史勘误**：本节旧文把判界写成 `(port.x, port.y) + DIR_DELTA[port.dir]`（体外第 2 格）——生成器照此剪枝导致 2,064 个墙距-1 合法 pose（3×3 +544 / 5×5 +528 / 6×4 +520 / core +472）从未进池（66,405 → 应为 68,469）；域补齐随修复批 3（owner 已拍板补域 scope）。
**剔除法则**：
对一个候选位姿分别检查激活输入端口集合与输出端口集合。若某一集合非空，且该集合内所有端口的 routing front cell 都越界，则该位姿视为“绝对面壁废解”，**立刻从 $\mathcal{P}_t$ 中永久删除**；只要同一集合中仍存在至少一个 front cell 留在网格内，该集合不得触发剪枝。
*(例外：边界仓库存/取货口原生豁免此法则，因其天然向内吞吐。协议箱自批 5 起有实体端口、与制造机 3×3 同受此法则约束——旧文"`omni_wireless` 无实体端口豁免"已废。)*

### 6.5.2 旋转对等性去重 (Rotational Symmetry Pruning)
**物理逻辑**：正方形机器在内部配方无方向性时，正放与倒放在占格和端口拓扑上可能完全等价。
**剔除法则**：对于 3x3 和 5x5 制造单位，若其处于模式 `NS`（上下出入），则 $o=0$ 与 $o=2$ 的物理投射完全一致；同理模式 `EW` 下 $o=1$ 与 $o=3$ 完全一致。枚举引擎必须主动剔除这种坐标系别名带来的重复解，仅保留最简基底姿态。

---

## 6.6 幽灵空地动态候选池 (Dynamic Ghost Rectangle Domain)

根据 01 章的外层降序枚举范式，空地矩形 $R_{w,h}$ 的尺寸由外层循环动态给定。
枚举引擎必须暴露出一个独立的空地候选生成接口 `generate_empty_rect_domain(w, h)`：

*   **输入**：外层传入的空地宽度 $w$ 和高度 $h$（已验证 $\min(w,h) \ge 6$）。
*   **遍历域**：平移锚点 $x \in [0, 70-w], y \in [0, 70-h]$。
*   **输出集合属性**：返回的所有位姿均只包含一个纯粹的**绝对禁区集合 `occupied_cells`**。在 07 章主问题中，求解器将从中挑选唯一一个位置，并强制任何其他刚体均不得染指该集合内的任何一个坐标。

---

## 6.7 本章输出规范 (Output Artifacts)

枚举引擎（预处理脚本）的最终使命，是输出一份高度结构化、绝对扁平的 JSON 静态编译文件：
**`data/preprocessed/candidate_placements.json`**

> 当前 GitHub `main` 是 lightweight checkout：production
> `data/preprocessed/candidate_placements.json` 当前存在于工作树中，且仍是 certified
> exact 必需输入。2026-07-18 Batch 3+5 identity 域与协议箱实体口重生成结果必须匹配
> size `53,595,501` bytes, SHA256
> `78e2bcf0777db8523aa767ee689ba7c3e65ecf7ecc20642627876d8d42fa3fef`。此前 F-01/F-02
> 恢复结果 size `45,774,305` bytes / SHA256
> `a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`、拐角修复前的 size
> `45,773,799` bytes / SHA256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0`
> 以及旧 size `53,594,995` bytes / SHA256
> `d5e3911fc1bc7c0ab48d67b981d28e8090741b04884c475e78dc0e128ca4683f` 均已 superseded，且
> hash-incompatible。

当前闭式池计数（identity 判界 + 协议箱实体口，批 3+5，2026-07-18；
每模式合法域 = 进/出两侧 stored 口格均在 $70\times70$ 内）：

| facility_type | closed form | count |
| --- | ---: | ---: |
| `manufacturing_3x3` | `4 * 68 * 66` | 17,952 |
| `manufacturing_5x5` | `4 * 66 * 64` | 16,896 |
| `manufacturing_6x4` | `4 * 65 * 65` | 16,900 |
| `protocol_core` | `2 * 60 * 60` | 7,200 |
| `protocol_storage_box` | `4 * 68 * 66` | 17,952 |
| `power_pole` | `69 * 69` | 4,761 |
| `boundary_storage_port` | `2 * 68` | 136 |
| **total** |  | **81,797** |

历史口径（勘误留档）：错位判界（front=+delta 查体外第 2 格）+ 协议箱零口
时代的总数为 66,405（3×3 `4*68*64`=17,408 / 5×5 `4*66*62`=16,368 /
6×4 `4*65*63`=16,380 / core `2*58*58`=6,728 / 箱 `68*68`=4,624）；
mandatory 补域 +2,064 = 68,469，箱按实体口重枚举 4,624 → 17,952，
合计 81,797。

数据结构范例：
```json
{
  "facility_pools": {
    "manufacturing_rect_6x4": [
      {
        "pose_id": "p_x10_y20_o0_m_long_sides",
        "anchor": {"x": 10, "y": 20},
        "pose_params": {"orientation": 0, "port_mode": "long_sides_io"},
        "occupied_cells": [[10,20], [11,20], ..., [15,23]],
        "input_port_cells": [
          {"x": 10, "y": 19, "dir": "S"}, {"x": 11, "y": 19, "dir": "S"}
        ],
        "output_port_cells": [
          {"x": 10, "y": 24, "dir": "N"}, {"x": 11, "y": 24, "dir": "N"}
        ],
        "power_coverage_cells": null
      }
    ]
  }
}
