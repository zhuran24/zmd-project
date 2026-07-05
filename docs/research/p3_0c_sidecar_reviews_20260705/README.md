# P3.0c binding PB sidecar 设计稿 v1 外审归档（2026-07-05）

轴 B 证书侧 Phase 0+1 设计稿 v1 的双会话独立对抗审原件。两份**均判 REJECT**
（方向保留：PB/OPB 独立重建 + RoundingSat + VeriPB sidecar 路线双方都攻击失败；
但 v1 的 scope gate、输入契约、语义完整性、验收强度不能作实现基线）。

| 文件 | 内容 |
|---|---|
| `sidecar_design_audit_session1.md` | 会话1：6 BLOCK + 8 CONCERN + 2 NIT，总判定 REJECT |
| `sidecar_design_audit_session2.md` | 会话2：7 BLOCK + 8 CONCERN + 2 NIT，总判定 REJECT |

两份高度收敛的核心指控（全部吸收进 v2，逐项对照表见设计稿 §9）：
1. dump 是「生产加工后的世界」，当权威输入破坏独立重建 → canonical sample record；
2. scope 非机器闭合，「首解 INFEASIBLE」外观下至少四种形态 → 五分类
   `binding_scope_class` 字段化 gate；
3. 输入校验/边界语义漏项（generic I/O 角色与完备性校验、metadata 校验、
   pose_optional `::` 反推、INVALID_INPUT vs raise vs UNSAT 三分）；
4. 「域空」在 Phase 1 纯模型下是死分支（枚举器要么 raise 要么非空）——
   真实 UNSAT 只来自 generic 精确计数（会话2 独有的关键反推）；
5. 验收缺 over-constraint 方向：过约束 emitter 在一切 INFEASIBLE 样本上
   都会漂亮 CONFIRMED → known-FEASIBLE canaries + 双向红测矩阵；
6. I1「相同对象」过度声称（binding_kwargs 透传，无 routing_context 代码层断言）；
7. 硬编码常量（pose_optional 映射、provider/receiver 集合）是 sidecar 与
   生产共享的 TCB，必须显式声明「Phase 1 防不了」。

修订后的设计稿：`../p3_0c_binding_pb_sidecar_design_v1.md`（文件名 v1 =
首落库，内容为 v2，同 Q1 分类学稿的命名惯例）。

处置纪律：修复文本未盲 apply——关键断言（域空死分支、required=0 不发 sum 行、
pose_optional 反推、I1 kwargs 透传）逐条对照源码复核后融合重写。
