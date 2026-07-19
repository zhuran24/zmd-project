# R1 严格版判读（2026-07-20，按 strict/internal/comparison_rubric.md）

> 判读对象：`04` 号逐字存档（GPT Pro 对 strict 三件套的回复，联网放开版）。
> 判读者：主会话；两项量化断言已亲手异构复算（`verify_r1_strict_bounds.py`）。

## 0. 一句话结论

**12/12 满分卷 + 两项可立即收编的 certified 前置引理**。它把 `problem_instance.json` 当权威、哨兵全部复算对（266/219/3,544/628/17 组/19 商品，310+264 制造账与我方 `05_rounds_tier2` 独立账逐字一致）；十条显式假设**全部**与我方已定谳语义吻合（含悬空臂合法、无流量守恒、箱出口空置、ghost 只斥本体、共享接驳格）——严格规格书的完备性由此得到一次干净房间级确认。

## 1. Rubric 打分

| 维度 | 分 | 依据 |
|---|---|---|
| Rule ownership | 2 | 每条硬规则有三栏归属表（search owner / 终局证明模型 / witness checker） |
| Rejection information | 2 | proof-carrying core（显式允许混合极性字面——"正字面-only 障碍解释不自动 sound"正是我方 I1 纪律的独立重推）+ 保底 exact nogood |
| Escalation criterion | 2 | Hall cut / commodity separator / degree conflict / 通用 core 的显式升级链；不可检查的拒绝只能当启发式罚分 |
| Optimality evidence | 2 | witness + 独立重生成模型的分片 UNSAT 证明 + manifest；"timeout/gap 什么都不证明"显式声明 |
| Memory engineering | 2 | 变量量级逐段落到 42G search / 34G proof shard 的本机 48G 计划；300G proof scratch 直接点到磁盘约束 |
| Failure analysis | 2 | 三类失败模式全部 benchmark 特化（语义漂移防误强化负向测试清单/几何-路由 thrash/证明工件爆内存），缓解不削 soundness |

## 2. 已复算收编的两项 certified 前置引理

1. **47 边界模式塌缩**（解析验证）：每边恰 23 台强制（46=23+23，⌊70/3⌋ 上限）、gap∈{0,3,…,69}、角格 (0,0) 互斥 ⇒ 24+24−1=47。**用途**：master/bespoke 线的对称塌缩与分片轴；边界 ID 可按边+anchor 字典序确定性指派。
2. **certified 起始上界 (1326, 34)**（`verify_r1_strict_bounds.py` 精确枚举复现，接驳格几何实取 f05b1291 池）：链条=P≥2（⌈219/144⌉）→ 自由格 ≤1,348 → 52 slot=52 需求 ⇒ 46 边界接驳格强制非本体 → 列0/行0 排除 → 47 模式 × 1,182 尺寸对的 |R∩Q| 枚举。**这是本项目第一个 certified 全局面积上界**（对照：round45 六臂全 UNKNOWN、历史所有上界证书尝试 structural 死）。副产品 cut：目标面积 A 下 `4P+9B ≤ 1356−A`。

诚实边界：1,326 只是上界不是可行声明；真最优的量级仍未知（现有 witness 侧 ghost 仅 42 级别，缺口巨大）。

## 3. 分类清单（rubric §Classification）

**Independent convergence**（与我方现行方法论同判据）：双轨"分解找解+独立整体认证"=三权分立哲学；proof-carrying rejection ledger=typed cut framework+I1 复验；≤2 箱+删冗余杆正规形=round45 `9219498` 正规形**逐字同款**（独立推出）；连通性量词/共享接驳格/ghost 语义全同。

**Equivalent reformulation**：operation-group 商模型聚合（footprint 级 z 变量 + 路由期再指派 ID）vs 我方实例级池+对称破除——同保证不同层切；方形机朝向推迟到 router（core 62²=3,844 锚点而非 2×62² 模式）是更紧的 master 表示。

**New candidate**（值得单独评估收编）：
- ①47 模式分片轴（终局证明 embarrassingly parallel 的天然切法）；
- ②(1326,34) 起始上界 + 降维 BetterRectangle 预枚举析取（避免信任 solver 内乘法）；
- ③component-typed 传输模型（48 变体+crossing 双 channel 节点）进终局证明模型——比我方 connectivity-only routing gate 更细，对 P3 witness 可实现性直接相关；
- ④parent-forest+rank 双向可达性编码（终局模型的具体编码选项）;
- ⑤流式 proof 检查+OptimalityManifest 结构（与 PB provenance 线同向，坐标更完整）。

**Specification miss / Unsound shortcut**：零发现。十条假设逐条对谳无一违背；全文无一处把 solver 状态当证据。

**Specification ambiguity**：其假设 #1（port_needs 按实例还是按组聚合）与 #5（悬空臂）确实是规格书未显式钉死、靠哨兵数才能倒推的点——建议随下一次 strict 包修订把这两条写成显式条款（非阻塞）。

## 4. 与上一轮（自然语言版 R1，`02` 号）的增量

上轮给的是架构同构性确认；这轮在严格数据上**产出了可复算的新数学**（47/1326/P≥2）+ 逐条可执行的编码蓝图（111K 变量 master 账、路由器 49 态/格、~2,696 channel 节点、42G/34G 内存计划）。干净房间实验的两轮投入从"信心校准"升级为"直接产出可收编引理"。

## 5. 建议动作（按优先级）

1. ✅（本轮已做）47+（1326,34) 复算落库；
2. 47 模式塌缩接入 bespoke/witness 线（round45 master 加边界模式枚举变量；witness 构造器直接按 47 模式布边界）——归 rounds 后续批；
3. component-typed 终局模型与 PB 证明链（RoundingSat/VeriPB 方向）的对接评估——归 P3.0 轴 B（上轮 R1 已建议 VeriPB 升格，本轮给了完整 manifest 蓝图）;
4. strict 包修订候补两条显式条款（§3 ambiguity）——等 owner 决定是否发 R2 时一并。
