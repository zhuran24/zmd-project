# DOC-ADR-014：事件驱动的文档 intake 与同一知识事务

状态：Accepted
日期：2026-08-13

## 背景

周期审计可以发现遗漏，却不能阻止“报告先写、登记以后再补”的灰区。仅靠提交末尾的静态检查也会让 agent 在错误路径上走得太远。文档系统需要在 Git diff 中识别具体事件，并把分类、知识身份、dossier 生命周期和 owner authority companion 作为同一事务验收。

同时，事件协议不能复制项目知识。它只声明哪些变化需要哪些结构化伴随动作；claim、decision、dossier 和原始证据仍由各自既有真源负责。

## 决定

1. `.docsystem/manifest.json` 只保存 intake 真源与 schema 的稳定坐标。
2. `data/repository_governance/document_system/intake.json` 保存事件类型、稳定身份字段、owner companion 规则、dossier 关闭结果和临时文档退出字段。
3. `docctl intake --changed` 从 Git-visible diff 推导紧凑事件卡；`docctl check --changed` 复用同一解析结果，不另写一套规则。
4. 新 Markdown 必须在同一变更中获得有效 policy；承担 current 职责的文档还必须进入显式 section。
5. 新 dossier 必须在同一变更中登记。新 tracked research dossier 以 `active` workflow 开始；关闭时必须有 current semantic review 与 typed outcome。
6. 既有 claim 或 decision ID 的语义身份不能原地改写或删除。证据、状态和非语义 profile 可以在 schema 允许的范围内更新；命题含义改变时创建新 ID，并通过 `supersedes` 留下方向。
7. `owner_only` 且属于受控 authority role 的路径只有在同一变更新增 current owner decision、并精确引用该路径时才可通过 diff 门。
8. 临时文档必须在 intake 真源中记录创建日、到期日、退出动作和理由。
9. 新 `local_optional` dossier 必须记录 manifest、SHA-256 与恢复说明；历史记录不因本 ADR 被追溯性伪造。

## 为什么不再增加第二套 dossier 真源

现有 `data/knowledge/dossiers.json` 已是全仓查询与生成投影的真源。为每个目录再建立可独立修改的 `DOSSIER.json` 会带来双写和一致性问题。本阶段让 `docctl new/close-dossier` 原子修改中央账本，并让目录 policy 继续提供局部操作语义。未来若引入局部 manifest，它只能成为由中央真源生成的只读投影，或经过单独迁移后成为唯一写入源。

## 后果

普通 agent 默认只看到当前 diff 触发的事件、失败原因和后续动作，不需要加载完整维护指南。框架维护者仍可通过 manifest、架构页、本指南和此 ADR 下钻到完整原因。周期审计继续存在，但职责变为发现语义遗漏和长期漂移，而不是替日常事件补账。
