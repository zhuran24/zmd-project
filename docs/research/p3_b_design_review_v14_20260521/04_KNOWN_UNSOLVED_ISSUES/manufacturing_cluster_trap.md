# Known unsolved issue: 132 个 manufacturing_3x3 cluster trap

## 数据

`manufacturing_3x3` 共 **132 个** facility instance, 是 266 mandatory 内
**最大单一 facility 类型** (49.6%, 接近一半).

每个 footprint = 3 × 3 = 9 cells. 132 × 9 = **1188 cells = 24.2% grid**.

跨 operation_type 分:
- 132 个分 ~10-15 个 operation_type (e.g. crusher_blue_iron,
  refinery_X, assembler_Y 等)
- 每 operation_type ~ 8-15 个 instance

## 为什么是潜在 trap

### Trap 1: 同 operation_type cluster symmetry

132 个 facility, 多达 ~10 个 operation_type, 每 type cluster ~8-15 个
**完全可互换 instance** (相同 footprint, 相同 IO spec, 相同 power coverage).

symmetric orbit 的 permutation 数 = O(8! × 10! × ...) 爆炸. master 自己
不识别 symmetry, search space 增大 ~10^15 倍 (每 orbit 阶乘).

→ 这是 stress 来源之一. cand C v3 m14 RF/std ratio 4.38 (40 inst) 跟此
symmetry 相关 — Ryan-Foster pair selection 在 symmetric instances 之间
振荡.

### Trap 2: manufacturing 3x3 间的 routing dependencies

manufacturing facility 间有 IO 关系: e.g. crusher 出料 → refinery 入料.
crusher 跟 refinery 距离 ≤ belt 路径长度上限. 132 facility 形成 routing
DAG.

DAG topology 决定 placement geometry — 哪两个 facility "应该" 相邻. 但
source-of-truth 没指定具体 layout, optimizer 自由.

→ 132 facility DAG 在 70×70 grid 上的 embedding 是 trap. NP-hard 已知
(graph embedding minimum total edge length).

### Trap 3: manufacturing 3x3 间 power_pole 共享

每 manufacturing facility 需要 ≥ 1 power_pole 在 coverage radius 内.
power_pole 自己占 cell + 有 radius (e.g. 5 cell). 132 facility 共享 ~50
power_pole.

每 power_pole 覆盖几个 facility (radius 内), facility 跟 power_pole 距
离约束跟 placement 强耦合.

→ master_model.py 内 `power_coverage` 约束族 (`x_{g,p} → ∃ y_{coverer_pole}`)
是 source of 大量 cstr. 跟 Augmented master Candidate D (lever 23) 2.36M
cstr 强相关.

### Trap 4: 3x3 footprint × 96% utilization 的 packing

3x3 packing 在 70×70 grid 上是 经典 strip packing 问题. 132 个 3x3 +
49 个 5x5 + 38 个 6x4 + 46 个 1x3 boundary 是 mixed-size strip packing
(NP-hard).

96% utilization 下 packing margin ≈ 0 (前面 `geometric_deadlock_data.md`
推算 stranded margin = 132 cells, 即 4 个 manufacturing_3x3 容差).

→ 任意 manufacturing 没放对都让全局 layout infeasible. 这是 cand C v3
0 iter infeasible 跟 96% utilization 的根因之一.

## 实测撞这个 trap 的 verdict

- **Cand C v3 m14 RF/std nodes ratio 2.44/4.38**: Ryan-Foster 在 20/40
  inst ramp 上比 std branching 多 2-4 倍 nodes. RF 在 symmetric orbit
  之间 pair 选择无 distinguisher, 浪费 branching.
- **B1 Phase 4 routing 系统性 front_blocked**: 132 个 manufacturing 跨
  4 side IO direction, port 跟 routing graph 冲突时 ~500 port front
  blocked.
- **Path 16 GOC-C2 vars 爆**: 1.5M vars 部分来源是 manufacturing cluster
  × owner-optional × commodity 维度. 132 × 10 commodity × 8 ports =
  10K 维, RSS 25 GB.

## 跟 B 设计的关系

B 的 **symmetry-lifted cut family** 直接解决 132 manufacturing 同质 trap:
- detect orbit (132 个 instance 按 operation_type 分 ~10 个 orbit)
- 单个 cut C 在 orbit 内 representative 上 sound → lift 到整 orbit
- search space 减 O(orbit_size!) 倍 — 132 / 10 = 13.2 orbit × 8-15
  instance/orbit → 总 lift factor O((10!)^10) = 巨大

但 lift 算法的 sound 性需要 verify:
- 必须确保 orbit 内 instance 真完全可互换 (无 cross-instance dependency
  不同)
- routing DAG 内若 instance i_1 是 crusher_blue, instance i_2 是
  crusher_red, 即使 footprint 同, IO commodity 不同 → 不可互换

→ orbit detection 必须 commodity-aware, 不只 facility_type. PoC 阶段
verify.

## 还没解的部分

1. **orbit detection 算法**: 需要 commodity DAG + IO spec 全比对, 不是
   facility_type 直接同
2. **symmetric breaking 的 sound 性**: lift cut 必须证明 σ(cut) sound
   for all σ in orbit
3. **manufacturing × power_pole channel**: power_pole vars 跟 facility
   vars 的 product 是 master scale 爆点. B 设计如何隔离这个?
4. **routing DAG embedding**: 132 facility DAG 的 grid embedding 仍是
   NP-hard, B 设计的 cutset / component_reach cut 在此 problem 上能否
   有效切

## Stress test 视角

构造恶魔构型 candidate 之二: 选 ~30-50 个 manufacturing_3x3 instance,
分 ~5 个 operation_type, 每 type ~8-10 instance. 故意让 commodity DAG
跨 type 形成"必须 chain 不能并行" topology.

让 ghost rectangle 占据 layout 中央, 强制 commodity chain 必须绕 ghost.

观察 B 5 cut family 能否识别:
- region capacity: 局部 region 内 facility 数 cap ≤ 实际 → trigger
- cutset: ghost 切 commodity 路径 → trigger
- port_exposure: 局部 port 跟 ghost edge 冲突 → trigger
- component_reach: ghost 切断 src→sink → trigger
- pattern_nogood: oracle 给 instance-pose cert
- symmetry-lift: orbit detection 处理 ~30 个 manufacturing 的 symmetry

如果各 cut family 单独都不识别, 找出**组合** infeasibility — 即每个 cut
family 单独 sound 但合起来仍找不到. 这是 B 设计 5 cut family 完备性的
真正 test.
