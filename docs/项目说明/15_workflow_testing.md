# 15｜工作流测试与证据分层

本页规定如何选择测试面、解释结果和维护 fixture。它不保存当前测试数量、通过数量、收集摘要或日志哈希；这些值必须来自同一工作树上的命令输出或登记的机器收据。

## 四层测试目的

| 层 | 主要问题 | 典型载荷 |
|---|---|---|
| Unit | 单个 helper、store、validator 或 lifecycle 分支是否满足局部合同 | 小型内联 fixture、边界值、错误输入 |
| Family | 单个 cut family 的 schema、certificate binding、独立重算和反例是否闭合 | family 专属 fixture、malformed proof、scope drift |
| Integration | 多 family、replay、master lowering 与生命周期交互是否保持原子性 | store、replay、master 或 typed platform 串联 |
| Adversarial | 假证书、错误强化、未绑定 literal、越界单元和 authority 越权是否 fail closed | 明确的红灯反例与负路径 |

不要用文件数、收集数或某次历史运行推断当前覆盖。需要规模时执行相应的 `pytest --collect-only`，并把命令、工作树、环境和退出码与结果一起保存。

## Fixture 组织

family fixture 默认与对应测试共址，保持状态构造和反例边界局部可见。只有多个 family 真正共享同一稳定合同、且共享不会隐藏前提时，才提升为公共 fixture。

`docs/research/**/red_fixtures/` 中的历史反例保留当时语义。将其用于当前测试前，必须确认：

- 规则与模型作用域仍相同；
- fixture 的坐标、端口和 identity 口径仍与当前实现一致；
- 目标 family 仍 active，或测试明确是在验证退役状态；
- 期望结果由当前独立 checker 或 oracle 重新解释，而不是照抄旧报告结论。

## 新 family 或新机制的最低测试包

一次新能力变更通常至少覆盖：

1. schema 与局部 helper；
2. certificate 到 literal / snapshot 的绑定；
3. 独立 evaluator 或 exact checker 的真重算；
4. malformed proof、scope drift 和错误强化等 adversarial 路径；
5. 一条可读的红灯反例；
6. 若进入 master、replay 或 lifecycle，再增加对应 integration 测试；
7. 若改变语义或 authority，更新 claim、decision、规范与框架检查。

测试绿灯不能替代 family admission、owner 决定或 production 接线审查。

## 工作流选择

代码资产治理源定义 developer、evidence、replay、focused 和完整门禁的选择边界。先查询当前入口：

```bash
.venv/bin/python devtools/check_repository_code_assets.py pytest-entrypoints --format json
.venv/bin/python scripts/preflight_gate.py --help
```

日常变更先运行最窄而充分的定点测试，再按操作卡扩大到相关子系统、文档框架、完整非慢速或慢速门。不要把一个 focused lane 写成“全仓通过”。

### 文档治理验收

文档、知识、policy 和框架工具使用 manifest-owned 的非变异门：

```bash
.venv/bin/python devtools/docctl.py gate --profile changed
```

该门为每条 lane 分配独立仓外临时目录，并比较执行前后的 Git-visible fingerprint。它验证文档治理面，不替代 production preflight。需要完整历史 code-assets replay 时使用 `--profile full`；缺少 ledger 指定的 Git object 时必须保留失败。

生成页要在 gate 之前通过显式 `render --write` 重建。gate 或 checker 不应在验收途中自动修复输入树。

## 静态检查

类型、lint、dead-code、安全、复杂度和资产边界检查各自覆盖不同风险。是否需要运行由目标路径的 `docctl context`、代码资产治理和 preflight 入口共同决定。结果记录必须包含实际命令和退出码，不能只写“clean”。

## Viewer sample 与 production 数据

小样本适合单元测试、反例重放和 review 包；生产全集用于真实 campaign 或专门的集成验证。fixture 若绑定具体 pose、候选数或样本几何，必须显式标记数据集身份，不得外推到另一套候选域。

## 维护步骤

修改测试策略或 fixture 约定前运行：

```bash
.venv/bin/python devtools/docctl.py context docs/项目说明/15_workflow_testing.md --intent edit
```

完成后运行操作卡要求的 checker，并把当前收集结果留在机器收据或任务记录中，不回写为本页的永久数字。

历史版本及其当时的 fixture 清单保存在 [`../history/convergence/workflow_testing_pre_phase3_batch4_20260812.md`](../history/convergence/workflow_testing_pre_phase3_batch4_20260812.md)。
