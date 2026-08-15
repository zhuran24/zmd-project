# 文档系统常态维护合同

本页是文档系统完成阶段性重构后的耐久交接面。它由 `.docsystem/manifest.json` 的 `steady_state_guide` 字段定位，解释系统进入常态后怎样继续维护，而不再依赖连续编号的大型整理批次。

本页不陈述当前 gate、研究上下界、hash、测试数量或 owner 决定。当前事实仍由结构化真源和生成投影负责；本页只规定维护事务、审计节奏、框架再开启条件与 fail-closed 边界。

## 1. 完成意味着什么

阶段性文档重构完成，表示下列能力已经成为仓库自身的一部分：

- 文档路径可以解析出最小操作卡、修改边界、原因和后续检查；
- 新文档、新 dossier、新 claim 与 authority companion 在变化发生时进入同一 intake 事务；
- 当前状态、知识目录、主题、术语、维护队列和职责图由结构化源生成；
- 历史证据保持历史含义，不追随现态改写；
- 周期审计只发现遗漏、陈旧与碰撞，修复仍回到原有真源；
- 本地、CI 与真实仓库落地使用同一组 manifest-owned 合同；
- 缺少历史 Git 对象、外部档案根或 owner 权威时继续显式阻断，不把环境缺失改写成通过。

完成不表示项目知识停止增长，也不表示所有开放问题已经解决。它表示后续变化不再需要通过“再做一轮全库考古”才能进入可维护状态。

## 2. 唯一日常写入路径

普通文档工作始终从目标路径开始：

```bash
.venv/bin/python devtools/docctl.py context <path> --intent <edit|create|move|delete>
```

完成写入后，先重建本次真正受影响的投影，再运行：

```bash
.venv/bin/python devtools/docctl.py intake --changed
.venv/bin/python devtools/docctl.py check --changed
.venv/bin/python devtools/docctl.py gate --profile changed
```

这三步分别回答：

1. 本次变化触发了哪些文档事件，是否缺少 companion；
2. diff、policy、知识账本与生成页是否闭合；
3. 所有当前治理 lane 是否在同一 Git-visible 输入上只读通过。

不要在生成页上直接修字，也不要新建第二份“临时当前状态”来绕过结构化源。需要修复的是 generator 的输入或生成逻辑。

## 3. 四类变化与所需上下文

| 变化 | 典型内容 | 维护边界 |
|---|---|---|
| L0 内容变化 | living 文档的解释、链接或排版 | 读取操作卡与相关短原因，运行内容检查 |
| L1 知识变化 | claim、decision、dossier、topic、terminology | 更新稳定 ID、作用域、证据和投影，不静默改写语义身份 |
| L2 局部合同变化 | `coverage_update` 或既有目录的 `contract_change` | 比较父子 policy，说明影响范围；只有合同语义变化才需要相应设计说明 |
| L3 框架变化 | schema、manifest、resolver、核心 invariant、治理 runner | 原子更新架构、ADR、迁移、生成物和红测 |

给新内容增加精确 policy 覆盖，不等于改变框架语义。只有改变继承算法、schema、解释语义或核心不变量时，才重新进入 L3。

## 4. 事件触发优先，周期审计兜底

事件驱动维护负责“变化发生时立即入账”。典型触发包括：

- 新建或移动 current Markdown；
- 新研究 dossier 打开或关闭；
- claim 含义、作用域、authority 或 supersession 变化；
- owner-governed 路径改变；
- generated projection 的真源变化；
- ephemeral 文档到期或 local-optional evidence 新增。

周期审计负责发现写入机制没有直接看见的问题：

```bash
.venv/bin/python devtools/docctl.py audit --profile weekly
.venv/bin/python devtools/docctl.py audit --profile deep
.venv/bin/python devtools/docctl.py audit --profile phase_close --as-of YYYY-MM-DD
```

`weekly` 适合固定调度；`deep` 对逾期 warning 也 fail closed；`phase_close` 列出阶段边界需要人工确认的表面。审计结果不是第二个 truth ledger，不能在 `MAINTENANCE_QUEUE.md` 中手工“关闭”。修复必须回到真正负责该语义的 policy、claim、decision、dossier 或 owner 真源。

## 5. 当前门、历史回放与 production 门的分工

文档治理门回答文档结构、知识投影、artifact 分类和当前 code-assets 是否自洽。production preflight 回答求解、认证、发布与冻结边界是否满足。两者都通过，仍不能越过 owner authority 或数学证明边界；任一门阻断，也不能把整体写成已通过。

当前治理 profile 不冒充历史 replay。需要完整冻结 Git object graph 的检查只通过手工 `historical_replay` 运行。production 边界使用 `.venv/bin/python scripts/preflight_gate.py --full`；真实外部档案根缺席时，依赖它的检查保持 fail closed。不得通过跳过测试、改写冻结摘要、把 workspace evidence 加入 Git，或降低 authority 来制造绿灯。

## 6. Workspace overlay 与真实仓库落地

`CLAUDE.md`、`AGENTS.md` 可以作为可选 `workspace_untracked` overlay 存在。它们不是 tracked 生成页的硬输入，也不能由补丁应用脚本静默纳入 Git。耐久 agent 协议位于 `docs/AGENT_OPERATIONS.md`。

真实共享仓库落地必须遵循：

```bash
.venv/bin/python devtools/document_patch_landing.py --help
.venv/bin/python devtools/docctl.py landing -- --help
```

工具只规划、校验、保存漂移字节和生成精确 pathspec，不执行 `git reset --hard`、`git clean`、`git add -A`、`git commit` 或 `git commit --amend`。未知漂移和未登记 collision 必须阻断；已登记漂移也只有在落地时点原字节归档、typed ACK 与 append-only 验证完成后才能安装 successor。

## 7. 框架何时重新开启

常态维护不再因为普通积压自动产生新的 Phase 或 Batch。以下情况才构成新的独立框架迁移：

- 修改核心不变量；
- 增加或改变 policy / manifest / knowledge schema 的解释语义；
- 改变 `docctl` 继承、authority 准入或生成算法；
- 改变治理 profile、只读边界、真实仓库 landing 事务；
- owner 决定引入新的权威档案面，例如正式 `OWNER_RULING_EVENT`。

框架迁移必须使用新 ADR、显式版本变化、兼容或迁移说明、定点红测和完整治理收据。不要仅因为工作量较大就继续编号，也不要用编号替代语义边界。

## 8. 恢复与发现

正常查询入口：

```bash
.venv/bin/python devtools/docctl.py guide
.venv/bin/python devtools/docctl.py explain DOC-INV-023
.venv/bin/python devtools/docctl.py explain DOC-ADR-020 --full
```

完整概念见 [`ARCHITECTURE.md`](ARCHITECTURE.md)，安全修改方法见 [`MAINTAINING.md`](MAINTAINING.md)，设计历史见 [`ADR/README.md`](ADR/README.md)。固定坐标分别是 `docs/governance/document-system/ARCHITECTURE.md`、`docs/governance/document-system/MAINTAINING.md` 与 `.docsystem/RECOVERY.md`。manifest 或 resolver 损坏时读取 [`.docsystem/RECOVERY.md`](../../../.docsystem/RECOVERY.md)，不要依赖已经可能陈旧的生成页自救。

## 9. 常态验收底线

一次文档相关提交至少应满足：

- 目标路径有可解析 policy，且操作未越过 mutation 边界；
- 所有结构化账本和生成投影一致；
- intake 事件闭合，没有未解释的稳定身份改写；
- `docctl doctor`、引用检查和 changed governance 在同一输入树上通过；
- checker 没有修改 Git-visible 状态；
- workspace-untracked 与 external evidence 没有被误报为 Git-tracked；
- 外部前置条件缺席时，结果明确标为 blocked，而不是“等价通过”。

这套合同由 `DOC-INV-023` 与 `DOC-ADR-020` 固定。它的目标不是让文档永远不变，而是让变化顺着同一条河道前进，不再每隔一段时间重新挖一条河。
