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

## 核心结论 (v2, LSB-correct)

cut body 的 master 约束大小取决于 lowering 方式:

| lowering | term/cut (fixture 尺度) | 100K proto (~4–6 B/term) | 判定 |
|---|---|---|---|
| compact no-good (锁 witness pose), 全 9 族 | 1–4 | ~1–3 MB | 随便扛 |
| expanded, fixture 尺度 region/window | ~百级 (见下表) | ~0.1–0.3 GB | 可控, 非 blow-up |
| expanded, 大 region/window 或全 pool | thousands–16K | 数 GB | 会爆 (需大 region) |

**关键转变 vs v1**: blow-up **不是** F1/F9 大池子在 fixture 尺度就发生; 它是 **region-size × pool-density**
的函数, 跨**所有**族, 只在 region/window 很大 + 走 expanded lowering 时才到 GB 级。fixture 尺度
(region 139 cells / window 10×10) 即使 expanded 也才百级 term。

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

## F9 density_envelope window→pose overlap (v23 外审 Finding 4 补测)

v1 对 F9 退回了 compact witness 计数 (4), 没真测 window 展开。v2 补测 (window_rect → cells → overlap):

| window | cells | manufacturing 各池 | protocol_core | power_pole |
|---|---|---|---|---|
| 10×10 @ (0,0) | 100 | 360 | 162 | 100 |
| 10×10 @ (1,3) | 100 | 504–524 | 240 | 121 |

→ F9 fixture 尺度 window (10×10) expanded ~360–524 term/cut → 100K ~150–300 MB。大 window (70×70)
会吃满整池 ~16–18K term → 数 GB。同 region_capacity: 风险是 window-size 的函数。

## 对 verdict / P1.3A 的影响 (v2)

spike 的 sizing "doesn't blow up" 在以下精确口径下成立:

> fixture 尺度下, **所有 9 族**的 realistic compact (witness/no-good) lowering → 100K 都便宜 (~1–3 MB)。
> expanded (full pose-overlap) lowering 随 **region-size × pool-density** 变化: fixture 尺度的
> region (139 cells) / window (10×10) 给 ~百级 term/cut → 100K ~0.1–0.3 GB, 仍可控; 只有**大** region/
> window (趋近全 pool) 才到 thousands–16K term/cut → 数 GB blow-up。
> → P1.3A lowering 设计硬约束 = 对**任何**族的 geometric / large-overlap expanded lowering 设
> **per-cut term cap + cumulative proto budget** (不是只 F1/F9; F2/F4 expanded 同样可大)。其余维持
> compact lowering 则全族安全。

这比 v1 "只 F1/F9 大池子 = 1.9GB" 既更准也更温和: 实质 blow-up 风险只在"大 region + expanded lowering"
的组合下, 而非 fixture 已展示的任何情形。

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
