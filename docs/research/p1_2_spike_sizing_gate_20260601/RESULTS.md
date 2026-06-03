# P1.2 spike — 真 cut body sizing cheap gate 结果 (2026-06-01; v2 LSB-corrected 2026-06-02)

## ⚠️ v1 → v2 修正 (v23 外审 Finding 2): bitset 解码字节序错了

本 gate 的 v1 版 (2026-06-01) 用 **MSB-first** 解 bitset, 但项目真源
`src/cuts/oracles/region_capacity_oracle._encode_region_bitset` 是 **LSB-first**:

```python
arr[idx // 8] |= 1 << (idx % 8)      # idx = x * 70 + y
```

v1 因此把 region cells 解到错误位置, term 数偏高约 **10x**。v23 外审独立按 LSB 重算 catch 了这个,
对真源码核实属实。同一条 region_capacity cert (139 set-bits) 的 per-type pose overlap:

| facility_type | v1 (MSB, 错) | v2 (LSB, 对) |
|---|---|---|
| boundary_storage_port | 68 | **134** |
| manufacturing_3x3 | 2026 | **264** |
| manufacturing_5x5 | 3222 | **256** |
| manufacturing_6x4 | 3228 | **260** |
| power_pole | 308 | **137** |
| protocol_core | 1320 | **0** |
| protocol_storage_box | 2026 | **264** |

**v1 的 "F1/F9 大池子 2000–3200 term/cut → 100K ~1.9 GB blow-up" 是 MSB bug 的假数字。**
LSB-correct 后, region 大池子展开是 ~264 term/cut → 100K ~100 MB, **不爆**。

## v2 → v3 修正 (v24 外审): bytes/term 按约束类型分 + F9 全 fixture

v24 外审 (两份独立, 主代理自核确认) 指出 v2 两处把量说小了:
1. **proto bytes/term 不能全局用 4–6** —— 实测 OR-Tools 9.15: `AddLinearConstraint` ~**3–4 B/term**, 但
   `AddBoolOr` no-good ~**10–11 B/term** (差 ~2.5–3x)。expanded no-good 的 100K 预算原被低估。
2. **F9 补测原只跑前 2 条 window** —— 全 6 条后 scoped(manufacturing) max = **784** (不是 360–524),
   all-type 上界 max = **3341**。

## 核心结论 (v3, LSB-correct + bytes/term-by-kind)

cut body 的 master 约束大小取决于 lowering 方式 **和约束类型**:

| lowering | term/cut (fixture max) | 100K proto (linear ~4 B / BoolOr ~11 B) | 判定 |
|---|---|---|---|
| compact (锁 witness), 全 9 族 | 1–4 | ~1–4 MB (任何类型) | 随便扛 |
| expanded scoped F1/F9 | 264–**784** | linear ~0.3 GB / **BoolOr ~0.86 GB** | linear 可控; BoolOr 偏大 |
| expanded all-type / routing UB | F4 5429 / F9 3341 | **BoolOr ~6 GB / ~3.7 GB** | 会爆, 必须 cap |

**关键转变 vs v1**: blow-up 不是 F1/F9 专属、也不是 fixture 尺度就发生; 它是 **(region/window × pool-density)
× (per-term 字节, 看约束类型)** 的函数, 跨**所有**族。fixture 尺度 region(139 cells)/window(10×10) 走
**linear** expanded 仍可控 (~0.3 GB@784 term), 但走 **BoolOr** expanded 同样 784 term 就 ~0.86 GB; routing/
all-type UB(数千 term)走 BoolOr 直接数 GB。**cap 必须按约束类型 + max/p99 设, 不是按 family-avg 粗估。**

## 逐族 term/cut (50-cert fixture, 真 registry, LSB-correct)

| family | n | compact | expanded scoped | expanded all-types (宽松上界) |
|---|---|---|---|---|
| region_capacity (F1) | 6 | 1 | 134 (boundary 小池) | 1315 |
| density_envelope (F9) | 6 | 4 (witness) | — (见 F9 window 补测) | — |
| component_reach (F4) | 6 | 1 | 5429* | 5429* |
| cutset (F2) | 6 | 1 | 173 | 173 |
| port_exposure (F3) | 6 | 2 | 500* | 500* |
| pattern_nogood (F5) | 6 | 1 | 1 | 1 |
| power_hitting_set (F7) | 4 | 1 | 16 (power_pole) | 846 |
| power_grid_reach (F8) | 6 | 1 | 16 (power_pole) | 677 |
| shape_packing_hall (F6) | 4 | 1 | 1 | 1 |

\* component_reach / cutset / port_exposure 的 expanded 数是**全类型并集的宽松上界** (它们没有单一
group→type 映射, 且本质是 routing/exposure no-good — 真实 lowering 是紧凑 1–2 term)。F4 的 5429
是 70 个 separator cell 跨全类型并集, 不是真实 lowering 形态。

## F9 density_envelope window→pose overlap (全 6 fixture, v3 修正)

v1 退回 compact witness (4); v2 补测 window 但只跑前 2 条 (v24 外审指出); v3 跑**全 6 条** window:

| window | mfg-max (scoped) | all-type UB | cells |
|---|---|---|---|
| [0,0,10,10] | 360 | 1720 | 100 |
| [1,3,10,10] | 524 | 2417 | 100 |
| [2,6,10,10] | 644 | 2841 | 100 |
| [3,9,10,10] | 700 | 3103 | 100 |
| [4,12,10,10] | 756 | 3251 | 100 |
| [5,15,10,10] | **784** | **3341** | 100 |

→ F9 fixture scoped(manufacturing) **avg ~628 / max 784** term/cut (不是 v2 写的 360–524); all-type UB max
**3341**。proto: scoped 784 走 linear ~0.3 GB / 走 BoolOr ~0.86 GB; all-type 3341 走 BoolOr ~3.7 GB。
大 window (趋近 70×70) 吃满整池 ~16–18K term。风险是 window-size × pool × 约束类型的函数。

## 对 verdict / P1.3A 的影响 (v3)

spike 的 sizing "doesn't blow up" 在以下精确口径下成立:

> fixture 尺度下, **所有 9 族**的 realistic compact (witness/no-good) lowering → 100K 都便宜 (~1–4 MB,
> 任何约束类型)。expanded (full pose-overlap) lowering 的 100K 预算 = **(per-cut term, 随 region/window ×
> pool-density 变) × (per-term 字节, 随约束类型变: linear ~4 B / BoolOr no-good ~11 B)**:
> - fixture F1/F9 scoped max **784** term/cut: 走 linear ~0.3 GB (可控), 走 **BoolOr ~0.86 GB** (偏大);
> - routing / all-type UB (F4 5429 / F9-alltype 3341 term/cut): 走 BoolOr **~3.7–6 GB** (会爆);
> - 大 region/window 趋近全 pool (~16–18K term/cut): 任何类型都数 GB。
> → P1.3A lowering 设计硬约束 = 对**任何**族的 geometric/expanded lowering, **按约束类型分别**设 per-cut
> term cap + cumulative proto budget (linear/BoolOr 预算不同), 且 cap 按 **max/p99** 不按 family-avg;
> 超 cap 就 compact fallback / reject / defer。其余维持 compact lowering 则全 9 族安全。

这比 v1 "只 F1/F9 大池子 = 1.9GB" 既更准也覆盖更全: 实质 blow-up 风险在 "expanded lowering × (大 region
或 BoolOr 形态 或 routing all-type)" 的组合下, 跨所有族; compact lowering 任何形态都安全。

## 复现 (v23 外审 Finding 1: 须包内可复现)

v1 脚本硬编码读外部 `cc_context/review/phase1_2_spike_review_v22.zip` 取 fixture (cc_context 不入包 → 包内
跑不了)。v2 改读**包内** `data/cuts/spike/oracle_emit_fixture_45cert.jsonl` + `data/preprocessed/
candidate_placements.json`。在解包后的 review 包 `project/` 根下:

```bash
python docs/research/p1_2_spike_sizing_gate_20260601/sizing_gate.py
```

## caveat

- LSB 解码已对真 oracle `_encode_region_bitset` 核实一致 (idx = x*70+y, bit = idx%8)。
- expanded 数是"若如此 lower"的几何上界; routing/no-good 族 (F2/F4/F3) 真实是紧凑 lowering, expanded 列
  只用于界定"若误用 expanded lowering 会多大"。
- 本 gate 只覆盖 master 约束 sizing。**cert 证书存储 + replay 校验** 在 100K 规模 (~613 B bitset/cert →
  ~60 MB store + 逐条 revalidate) 是另一条未测轴, 归 P1.3A proof lifecycle sizing。

## v3 → v5 修正 (v25 外审两份独立并集, 主代理逐条对真代码核实)

v25 送 GPT pro 第四轮 (两份独立都 substantive, 都 B/PATCH, **无 soundness 洞**)。并集 4 条 sizing finding 已修进本 gate (脚本升 v5):

1. **[A-F1, 最重] type-pool 数 ≠ 真 master concrete literal 数**。本 gate 之前按 facility **type** 数 pose pool overlap (type-pool total **81,795**)。但真 pose-bool master (`src/models/exact_coordinate_master.py`) 按 mandatory `(facility_type, operation_type)` **group × pose** 建变量, group 乘数 (from `data/preprocessed/mandatory_exact_instances.json`, 266 instances → 19 groups): mfg_3x3=**8** / mfg_5x5=**4** / mfg_6x4=**5** / protocol_core=1 / boundary_storage_port=1。→ concrete master var upper proxy = **325,747** (≈4× type-pool)。F4 5429 → **20,157** 是 group-expanded proxy。**F9 现有 cert 是 single-group** (`density_envelope` cert 带 `group_id`, validator 拒 witness group ≠ cert group): 当前 per-cut cert-group max 仍是 **784**；same-template proxy max **4,608**；all-manufacturing cross-group stress proxy **11,644**，不是当前 F9 per-cut concrete literal vector。满 mfg 池 → **295,700**。**所以 type-pool UB (F9 3341 / F4 5429 / ~16–18K) 是 cheap proxy, 不是真-master literal 上界。** 单 group 的 F9 **784** 仍是单 group lowering 的真实尺度。脚本现多打 `exp_group_all` 列 + group-expanded/stress 投影。
2. **[B-F1] family summary 表 F9 行不再 fallback 到 compact 4.0**。之前 `cut_cells()` 对 density_envelope 返回空 → summary 退回 witness 4, 与详细 F9 表 (784/3341) 自相矛盾。v5 给 `cut_cells` 加 density_envelope 分支 (用正确 `[x,y,h,w]` window_cells), summary 现承载真实 expanded overlap。
3. **[B-F2] OR-Tools bytes/term 现脚本内可复现实测** (不再只 hardcode)。脚本 OR-Tools 可 import 时实测 81,795 var 高 index tail: **linear 4.03 / BoolOr no-good 10.01 B/term** (与 hardcode 的 4/11 保守一致)。⚠️ 实现用 `model.ExportToFile(.pb)` 量字节 —— 9.15.6755 的 `CpModelProto` pybind **没有** `ByteSize`/`SerializeToString` (一份审查的补丁误用 `.ByteSize()` 会崩, 本 gate 避开); 无 OR-Tools 时 fail-soft 跳过。
4. **[A-F2] F9 `window_rect` 是 `[x,y,h,w]` 不是 `[x,y,w,h]`**。现 fixture 全 10×10 方形故数字不变, 但脚本读序已修正 (非方形 window 会错)。

**对 P1.3A 的硬约束 (v5 收紧)**: per-cut term cap + cumulative proto budget 的 **cap 输入必须是真 translator 在 group/template/optional 展开后发出的 concrete literal vector 长度** (不是 type-pool 数), 按约束类型分字节 (linear ~4 / BoolOr ~11), cap 按 max/p99 跨所有族。**别把 3341/5429/16–18K 当真-master 上界写进设计** —— 它们是 type-pool proxy。详 [[p1-3a-design-phase]] sizing 基线。


## v5 → v6 复审澄清 (post-v26)

- `density_envelope`/F9 证书当前带 `group_id`，family validator 拒绝 witness group 与 cert group 不一致 (源码 `src/cuts/families/density_envelope.py` 已核)；因此现有 F9 lowering 是 **single-group**。
- sizing_gate 输出中的 F9 **11,644** 应标为 all-manufacturing cross-group **stress proxy**，不是当前 F9 per-cut concrete literal vector。当前 F9 cert-group max 仍是 **784**；same-template proxy max **4,608**。
- P1.3A 的硬约束不变: 真 translator 发出后按 `len(final_concrete_literals)` 设 max/p99 cap + cumulative proto budget，按 linear/BoolOr 分预算；任何 cross-group/template lift 必须先经过这个 concrete-vector cap。
