# DOC-ADR-017：可执行知识 authority、表示坐标与非授权 decision 登记册

状态：Accepted
日期：2026-08-14

## 背景

知识账本早期把“记录当前可查询”“证据看起来很强”“机器能够核验”和“owner 已经裁决”压进了相邻字段。独立落地复核发现三类危险：部分只有历史研究报告的 claim 被标为 `machine`；`decisions.jsonl` 没有明确声明自己不授予 authority；`.artifacts/**` 中的 workspace-only evidence 与 Git-tracked 真源没有结构化区分。

这些问题不会立刻改变数学命题，却会改变 agent 对命题可信等级、耐久性和下游可复用性的判断。高估 authority 比缺少标签更危险，因此需要 fail-closed 的可执行准入规则。

## 决定

1. claim 必须分别声明 `representation_class` 与 `authority`。前者描述记录在表示系统中的位置，后者描述认识论等级；两者正交。当前 `claims.jsonl` 的记录均为 `AUTHORITATIVE_CURRENT`，并由 `current_state.json` 给出到 DOC_POLICY `document_class` 的规范映射。
2. 每条 claim 必须携带 `authority_basis`。`machine` 只允许使用 `machine_verified` basis，列出当前 Git-tracked 机器真源和具名 `verification_id`；knowledge checker 必须实际执行该 verifier。历史执行收据即使完整，也最多是 `research_authority`。
3. evidence 必须声明 `git_tracked`、`workspace_untracked` 或 `external_root`。workspace/external evidence 必须可选，不能被当作当前 tracked 真源；external evidence 还必须有恢复说明。
4. `decisions.jsonl` 定位为 append-only、逐记录 `non_authorizing=true` 的查询登记册。每条记录必须引用外部 owner authority source，并用结构化 assertion 验证承重字段一致。登记册本身不能创建、扩大或替代 owner authority。
5. claim 通过 `decision_ids` 连接相关登记记录，但该链接只提供可发现性，不改变 claim 的 authority。未来 `OWNER_RULING_EVENT` 不可变档案面落地后，`ruling_event_id` 可回填；本批不擅自扩展第五种 `representation_class`。
6. stable claim 的语义变化继续遵循显式换代。AB16 收官、throughput 口径和 routing 边界通过新 claim 与 `supersedes` 表达，不原地改写旧命题。
7. 知识层当前计数集中到 `knowledge_census.json`。checker 比较 fixture 与计算性质；测试从 fixture 取期望值，不在多个测试中复制 claim、dossier、triage 或 profile 数字。
8. schema 新增稳定语义字段时，只能通过 `intake.json` 中精确的 `from_schema_version → to_schema_version` 迁移声明补入既有 ID。该豁免只允许“旧记录缺字段、新记录新增字段”，不能夹带 statement、scope 或其他语义改写。
9. `DOC-ADR-014` 原先要求缺失 authority companion 立即阻断。OWNER_RULING_EVENT 档案面尚未落地期间，该联动保留为机器可见、default-off 的 warning：`companion_check.blocking=false`。登记册仍不授权；未来 promotion 只翻转该开关，不另造一套检测逻辑。
10. 补记 Phase 2 Batch 4 对 `DOC-INV-003` 的低披露措辞迁移：`validity_profile` 负责描述 refutation、scope correction 或 semantic replacement 事件，`dependencies` 只描述证明依赖；当旧命题被替代时，两者都不能取代新 ID 指向旧 ID 的 `supersedes` 边。

## 后果

知识 checker 现在不仅验证 JSON 形状，还验证 authority 声明是否有可执行依据、decision 指针是否真的命中外部真源、evidence 的耐久层是否与 Git 拓扑一致，以及表示分类映射是否唯一。账本仍是知识治理对象，不是发布面；文档治理门的绿色也不会授予 production、certification 或 owner authority。
