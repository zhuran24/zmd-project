# 24｜仓库代码资产治理

本页描述代码资产分类和工作流隔离的稳定合同。当前文件数量、代码行数、测试收集摘要、哈希和 retirement inventory 只由机器 ledger 与 checker 输出，不在本文维护副本。

## 真源与命令

机器真源位于：

- `data/repository_governance/code_assets.json`
- 相邻 schema 与 checker；
- `devtools/check_repository_code_assets.py`。

常用查询：

```bash
python devtools/check_repository_code_assets.py check
python devtools/check_repository_code_assets.py inventory --format json
python devtools/check_repository_code_assets.py pytest-entrypoints --format json
```

“Git-visible”、代码后缀、行尾与字节口径均由 schema 和 checker 定义。命令输出只代表它声明的工作树与 revision。

## 分类合同

每个 Git-visible 代码资产必须恰好属于一个机器登记类别。核心类别包括：

| 类别 | 稳定含义 |
|---|---|
| `active_implementation` | 当前运行实现、入口或仍维护的可执行模块 |
| `test` | pytest 测试、fixture 与测试专用 helper |
| `common_infrastructure` | 通用 I/O、适配、开发、构建或运维基础设施 |
| `authoritative_input` | canonical、frozen 或 hash-bound 输入 |
| `enforcement_control` | schema、policy、checker 或门禁控制文件 |
| `historical_evidence` | 研究源码、可执行快照、复现 harness 或时间点证据 |
| `retirement_candidate` | 已显式登记、等待后续 owner 决策的旧实现 |

分类只规定治理和默认工作流，不自动授予数学、production 或 certification authority。

## 当前实现与历史证据的边界

不能仅凭目录名把整棵树判为 current 或 historical。例外和混合目录必须由机器 manifest 精确登记。历史 evidence 保留原路径与字节，不进入默认开发噪声面，但仍能通过显式 evidence、replay、full、安全或 frozen-hash 检查被审计。

默认搜索、lint 或 pytest 投影是工作流便利，不是运行时沙箱，也不能缩小 secret scan、artifact boundary、权威输入、冻结哈希或完整 preflight 的覆盖。

production source 对 `devtools` 的 import 始终禁止。若既有 production 常量仅保留一个已退役工具的 fail-visible 路径，manifest 例外必须精确绑定文件、赋值符号和字面量，并保持 `literal_only / dormant_advisory_pointer`；宽泛路径、动态调用、import 和失效记录都会被 checker 拒绝。

## Artifact evidence 的两层表示

语义真源不是 `data/artifact_boundaries.json` 里的长前缀表，而是两处更小的输入：

- 一级 `.artifacts/<dossier>/` 证据根来自 `data/knowledge/dossiers.json`；
- 直接位于 `.artifacts/` 下的受跟踪文件和 runtime-only 前缀来自
  `data/repository_governance/artifact_evidence_inputs.json`。

`data/artifact_boundaries.json` 是自动生成的 schema-v1 兼容投影。冻结的
`scripts/check_artifact_boundaries.py` 仍消费这个固定路径和旧形状，因此生成器会同时输出
普通前缀与适配 Git 行式 C-quoted 路径的兼容前缀。语义消费者只使用 dossier 根与显式根文件，
不会把兼容字符串当成新的仓库路径。

正确维护顺序是：

```bash
.venv/bin/python devtools/artifact_evidence.py render --write
.venv/bin/python scripts/check_artifact_boundaries.py
.venv/bin/python devtools/artifact_evidence.py check
.venv/bin/python devtools/check_repository_code_assets.py inventory --format json
```

新增 tracked artifact package 时先登记 dossier；新增直接根文件时修改 semantic input；runtime
输出必须留在 ignored prefix，且不得与证据根重叠。不要手改生成投影，也不要为了适配投影而
直接修改冻结 checker，除非进入经 owner 授权的 certified source reset 与完整重验流程。

## Artifact evidence 与 code-assets inventory

当前工作树 inventory 会在读取内容前排除已登记的 artifact evidence。这样可以保留研究快照的
Git 可见性，同时避免其中的脚本副本被误算为当前代码资产。未登记的 `.artifacts/**` 代码仍按
普通代码资产分类，并触发 expected-count 漂移。

历史 commit inventory 则保持原始测量，不套用今天的 dossier 豁免。这样在完整 Git 历史中，
旧 baseline 可以按当时的 tree 重放，而不会被后来的文档登记重新解释。注册 evidence 不会把它
提升为 current、可执行、certified 或 production authority，也不单独证明字节不可变。不要用
`inventory --commit HEAD` 替代 live boundary 检查；两种 inventory 刻意保留不同语义。

## 共享 helper 的提升规则

只有当多个活动消费者真正共享相同语义、错误模型和生命周期时，才把 snapshot-local helper 提升为公共基础设施。提升时必须：

1. 明确公共合同和不包含的实验语义；
2. 保留历史包对原字节和原 helper 的复现能力；
3. 更新消费者、测试、资产分类与回滚路径；
4. 避免让名称相近的 snapshot、receipt、replay 或 no-overwrite 机制被错误互换；
5. 确认新公共层不进入未授权的 certified TCB 或 production import 图。

## 工作流选择

开发搜索、tracked 全量搜索、developer lint、full lint、developer/evidence/replay/focused pytest、完整 preflight 与慢速门各有独立用途。具体命令和当前入口由机器 ledger 输出，维护者应在同一工作树上查询后执行。

显式路径或完整门不能被默认投影静默吞掉。一个工作流的通过结果不得写成另一工作流或全仓的结论。

## 新增、重分类与退役

新增代码资产必须在同一变更中获得唯一分类。目录规则无法准确覆盖时才增加显式例外，并写明 authority、默认 workflow、复核条件和退出路径。

`retirement_candidate` 只是待决状态，不授权删除、移动或改写。退出只能通过明确的重新分类或经授权的后续删除。历史 evidence 的移动或字节变化另受其只读与复现合同约束。

## 验收边界

资产治理验收至少检查：

- 每个 Git-visible 代码资产唯一分类；
- 默认与完整搜索、lint、pytest 投影符合 manifest；
- current authority、安全与治理控制未被便利投影隐藏；
- frozen、sealed、hash-bound 与历史载荷保持所需身份；
- secret、artifact-boundary、安全和完整 preflight 不依赖缩小覆盖的 ignore；
- checker、schema、文档和回归测试原子一致。

机器检查通过只证明资产治理合同，不证明 solver soundness、owner close 或 publication。

历史版本及其当时的清单和收据保存在 [`../history/convergence/24_repository_asset_governance_pre_phase3_batch4_20260812.md`](../history/convergence/24_repository_asset_governance_pre_phase3_batch4_20260812.md)。
