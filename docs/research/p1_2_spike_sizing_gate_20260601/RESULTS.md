# P1.2 spike — 真 cut body sizing cheap gate 结果 (2026-06-01)

## 背景

P1.2 spike close gate (v22) 的 verdict 把 Finding 5 #2 "true cut body distribution
sizing" 标成 YES。第九审 (GPT pro, faithful + clean 两版独立跑) 双双判 **B**: spike
的 toy_translator 实际没忠实 lower 真 cut body —— 38/50 cert 走 synthetic 3-literal
fallback, 唯二真提取的两族 (port_exposure / density_envelope) 提取出的 pose 又全部
不在真 registry 里 (36 个 unknown), 被静默 hash-remap。所以 spike 的 100K proto/RSS
数字是 "合成/remap 吞吐量", 不是 "真 cut body sizing"。

本 gate 不重跑 spike, 直接对**真 fixture + 真 registry** 算出真 cut body 在不同
lowering 下的 master 约束大小, 给 P1.3A lowering 设计一个带数字的硬约束。

复现: `python docs/research/p1_2_spike_sizing_gate_20260601/sizing_gate.py`

## 核心结论

**真 cut body 的 master 约束大小不是一个固定可测的事实, 而是个 ~1000x 的设计变量,
完全取决于怎么 lower, 且整个 blow-up 风险只集中在 F1 / F9 两族。**

| lowering 方式 | term/cut | 100K proto | 判定 |
|---|---|---|---|
| 紧凑 no-good (只锁 witness pose) | 1–4 | ~1–3 MB | 随便扛 |
| 合成 3-literal (spike 实测) | 3 | 19.55 MB (实测) | spike 的数字 |
| 展开, 小池子 (boundary / power) | 16–68 | ~10–40 MB | 没问题 |
| **展开, 大池子容量 cut (mfg / storage)** | **2000–3200** | **~1.2–1.9 GB** | **爆** |

spike 的 19.55 MB 落在便宜端: 它是 "紧凑 no-good / 小池子" 的合理代理, 但若真用了
大池子展开容量 cut, 它低估 50–100x。

## 逐族 term 数 (50-cert fixture, 真 registry 限定类型)

| family | n | compact (no-good) | expanded (scoped) | 自然形态 |
|---|---|---|---|---|
| region_capacity (F1) | 6 | 1 | 68 (boundary 小池) | **容量和, 大池子会涨** |
| density_envelope (F9) | 6 | 4 (witness) | 4 | **面积和, 大池子会涨** |
| component_reach (F4) | 6 | 1 | 5429* | 路由连通 no-good (实际紧凑) |
| cutset (F2) | 6 | 1 | 761* | 路由割 no-good (实际紧凑) |
| port_exposure (F3) | 6 | 2 | 500* | 2-literal no-good (实际紧凑) |
| pattern_nogood (F5) | 6 | 1 | 1 | 紧凑 no-good |
| power_hitting_set (F7) | 4 | 1 | 16 | 小池 (power_pole 4761) |
| power_grid_reach (F8) | 6 | 1 | 16 | 小池 |
| shape_packing_hall (F6) | 4 | 1 | 1 | 紧凑 |

\* component_reach / cutset / port_exposure 的 expanded 数是**全类型并集的宽松上界**
(它们没有单一 group→type 映射)。这三族本质是 no-good (锁导致 routing/exposure 冲突
的具体 witness assignment), 真实 lowering 是紧凑的 1–2 term, expanded 列只是最坏假设。

## 风险集中在哪

- **7 个族 (F2/F3/F4/F5/F6/F7/F8)**: 本质都是 no-good / 小池子, 任何 lowering 下都是
  几项到几十项, 100K 随便扛。不是风险。
- **2 个族 (F1 region_capacity / F9 density_envelope)**: 容量/面积约束, 自然形态是
  "区域内 pose 之和 ≤ 上界"。fixture 里它们打的是小池子 (boundary 68 / witness 4),
  但如果打**大制造池子** (manufacturing 各 ~17952 pose) 且区域不小, 每条 ~2000–3200
  term (实测: 同一 139 格区域落 manufacturing 覆盖 2026–3228 pose; 整张 70×70 吃满整池
  ~18000)。**100K 条这种 → ~1.9 GB proto → 爆。**

## 对 verdict / P1.3A 的影响

spike 的 "doesn't blow up" 只在以下条件成立时有效, 必须写进 verdict 当显式 scope:

> 100K cut 的 master sizing 是有界且便宜的 (~1–40 MB), **唯一**的 blow-up 路径是把
> **F1/F9 的大池子容量/面积 cut 按展开式 lower** (每条 ~2–3K term → 100K ~1.9 GB)。
> 因此 P1.3A lowering 设计**必须**对 F1/F9 二选一:
>   (a) 按 witness 紧凑 no-good 来 lower, 或
>   (b) 给"大池子展开容量 cut"的条数/规模设上界。
> 其余 7 族任意 lower 都安全。

这是 P1.3A lowering 设计的**带数字的硬约束**, 不是含糊的 "有风险"。F1/F9 到底走紧凑
还是带上界的展开, 是 P1.3A N=8 设计要定的事, 但带着这两个数字 (2–3K term/cut,
1.9 GB@100K) 进去, 不是空手。

## caveat

- bitset 解码假设 70×70 row-major MSB-first; 朝向只影响"摸到哪些 pose", 不影响数量级。
- expanded 大池子数是"若如此 lower"的上界, 不是断言项目一定会这么 lower。本 gate 的
  价值是把 sizing 从"测过了没问题"精确成"除 F1/F9 大池子展开外都没问题"。
- 本 gate 只覆盖 master 约束 sizing。**cert 证书存储 + replay 校验** 在 100K 规模的成本
  (每 cert 带 ~613 字节 bitset → ~60 MB store + 逐条 revalidate) 是另一条未测的轴,
  spike 也没量, 应在 P1.3A proof lifecycle 一并 size。
