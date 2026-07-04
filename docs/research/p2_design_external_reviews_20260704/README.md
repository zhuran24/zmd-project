# 2026-07-04 设计稿预实现外审归档（GPT Pro 五会话）

**性质**：HISTORICAL_OR_PLAN 审计档案。这些是对三份「先想后做」设计稿 v1 的外部审查/对照产物，
是 v2 修订的输入证据。**不是**命令、不是当前状态权威；补丁一律未盲 apply（v2 由本方 triage 后重写）。

| 文件 | 会话 | 内容 |
|---|---|---|
| `p2_0_blind_design_gpt.md` | 吞吐·盲设计 | 独立设计的吞吐范式（TP7-S/TP7-D 两层结构——v2 采纳为主结构） |
| `p2_0_adversarial_review_gpt.md` | 吞吐·对抗审 | 5 BLOCK + 3 CONCERN + 2 NOTE（BLOCK-1 源口漏 protocol_core 等,全部核实为真） |
| `p2_0_sandbox_counterexamples_gpt.patch` | 吞吐·沙箱反例 | tick 仿真器 + fluid checker + CE1-CE4 反例目录（CE4 = 公理未覆盖的多输入队首阻塞） |
| `f5_adversarial_review_gpt.md` / `.patch` / `.py` | F5·对抗审 | 2 BLOCK（liftable-reject 量词、multiplicity 坍缩）+ P-HOM 全量机器验证（266 条 0 违例）+ 计数修正 |
| `tns_adversarial_review_gpt.md` / `.patch` / `.py` | TNS·对抗审 | 4 BLOCK（authoritative 域绑定、负向复验硬门、resume 生命周期、sink projection）+ 5 CONCERN |

对应设计稿：`../p2_0_throughput_certification_paradigm_design_v1.md`（→v2）、
`../p1_3_f5_orbit_lift_soundness_design_v1.md`（→v2）、
`../terminal_no_solution_evidence_contract_design_v1.md`（→v2）。
