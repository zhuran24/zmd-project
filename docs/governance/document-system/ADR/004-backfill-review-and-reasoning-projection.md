# DOC-ADR-004：知识回填审阅账本与推理分类投影

状态：Accepted
日期：2026-08-11

## 背景

第一阶段给 claim、decision 与 dossier 建立了稳定身份，但“某个 dossier 是否已经做过语义提炼”仍没有机器可查询的记录。目录登记只能证明材料存在，不能证明其中的结论已经被审阅。与此同时，用户关心的“领域策略能分离哪些候选，以及通用 CP-SAT 传播是否做不到”也不能只靠全文搜索或把所有有效不等式混成一类回答。

如果直接在 dossier 记录上增加一个布尔值，会丢掉审阅范围、当时提炼出的 claim、未决问题和后续 supersede 链。如果另写一份手工专题总结，它又会成为新的易漂移副本。

## 决定

1. 新增 append-style 的 `data/knowledge/backfill_reviews.jsonl`。每条 review 绑定一个 dossier，记录审阅范围、实际读过的路径、结果、提炼 claim、未决项和 supersedes。每个 dossier 最多有一条 `status=current` 的 review。
2. dossier inventory 与 backfill review 明确分工。inventory 只回答“材料是否存在且在哪里”，review 回答“是否已经做过语义审阅，以及审到了什么”。review 本身不授予数学或 owner authority。
3. claim 可选携带 `reasoning_profile`，只保存可查询的推理坐标，包括条件处置、操作效果、一般性、solver 关系、发现方式，以及“通用传播不能替代”的证据等级。原始 statement、premises、authority 与 evidence 仍是结论真源。
4. 新增由 generator 生成的 `docs/REASONING_LEDGER.md`。它投影分类分布、已审 dossier、未决项，并把“领域化排除有效”与“已证明指定通用传播系统无法得到同样分离”分开计数。
5. `generic_propagation_evidence=formal` 采用高门槛：必须明确传播系统和输入族，并有不可分离证明。运行慢、零激活、UNKNOWN、一次超时或实验中未观察到传播都不能升级为 formal。
6. `docctl` 在目标路径属于 dossier 时，连同 claim/decision 摘要一起显示当前 backfill review。agent 因而能看到“这包是否审过、审到什么、还有什么没做”，而无需加载全仓回填手册。

## 后果

- 历史回填可以分批进行，并能准确区分“未审”“已审无可复用结论”“已提炼”“不确定”和“延后”。
- 领域不等式、语义约束、反例与实验边界可以按统一维度查询，但分类不会改变原 claim 的 authority。
- 生成页增加一个真源和一个投影，框架 schema、manifest、policy、doctor 与测试必须一起维护。
- 旧 dossier 不需要为回填而改写正文，符合历史证据冻结原则。

## 未采用的方案

- **在 `dossiers.json` 上直接增加 `reviewed=true`**：无法表达局部审阅、重审、未决项和 supersede。
- **每个 dossier 内放一份手工 review Markdown**：对局部阅读友好，但难以做全局一致性检查和覆盖统计，且会形成重复入口。
- **从文档正文自动推断所有 claim 与 evidence 等级**：自动抽取可生成候选，但无法可靠判断数学有效性、作用域或 authority，不能静默晋升。
- **把所有 solver 未发现结果都标成 generic-propagation impossibility**：混淆搜索、建模、预算和传播闭包，证据等级不可接受。
