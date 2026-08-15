# DOC-ADR-005：数学推导图与稳定推导族

状态：Accepted
日期：2026-08-11

## 背景

`reasoning_profile` 能回答一条结论怎样改变候选、模型或 solver 工作流，却不能区分“原子引理”“复合定理”和“研究账本投影”，也不能稳定查询一条上界由哪些数学构件直接组成。只靠 dossier 全文或 tags，会把推导关系重新交给读者考古；把完整证明复制进 claim ledger，又会制造第二份正文和新的漂移源。

第二阶段回填开始出现多层组合链：面积分账、流量容量、route footprint、电杆覆盖、ordinary / marked membrane、endpoint budget、局部 access capacity、lex-band 枚举与 finite-PB certificate 彼此组合。它们需要可查询的直接边，同时必须保留原报告作为证明正文和证据真源。

## 决定

1. claim 增加可选 `derivation_profile`。它只保存：
   - `role`：`definition`、`atomic_lemma`、`composite_theorem`、`ledger_projection`、`method`、`counterexample` 或 `open_obligation`；
   - `families`：稳定数学推导族；
   - `verification_modes`：纸面推导、源重算、精确枚举、优化证书、独立重算、对抗复核、authority admission、反例、Roundingsat/VeriPB 或机器投影。
2. claim 顶层 `dependencies` 是数学推导图的直接前件边；`supersedes` 是语义换代边。账本不保存自动推断的传递闭包。
3. `reasoning_profile` 与 `derivation_profile` 正交：前者回答操作效果和 solver 关系，后者回答证明角色、数学族和验证路径。任一 profile 都不改变 statement、premises、status、authority 或 authority effect。
4. `REASONING_LEDGER.md` 自动投影推导角色、数学族、验证方式和直接依赖关系；`CATALOG.md` 仍展开完整 claim 摘要；原始证明正文留在 evidence dossier。
5. 对同一命题只增加新证据或验证方式时，可以保留 claim ID；命题、scope、premises 或 authority effect 实质变化时，仍创建新 ID 并显式 supersede。

## 后果

- 上下界和组合排除可以按原子引理、复合定理和 ledger projection 查询，而不必重读全部历史包。
- agent 能区分“数学前件”“操作分类”和“authority 结论”，减少把账本数字误当成无前提定理的风险。
- schema、generator、架构说明、维护协议、policy 引用和回归测试必须一起演化。
- 推导图质量仍依赖语义审阅。自动化只能校验 ID、schema 与无环性，不能独立判定某条依赖在数学上是否充分。

## 未采用的方案

- **只增加 tags**：可以聚类主题，不能表达直接推导边或节点角色。
- **从报告正文自动推断证明图**：可生成候选，但无法可靠区分前提、引用、反例和 authority admission，不能静默落账。
- **把完整证明写入 claim ledger**：会复制证据正文，使 ledger 变成第二套研究档案。
- **只在专题 Markdown 中手画依赖图**：难以做全局无环检查、稳定链接和自动投影，且会再次漂移。
