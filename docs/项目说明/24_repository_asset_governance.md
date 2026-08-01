# 24 — 仓库代码资产治理

**Status:** CURRENT
**Updated:** 2026-07-30
**Scope:** G1 代码资产清点、G2 逻辑隔离与 G3 最小公共研究基础层

本文定义代码资产的可复算分类、维护者实现索引，以及 developer、evidence、replay、full
工作流之间的边界。它是仓库维护治理，不是 solver、cut、模型数学、候选、AB16/B6、
Stage-B、上下界或认证语义的 authority。认证边界仍以根目录 `PROJECT_LOCK.md`、冻结输入、
proof obligations 与 owner gate 为准。

## 治理权威与优先级

| 路径 | 角色 |
|---|---|
| `data/repository_governance/code_assets.schema.json` | 分类 manifest 的结构合同与 fail-closed 约束 |
| `data/repository_governance/code_assets.json` | 目录规则、小型显式例外、逻辑隔离投影和带日期基线收据 |
| `devtools/check_repository_code_assets.py` | 从 Git-visible 文件集合重新枚举、分类并校验 manifest |
| `devtools/tests/test_repository_code_assets.py` | 分类互斥、覆盖完整性、搜索/lint/pytest 投影及边界回归 |
| `.rgignore` | 从治理规则得到的 developer 搜索投影；不是 inventory、security 或 proof authority |

分类规则优先使用目录和后缀，只有跨目录的真实例外才进入显式表。manifest 不保存两千个文件的
手工清单；checker 必须拒绝未分类、重复分类、无效例外、失效路径和投影漂移。任何分类都不能
改变文件本身的 production authority：例如，`authoritative_input` 仍须服从其既有哈希和冻结
仪式，`active_implementation` 也不会仅因分类而获得认证权。

## 2026-07-28 基线收据

以下数字是 tracked-clean `main`、HEAD
`201c1988243951e16473af15f5d670ab11edf964` 的带日期快照，不是后续工作树现值：

| 度量 | 数值 |
|---|---:|
| Git-visible 资产 | 3,249 |
| 代码资产 | 2,001 |
| 代码资产 bytes | 36,483,677 |
| 代码资产 LF 行 | 912,444 |
| active implementation | 386 |
| test | 646 |
| common infrastructure | 475 |
| authoritative input | 4 |
| enforcement control | 7 |
| historical evidence | 464 |
| retirement candidate | 19 |
| certified exact-source paths | 800 |
| exact-source path tuple SHA256 | `56e11a22c73ba5a791e4d5b7b8a3ce9fa995a9b7fc43b60ab09bf608cb901905` |
| certified exact-source digest | `d9bedf5fba84e0885349c3b78775331c45b98fcf3a0105477df9ccf8fee354de` |

“Git-visible”指 Git 已跟踪文件加未忽略的未跟踪文件；代码后缀集合和 LF/bytes 口径由 schema
与 checker 固定。维护者不得把旧的 1,933 文件/858,680 行快照或本表数字复制成“当前值”。
当前树必须运行：

```bash
python devtools/check_repository_code_assets.py check
python devtools/check_repository_code_assets.py inventory --format json
```

同一 tracked-clean 基线在 G2 隔离前的 bare-pytest collect-only 收据为 6,624 个 nodeid，
规范化 SHA256 为
`6917fa03f27442fb0d42deb7e143dbd52cb943fd64b3b39551f6eb8509961f96`。它是 before receipt，
不是终态 developer 面；其中包含 6,517 个 `src/tests` nodeid 和 107 个当时被 bare discovery
顺带收集的 auxiliary memory nodeid。

G2 把 non-slow 全集拆成三个互斥面；下表是 2026-07-30 AB16 qualification
收窄、既有 W0 D6 回归及治理测量闭合后的当前收据：

| collect 面 | nodeids | 规范化 SHA256 |
|---|---:|---|
| developer | 3,546 | `cc0c66ba0e8751665ac3da3d51cc3f33afebfdbc66572d441abfec007e73fc2a` |
| evidence、非 replay、非 slow | 1,756 | `5341b4924b0ea12de507710956163eb2b57d4f3e1b90013ade3a796ab57baf20` |
| replay、非 slow | 1,563 | `bac7d8817a81e5637db4c69ad9cbfe1ea4f0c3db5cadd21e6134c1387a55f75f` |
| 三面并集 / full non-slow | 6,865 | `c8562f86531928f02f8f75f2e05c5ef70d87df02d790f61295d4bcbcad126682` |
| full/all | 6,896 | `8cb3f886c1d41b66db4b72530b5126f30b0841dbd5d63e8e77f340b73db8bc59` |
| slow | 31 | `9606959449cd99e6c4ca6c0c305e75f9d4fb4459a159bd2f7daf1e45e82ff6dd` |

三个快速面两两无交，其并集逐 nodeid 等于 full/non-slow；non-slow 与 slow 的并集等于
full/all。新增 AB16 protocol/plugin/qualification、Gate-A authority 边界及普通 preflight
隔离回归进入各自既有 lane；replay 与 slow 收据保持不变。`cuts_collection_counter`
count 保持 958，规范化 SHA256 为
`1431c01e8a0aa94f04bb9071e6cb5d6fdd5415d917133f3758ab9ffdf904bb0d`；
其他既有 focused 入口收据不变。所有数字都是收集面身份，不是通过数量或 soundness 证明。

## 分类合同

| 分类 | 判据 | 生命周期与权威来源 | 默认开发面 | 例外 |
|---|---|---|---|---|
| `active_implementation` | 当前运行实现、入口或仍维护的可执行模块 | 随产品实现演进；authority 只来自既有调用链、`PROJECT_LOCK.md` 和机器门禁 | 导入、搜索、lint、developer tests | env-gated 仍可属于 active；例如 `pose_bool_exact_master.py` 是 active alternative，但 certified mode 显式禁用 |
| `test` | pytest 测试、fixture 或测试专用 helper | 跟随被测合同；测试成功本身不授予 production authority | developer 只收集快速默认面 | evidence/replay/slow 测试由显式 workflow 收集 |
| `common_infrastructure` | 通用 I/O、适配、开发、构建或运维基础设施 | 由实际消费者和门禁约束；不能建立平行认证链 | 活跃部分进入默认搜索/lint | 历史快照内的同名 helper 不因此变成通用库 |
| `authoritative_input` | canonical、frozen 或 hash-bound 输入 | 来源是既有 frozen registry、manifest 与 `PROJECT_LOCK.md`；变更须走原冻结仪式 | 始终可搜索并进入完整边界检查 | 不因体积或历史路径被 `.rgignore` 隐藏 |
| `enforcement_control` | schema、policy、checker 或决定门禁覆盖面的控制文件 | 结构治理 authority；修改须保持 fail closed | 始终可搜索、lint 和测试 | 不得替代 proof obligation 或 owner gate |
| `historical_evidence` | 研究源码、可执行快照、复现 harness 或时间点证据 | 原路径和字节长期保留；其 claim 仅限自身封存边界 | 从默认导入、代码搜索、lint、pytest 发现隔离 | explicit-path evidence/replay/full 仍可执行和校验 |
| `retirement_candidate` | 已由小型显式表登记、待后续 owner 决策的旧实现 | 保持 tracked；候选状态不授权删除、移动或改写 | 从默认导入、代码搜索、lint、pytest 发现隔离 | security、secret、artifact-boundary 和 full gates 仍覆盖 |

`docs/research/**` 默认是历史证据，但 `PROJECT_LOCK.md` §2B 指定的
`p3_b_design_v2_20260521/{cut_lifecycle_v2.md,state_machine_v2.md,cut_family_specs/**}`
是 current specs。搜索投影隔离 manifest 指定的历史 executable trees；对
`docs/research/**` 只匹配代码后缀和一个显式 verbatim-code Markdown，不 blanket 隐藏研究文档，
也不会隐藏这些 current specs。

`src/search/phase3b/**` 不能按目录名整体视为历史快照：其中仍有进入 exact-source TCB、并由
`benders_loop` 合法导入的当前模块。G2 隔离的是 `scripts/phase3b/**`、`src/tests/phase3b/**`
以及三个显式 `scripts/run_phase3b_*.py` replay wrapper；后者仍可通过 replay/full 通道运行。

## 维护者实现索引

下表给出活动代码的首选入口，并明确哪些重复能力仍是 snapshot-local。G3 只为隔离实验提供
字节级输入、运行目录和 replay 合同；它位于 `devtools/`，不进入 production import 图、
certified exact-source TCB、solver、cut、上下界或 checkpoint authority。历史证据中的同名
helper 仍由各自封存字节约束，不作为公共实现来源。

| 能力 | 首选或 context-bound 入口 | 重复实现边界 |
|---|---|---|
| strict JSON | `src/io/strict_json.py::loads_strict_json` 是 shared authority；exact campaign 保留 `_loads_strict_json_object` | 新活动调用优先复用 shared contract；checkpoint compatibility、隔离 TCB 与 sealed replay 可保留自包含 decoder |
| stable snapshot read | `devtools/research_run_contract.py::read_stable_snapshot` 是 developer/research shared authority；exact campaign 保留 context-bound reader | 公共合同绑定一次打开所得实际 bytes、前后 `fstat` 与 SHA-256；SMM4 的 `snapshot_regular` 只属于冻结 replay |
| retained same-FD | 无活动 shared authority | SMM4 与 AB16 各自 `snapshot_regular` 由封存 bytes 约束，不能跨包导入 |
| exclusive no-overwrite | `devtools/research_run_contract.py::ExclusiveRunRoot` 是 developer/research shared authority；exact campaign 保留 checkpoint-context lock | 公共实现只管理新建的隔离 run root；不替代 campaign lock 或 sealed replay writer |
| canonical config/receipt | `devtools/research_run_contract.py::canonical_json_bytes` 是 developer/research shared authority；`build_artifact_root_manifest` 从可信锚点逐组件 no-follow 打开 root，枚举写回执前的完整 root | manifest 只登记除固定 `receipt.json` 外的全部后代 path/type；不保存也不声称 receipt 自身哈希。experiment payload 保持不透明，不能携带实验数学的公共 authority |
| independent replay | `devtools/research_run_contract.py::verify_artifact_root_closure` 是 artifact-root closure shared authority；`replay_identity_graph` 复核命名字节图，`run_isolated_replay` 与 `require_isolated_python_process` 约束 `-I -B` 子进程 | root 与全部后代目录的 FD/signature 保留到完整枚举结束再逐一复核；完成态 root 必须恰为 manifest 条目加唯一普通文件 `receipt.json`，额外文件、目录、symlink 或特殊节点 fail closed。公共层不解释 FEASIBLE、INFEASIBLE、front、cycle 或任何实验语义 |
| resource receipt | 无活动 shared authority | AB16 resource-receipt family 与 SMM4 `_validate_resource_receipt` 均为冻结证据图的一部分 |
| terminal receipt | `src/search/exact_campaign.py::terminal_certified_final_result_violation_for_project` | AB16 terminal-receipt family 只属于 immutable closeout |

相邻但不互换的活动子系统入口包括
`src/cuts/state_snapshot.py::build_validated_state_snapshot`、
`src/cuts/frozen_artifacts.py::build_frozen_artifact_bundle`、
`src/search/certified_artifact_contract.py`、PR2 L0 verifier、terminal fixed-witness capsule 和
`src/search/certified_surface.py`。它们分别服务 cut state、artifact contract、隔离 TCB、
terminal witness 与中央发布事务，不能因为名称相近而当作通用 snapshot/no-overwrite/receipt helper。

AB16、SMM4 及其他历史研究包中的 same-FD、retained-FD、exclusive/no-overwrite、
resource receipt 和 terminal receipt helper 仍由各自封存源码与哈希约束。它们没有被宣布为活动
通用基础设施，也不得被生产代码跨边界导入；evidence/replay 通道按原路径执行。

G3 运行工件只写入 `data/artifact_boundaries.json` 登记并由 `.gitignore` 精确忽略的
`.artifacts/research_runs/`。该前缀是 regenerable research runtime，不是 tracked historical
evidence；运行目录必须独占创建，既有路径或文件不得覆盖。artifact-root manifest 的闭包语义
不自指：内嵌 manifest 排除固定终端 `receipt.json`，回执写入前验证 manifest 恰为全部后代，
写入后再验证 manifest 加该固定普通文件恰为全部 root；回执不得保存自身内容哈希。该闭包只陈述
验证时观察到的目录集合，不把普通可写目录冒充为文件系统级封存。

## 默认面与显式完整通道

| 目的 | 命令或入口 | 行为 |
|---|---|---|
| developer 搜索 | `rg -n '<pattern>'` | 遵守 `.rgignore`；只减少日常噪声 |
| 全部 tracked 搜索 | `git grep -n -I -e '<pattern>' --` | 不读取 `.rgignore`；可审计 authority、安全边界和历史路径 |
| developer lint 投影 | `python devtools/check_repository_code_assets.py lint --profile developer --format nul` | 输出 NUL-safe Python 开发资产集合；不自行运行 Ruff |
| full lint 投影 | `python devtools/check_repository_code_assets.py lint --profile full --format nul` | 输出 NUL-safe 全仓 Python 资产集合；不读取 `.rgignore`，也不自行运行 Ruff |
| pytest 入口收据 | `python devtools/check_repository_code_assets.py pytest-entrypoints --format json` | 输出登记的入口/预期收据；不运行 pytest |
| developer pytest | `python -m pytest --repository-workflow=developer src/tests` | 快速默认面；隔离历史 evidence/replay 收集 |
| evidence pytest | `python -m pytest --repository-workflow=evidence src/tests -m "evidence and not replay and not slow"` | 显式纳入非 replay 的快速 evidence 合同 |
| replay pytest | `python -m pytest --repository-workflow=replay src/tests -m "replay and not slow"` | 显式纳入快速 replay 合同 |
| focused compatibility | `--repository-workflow=focused-full` | 供既有显式目标/CI lane 使用；不把路径选择误判为 bare developer |
| auxiliary memory full | `python -m pytest cc_memory/tests cc_memory_vnext/tests` | 显式收集 107 个辅助 memory tests；`testpaths` 不再让它们意外混入 bare developer |
| 完整非 slow 门禁 | `python scripts/preflight_gate.py --full` | 保留全仓 lint、pytest、hash、secret、artifact-boundary 与安全边界 |
| 完整 slow 门禁 | `python scripts/preflight_gate.py --slow-tests` | 单独运行 slow soundness lane；不能由 `--full` 代替 |

Linux 上的 developer Ruff 快速面把 NUL 投影直接交给既有 Ruff 配置：

```bash
python devtools/check_repository_code_assets.py lint --profile developer --format nul \
  | xargs -0 -r python -m ruff check
```

不带目标的 bare pytest 由仓库 conftest 的 early isolation 解析为 developer 面；
`scripts/select_tests_for_paths.py` 保持原字节，其既有唯一 `--basetemp=.pytest_tmp/selected`
是 developer compatibility discriminator。显式路径、evidence、replay、focused-full 与 full
不会被默认收集面静默吞掉。

`.rgignore` 不参与 Python import 决策，也不参与 Git 枚举。secret scan、artifact-boundary、
冻结哈希、安全检查、治理 checker 和 preflight 必须从 Git-visible/显式路径枚举，不能通过隐藏
文件制造“全仓干净”的假象。

默认 production source discovery 继续使用既有的两处 source tuple；治理回归要求两者一致，
并要求 `devtools/` 不进入 certified TCB/source discovery。历史源码不新增 package 入口，也不由
活动代码导入。该边界是默认工作流隔离而非运行时沙箱：evidence/replay 仍可用显式路径加载封存
模块，checker 也不会把“默认未发现”夸大为全仓 import 不可能性。

## 兼容、回滚与维护

- 所有历史路径、symlink 拓扑、frozen/sealed/hash-pinned bytes 原位不变；逻辑隔离不迁移、
  不删除、不 reseal。
- `.rgignore` 只影响 developer `rg`。需要临时恢复旧搜索体验时可显式使用 `git grep`；
  回滚该投影也不会改变 Git、import、pytest 或 authority。
- pytest workflow 是入口选择，不重写测试或历史导入。旧的 explicit-path/full 调用保持完整覆盖。
- manifest/schema/checker 是唯一治理实现；不得另建第二份分类表或在 CI 内复制分类规则。
- 新代码资产必须在同一变更中获得唯一分类。目录规则覆盖不了的情况才增加显式例外，并说明
  authority、默认 workflow 与退出条件。
- retirement candidate 的退出只能是重新分类或经授权的后续删除；本治理状态不自动触发任何一项。

## 验收门

合入前至少满足：

1. `python devtools/check_repository_code_assets.py check` fail-closed 通过，且每个 Git-visible
   代码资产恰有一个分类；
2. `python -m pytest -p no:randomly --basetemp=.pytest_tmp/repository-governance
   devtools/tests/test_repository_code_assets.py -q` 通过；
3. developer、evidence、replay 和 focused/full 入口的 collect 身份与预期一致；
4. `.rgignore` 隐藏的只有 manifest 声明的历史源码/可执行资产和 19 个 retirement candidates，
   `PROJECT_LOCK.md`、current specs、`pose_bool_exact_master.py`、rules 与 governance controls
   仍在默认搜索面；
5. frozen/sealed/hash-pinned 路径相对基线无字节差异，symlink 清单与目标不变；
6. focused checks、`preflight_gate.py --full` 与 `preflight_gate.py --slow-tests` 分别通过；
7. secret scan、artifact-boundary、安全检查和完整 preflight 未使用 `.rgignore` 缩小覆盖。
