# W0 power-cycle domino：D6 局部联合 completion gate

**状态：** RESEARCH_ONLY / LOCAL_D6_ONLY / TWO_V2_NEGATIVE_ROOTS_ACCEPTED /
SWAP_V3_REPLAY_ACCEPTED_INFEASIBLE

**更新日期：** 2026-07-30

**全局账本：** tracked 状态仍为 `U=(1188,18)`、`L=absent`；本目录的 local
config/receipt/replay 不复制或声称携带 U/L。

本目录实现 power-cycle domino framework 的 exact、front-aware D6 局部联合 gate。两个
closed-root v2 antecedent 与随后唯一放宽 class transfer 的 swap v3 antecedent 均已得到
replay-accepted `INFEASIBLE`。swap v3 保持 power-cycle、D6 的 6×7 protected rectangle、
28 个合法 attachment slots、全局 class ledger 和其他 W0 全局不变量不变，只交换 D6 与 D9
的一个 class。

任何本目录结果都不产生 whole-layout witness、全图 cut、lower-ledger、全局 infeasibility、
production authority 或 certified exact-source authority。持久 producer 与 durable replay
材料只写入 `.artifacts/research_runs/` 下的新 no-overwrite roots；第二份异构 replay
receipt 写入 fresh `/tmp` no-overwrite root。历史 roots 不删除、不改写、不补写。

## 已接受的 v2 negative roots

以下两组结果均已用 root 内 SHA-pinned v2 replayer 独立逐字重放，两份异构 replay receipt
逐字节一致：

| profile / producer root | exact antecedent SHA-256 | producer `receipt.json` SHA-256 | replay receipt SHA-256 | 精确结论 |
|---|---|---|---|---|
| `seed_narrow` / `w0-d6-seed-narrow-v2-20260728T162612Z-3bc004459ef3` | `7dd634386b4c27a695a7115bd0dddf1c67556ab58923e9dfe526e5f7ee54e59f` | `275cb3cf306a7fcecb02d9b243330c8dd0d648cf1f43d75390d97fc7d16ca8dd` | `6a8c662b0592c378c607e53411559c2efcf2e8a28e320e7aae6d626b54b7cd0e` | 该 seed-narrow D6 antecedent `INFEASIBLE` |
| `all_legal_d6_slots` / `w0-d6-all-legal-slots-v2-20260728T162612Z-3bc004459ef3` | `a5fc8a3a3814970f2401d4c27800e422f8cb46cd358b6d07451f9935f76ddef3` | `abff1d867c1b93395b16eafb886e5b454fccb091f57eeade685a68e1b90e40eb` | `9d0581e0429dab5c76a7f132c175e9aa3a42043d113b2719b96269caa1683284` | 该 28-slot D6 antecedent `INFEASIBLE` |

`seed_narrow` 只排除了原 class allocation 下的 11 个 seed-derived slots；它没有排除同一局部
几何上的其他合法 attachment slots。`all_legal_d6_slots` 随后把 attachment scope 扩至固定的
全部 28 slots，因此排除了“只移动 D6 attachment slot”这一修复轴。两者都没有改变或排除：

- D6 与 D9 之间的最小 class transfer；
- 安全 pole anchors；
- tile 内 size 分配；
- domino pairing；
- 其他 D 区、whole witness 或全图可行性。

因此这两个 `INFEASIBLE` 只关闭各自精确 local D6 antecedent，不是 cut、全局拒绝或
lower-ledger 证据。

两个 v2 negatives 后仍未改变的四个轴中，class transfer 是唯一既不移动 body/pole、也不改变
tile split 或 pairing，且能以同 template 的 `6B↔6G` 保持全局 ledger 精确不变的单轴
delta。当时的 receipts 没有把 anchor、tile split 或 pairing 单独识别为冲突来源；一次改动
它们会引入新的 geometry 或组合轴，证据上不比这个单计数交换更小。因此 swap v3 选择了
class transfer，其他三轴保持不动。

另有更早的 historical producer root
`w0-d6-seed-narrow-20260728T132308Z-27b4ae9`。它使用缺少完整 root-closure 合同的
`w0_d6_receipt_payload_v1`，且 root 内存在未登记的 `sources/__pycache__/*.pyc`。它只能说明
receipt 登记的命名字节图曾通过，不能声明完整 root 已闭包。新版只能稳定返回
`ROOT_CLOSURE_CONTRACT_MISSING`；禁止为兼容而放宽。这里的 historical
`receipt_payload_v1` 不等于下表中当前已接受 v2 roots 使用的 `antecedent_v1`。

## swap v3 终态结果

首个实现提交为 `db00416d3c687dfca28695fa972b768a3f31ee4e`。solver-free focused、
Ruff、定向 mypy、asset/boundary/governance 验收通过后，执行链在两次相同资源门禁之间完成
`scripts/preflight_gate.py --full`：preflight `19 passed`，其中 full non-slow pytest 为
`6463 passed, 153 skipped`。随后只启动一次固定的 swap v3 producer：

| 项 | 终态 identity |
|---|---|
| producer root | `w0-d6-6b-d9-6g-swap-v3-20260728T202427Z-db00416d3c68` |
| protocol / profile / attachment scope | `w0_d6_swap_v3` / `d6_6b_d9_6g_swap_v1` / `all_legal_d6_slots` |
| exact antecedent SHA-256 | `dab2a3282b4d4c632d4e0260cc364f397b567f108dbf6480db5d1553a41a9221` |
| config SHA-256 | `512af594f6730dcc58be3d3064e9ecc4629f2d42a45151a68fb97e465abce14d` |
| result SHA-256 | `55498c85684aa6b48d8e16ae3e10140276caec4e0b63726901d870ae79824963` |
| identity graph SHA-256 | `81711a4396904fb217fce4cc66c9d3e9577564be7d7cb7c5bf244f0c4ea93c75` |
| producer `receipt.json` | `1f5236c39d6f9b827c6244da49fb16f81d97faf0822062042de5dff1e57e620c` / 5,049 bytes |
| producer terminal | `INFEASIBLE`; `artifact_root_closed=true`; `interrupted=false` |

root 内 pinned v3 replayer 分别由 coherent CPython 3.13.13 和 fresh `/tmp` 下的
`/usr/bin/python3` 3.14.6 以 `-I -B` 执行。两份 replay 都返回 `PASS`，输出逐字节一致：

| 项 | 终态 identity |
|---|---|
| durable replay root | `w0-d6-6b-d9-6g-swap-v3-20260728T202427Z-db00416d3c68-replay` |
| replay receipt SHA-256 / size | `568b58bb5e72580dead23936242faa69a7ccbda9e2ec4e3b7476a9bc66cc6f24` / 6,709 bytes |
| closure / byte graph / antecedent recomputation | `verified=true` / `verified=true` / `verified=true` |
| exact conclusion | `exact_d6_antecedent_infeasible_only` |

这个结果只关闭 SHA-256 为
`dab2a3282b4d4c632d4e0260cc364f397b567f108dbf6480db5d1553a41a9221`
的 exact local D6 swap antecedent。D9 仍只是未求解的 ledger 算术补偿；结果不排除改变
safe pole anchors、tile 内 size allocation 或 domino pairing 后的其他 antecedent，也不产生
whole witness、cut、全局 infeasibility 或 lower-ledger 结论。按三态合同，本轮在该
replay-accepted `INFEASIBLE` 处停止；不自动进入另一轴、D7 或多轴放宽。

## 版本矩阵与协议绑定

W0 D6 只接受两个原子 cohort；schema 不能独立挑选或跨行混搭：

| cohort | antecedent | config payload | receipt payload | replay receipt | 使用范围 |
|---|---|---|---|---|---|
| accepted closed-root v2 | `w0_d6_antecedent_v1` | `w0_d6_run_config_v2` | `w0_d6_receipt_payload_v2` | `w0_d6_replay_receipt_v2` | 上述两个已接受 roots |
| swap v3 | `w0_d6_antecedent_v2` | `w0_d6_run_config_v3` | `w0_d6_receipt_payload_v3` | `w0_d6_replay_receipt_v3` | `d6_6b_d9_6g_swap_v1` |

任意跨版本混搭都必须在解释 solver status 前 fail closed，稳定返回
`ARTIFACT_PROTOCOL_COHORT_MISMATCH`，且 `conclusion=null`。工作树中的新版 v3 replayer 受自身
source pin 约束，不能声称直接重放历史 v2 roots；历史 v2 roots 只能继续用各 root 内的
SHA-pinned v2 replayer。新版的 v2/v3 兼容解析与分派只用固定的合成 fixture 验证。

swap v3 的 CLI、config、receipt、antecedent 和 replay 必须逐字段交叉绑定以下七字段
protocol object：

```json
{
  "cohort": "w0_d6_swap_v3",
  "class_allocation_profile": "d6_6b_d9_6g_swap_v1",
  "antecedent_schema": "w0_d6_antecedent_v2",
  "config_payload_schema": "w0_d6_run_config_v3",
  "receipt_payload_schema": "w0_d6_receipt_payload_v3",
  "replay_receipt_schema": "w0_d6_replay_receipt_v3",
  "project_lock_sha256": "e7a43fe0509fe853b18e487d36d230b14a0ba856f0f6c745ac33fd7346ac71b7"
}
```

上框记录的是已经执行并由 root 内 SHA-pinned v3 replayer 验收的历史
swap-v3 root；不得把其中的 lock identity 就地改写。首个 checked-in
successor 因 `PROJECT_LOCK.md` 新增 AB16 research-only cohort，改钉
`e8130589effaa332122260b44df9aed367cdb9d1bc96ca17b24a1075007a24b3`，
同一数学 profile 的静态 antecedent fixture 为
`3d40e1318b631119ca5314f31443b91dbada2d5a1125e3f8da7c4c3dcf8db394`。
当前 checked-in successor 为
`aeadef3aded03099d18580a05454c90af11a4dd6859d7798516ced73d2df2b42`（2026-08-05
严格空地修复批 + 谓词甲案 + canonical emptiness freeze-ritual 后版本），对应静态
antecedent fixture 为
`6efaff3e15cf1e6b173e244ff26f79d55dd78a0988162f34079191630aa7a8a0`。
上一代 successor 为 `64a6802446de075293e32c6607d24cfe872d2070b6cd66f4e53cb275483aa69a`
（2026-08-03 AB16 收官后版本，antecedent fixture
`7de91e645d0a92d03f9593e8af20be43be8147f406a98e9accaea6ed7080b78d`）。

> **2026-08-03 订正**：本段原钉
> `a2ec971f687c04966e8329868b4eab05aaa3c9fd9ad71a96f0ab79df85b92559` 为「当前
> checked-in successor」，但该字节**从未存在于本仓库任何一次 `PROJECT_LOCK.md`
> 提交**（51 个历史版本逐一 sha256 比对，零命中；也不等于被 revert 的 `62bc65f`
> 时点值 `114ea93e…`）——它是 codex 自治期在某个未落地状态下算出的幻影，且被
> 同批钉进 `run_d6_research.py`/`replay_d6_certificate.py`/`d6_joint_completion_gate.py`
> 与两个 `src/tests/test_w0_d6_*.py`。因为那两个测试的外部输入路径同时写错
> （`~/下载/w0回复/` 实为 `~/下载/gpt回复/`），11 条测试自落地起始终 `skip`，
> 这个指向虚空的运行门禁从未被执行到。订正=改钉当前真实 checked-in 字节；
> 安全性依据：D6 历史 root 绑定的 `e8130589…`（commit `57c8b352`）到当前
> `64a68024…` 的全部 lock 改动（110 插入/123 删除）**均在 AB16 段**，§3B 的
> 「W0 D6 research-only artifact protocol boundary」条款逐字未变，新版头部亦明写
> `prior certified, W0, P1.2, and Stage B boundaries unchanged`。历史 root 的
> 绑定值 `e8130589…` 不变（下段「不迁移、不补写」照旧）。静态 antecedent fixture
> 随之从 `94f72b64…` 改钉 `7de91e64…`——这是下段所述「identity 变化只来自 lock
> scalar」的机械连锁（`build_d6_antecedent` 把 lock sha 放进 `protocol` 参与
> canonical hash），已用门禁解释器独立重算复核，非新的 solver 结果。
这些变更只影响未来 W0 run 的 source/lock 闭包；不迁移、不补写也不重新解释
上述历史 root。identity 变化只来自 lock scalar，不是新的 solver 结果。

`PROJECT_LOCK.md` 的该 SHA 是已提交运行门禁，不是 certified source pin；它只定义 W0
research-only 合法版本矩阵与 authority/兼容边界。公共 G3 schema 保持
`research_run_config_v1`、`research_run_receipt_v1`、`artifact_identity_graph_v1`、
`research_artifact_root_manifest_v1` 与 `isolated_python_process_contract_v1`。

## swap v3 的唯一变化轴

profile `d6_6b_d9_6g_swap_v1` 只执行：

- D6 向 D9 转出 `1×6B`；
- D9 向 D6 转出 `1×6G`。

class universe 的固定顺序为
`3I2, 3L, 3O2, 3O3, 5L, 5O2, 6B, 6F, 6G`：

| allocation | 3I2 | 3L | 3O2 | 3O3 | 5L | 5O2 | 6B | 6F | 6G |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D6 before | 0 | 7 | 0 | 3 | 2 | 2 | 1 | 0 | 2 |
| D6 after | 0 | 7 | 0 | 3 | 2 | 2 | 0 | 0 | 3 |
| D9 before | 0 | 18 | 0 | 0 | 3 | 0 | 0 | 0 | 3 |
| D9 after | 0 | 18 | 0 | 0 | 3 | 0 | 1 | 0 | 2 |
| global before | 6 | 109 | 6 | 11 | 32 | 17 | 3 | 3 | 32 |
| global after | 6 | 109 | 6 | 11 | 32 | 17 | 3 | 3 | 32 |

`6B` 与 `6G` 都使用 `manufacturing_6x4` template，均有 1 个 active output，active inputs
分别为 5 与 3。因此派生 totals 同时改变 D6 与 D9：

| allocation | bodies | active inputs before → after | active outputs |
|---|---:|---:|---:|
| D6 | 17 | 25 → 23 | 25 |
| D9 | 24 | 30 → 32 | 24 |

D9 只承担全局 class ledger 的算术补偿，本实验不构建或求解 D9 模型；即使 D6 返回
`INFEASIBLE`，也只能关闭 local D6 swap antecedent，不能把未求解的 D9 升级成全局结论。

除该 class transfer 外，以下全部保持不变：

- domino power cells 仍为 `(1,2)` 与 `(2,2)`，局部范围仍为
  `x=14..41, y=28..41`；
- 两个 2×2 safe pole body anchors 仍为 `(20,34)` 与 `(35,35)`；
- body-only protected rectangle 仍为 anchor `(29,28)`、size `6×7`；
- directed power cycle 仍为 `y=29, x=14..41`、方向 east；
- attachment scope 固定为 `all_legal_d6_slots`，即 cycle 上 `x=14..41` 的 28 个 slots；
- 两个 tile 的 type/size split 仍分别为
  `(5×3x3, 3×5x5, 1×6)` 与 `(5×3x3, 1×5x5, 2×6)`；
- body geometry、domino pairing、tile assignment、mode/front/transport 语义和三份 pinned
  inputs 均不变；
- 原 seed hints bytes 保持不变，只进入 `CpModel.AddHint`，不成为 hard constraints；同模板
  `6B↔6G` 换类不要求改写 hint bytes。

v3 antecedent 必须内含固定 transfer object、D6/D9 before/after 的零补齐 class vectors 以及
global before/after totals。有效 D6 `class_counts` 是 after vector，`expected_totals` 必须独立
复算为 `17 bodies / 23 inputs / 25 outputs`；不得继续硬编码旧的 25-input total。

## 输入与局部联合语义

| 输入 | SHA-256 | 角色 |
|---|---|---|
| `docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json` | `e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c` | strict instance |
| `W0_power_cycle_domino_framework_v1.json` | `db6046cf598f9b5738b7f8950c91ea31834e8214e7e07995175b71eb04bdbb89` | 外部 research framework |
| `W0_geometry_only_seed_v1.json` | `18c72669105f486bf54a2665bd74d1ff952ce2eeb39b28a7b30d5ce8d5d2f5f1` | 外部 geometry warm-start seed |

runner 通过 G3 公共研究合同读取一次实际 bytes、复核期望 SHA-256、复制到独占 run root，再只
消费该快照的内存 bytes。seed 内部
`validation_summary.source_sha256=295bfef9b2681193e3a9cc085c479a960f87de0131abfbdfacb676479bdb2aa5`
未绑定实际 seed bytes，只登记为被拒绝的 producer claim。外部 validation 与 frozen-geometry
front probe 都不是验收 authority；构造器自报不能替代独立 replay。

gate 联合决定 operation class、body anchor、mode、exact active physical ports/fronts、
transport incidence、cycle attachment roles 与两个方向的可达性流。class template 和 I/O
数量从 strict `operation_groups` 推导，mode 与 physical port catalog 从 strict
`facility_templates` 推导。每个 body 必须留在所属 14×14 power cell，彼此不重叠，避开
cycle、pole bodies 与 protected rectangle，并至少有一个 body cell 被固定 pole 覆盖。
active front 按 `anchor + port.body_cell + direction_delta` 独立复算，必须在 domino 内且不被
body 占用。

ground transport 使用 strict routing 的 44 个 directed patterns：12 个 straight/turn、
16 个 splitter、16 个 merger；elevated channel 只有 4 个 directed straight patterns。同一
cell 的双层使用只允许互相垂直的 straight channels，cross 不在同一 cell 内换线；相邻 cell
则按权威 routing incidence 聚合前驱/后继。普通 cycle cell 固定为 `W→E`；output injection
为 `{W,N}→E`；input tap 为 `W→{E,N}`，两类 role 不共用 cell。

`OUT` 极性要求每个 active output 注入 1 单位，由 output-injection slots 吸收总计 25；
`IN` 极性由 input-tap slots 发出总计 23，每个 active input 消耗 1。整数流必须落在所选
directed channel arcs 上。`configuration.json` 携带离散配置和可独立复算的流/可达性证据；
最小 `certificate.json` 只绑定 antecedent/config SHA、status 与 claim boundary。

## Authority 与三态语义

swap v3 的 config、receipt 与 replay 只保留并逐项核对：

```json
{
  "artifact_status": "research_only_local_d6",
  "proves_whole_witness": false,
  "changes_lower_bound": false,
  "changes_upper_bound": false,
  "may_emit_cut_or_rejection": false,
  "production_authority": false,
  "certified_exact_source_authority": false,
  "frozen_or_sealed_input_mutation": false
}
```

已接受的 v2 roots 使用较早但等价的 boundary 字段名；它们不因 v3 命名更新而被改写。

- `FEASIBLE`：只证明 receipt 精确绑定的 local D6 swap antecedent；交付
  `configuration.json` 与最小 `certificate.json` 后停止。
- replay-accepted `INFEASIBLE`：只关闭完全一致的 local D6 swap antecedent；停止，不自动
  进入下一轴或 D7。
- `UNKNOWN`、超时、中断、producer/replay status 分歧、root closure 失败、replay 失败或任一
  运行异常：不产生拒绝、cut、下界或全局结论；停止并只修同一 swap 链。
- intake、hash、项目锁、clean-HEAD 或 antecedent 构造失败发生在 verdict 之前，不是 D6
  verdict。

## No-overwrite root、closure 与 receipt 无自指

producer root 包含快照 inputs、源码副本、canonical `config.json`、完整
`antecedent.json`、`result.json` 与最终 `receipt.json`；仅 `FEASIBLE` 含
`configuration.json` 和 `certificate.json`。run-root 名称由显式 UTC 与 committed HEAD
组成，不由 config/receipt SHA 派生。

manifest 按 path 排序，精确登记除固定终端路径 `receipt.json` 外的全部后代及其类型。
`receipt.json` 是协议保留的唯一额外终端成员，不是 artifact label，不进入 manifest，也不
包含自身 SHA 或 size。写入 receipt 后，producer 与 replayer 都验证
`manifest entries + receipt.json` 恰好等于完整 root；写后 receipt identity 只能出现在
producer stdout summary 或外部 replay receipt。

artifact-root 枚举从可信绝对路径锚点开始，逐组件用 parent descriptor 与
`O_DIRECTORY|O_NOFOLLOW` 打开。root 与每个后代目录的 descriptor 和初始 signature 保留至
完整枚举结束，再逐一 `fstat` 比对后关闭。任何未登记普通文件、目录、symlink、FIFO、
special node、`.pyc`/cache、目录逃逸或枚举漂移都 fail closed。producer、pinned gate 和
pinned replayer 都必须在可验证的 `-I -B` 进程合同下运行，不得在正式 root 内生成
bytecode/cache。

W0 D6 artifact labels 到 root-relative paths 的映射固定如下，不能同步重写 identities 和
manifest 后整体改名：

| artifact label | 固定 root-relative path | 存在条件 |
|---|---|---|
| `config` | `config.json` | 全部 status |
| `antecedent` | `antecedent.json` | 全部 status |
| `result` | `result.json` | 全部 status |
| `inputs.strict_instance` | `inputs/strict_instance.json` | 全部 status |
| `inputs.framework` | `inputs/framework.json` | 全部 status |
| `inputs.seed` | `inputs/seed.json` | 全部 status |
| `sources.runner` | `sources/run_d6_research.py` | 全部 status |
| `sources.gate` | `sources/d6_joint_completion_gate.py` | 全部 status |
| `sources.replayer` | `sources/replay_d6_certificate.py` | 全部 status |
| `sources.common_contract` | `sources/research_run_contract.py` | 全部 status |
| `configuration` | `configuration.json` | 仅 `FEASIBLE` |
| `certificate` | `certificate.json` | 仅 `FEASIBLE` |

replayer 是 stdlib-only、solver-free 的自包含实现，不导入 gate、runner、G3、`src/` 或
OR-Tools。它在解释 status 前和返回前都验证完整 root、固定 path map、命名字节图与 semantic
cross-bindings。`INFEASIBLE`/`UNKNOWN` 不得携带 configuration/certificate；只有
`FEASIBLE` 执行 body/front/incidence/crossing、cycle role、flow 与 graph reachability 的
完整语义复算。

## 正式运行命令（本轮已执行配方）

必须从首个实施提交后的 clean committed HEAD 执行，固定 cohort/profile/scope。命令中的
`{UTC}` 与 `{HEAD12}` 必须先替换为实际 UTC run timestamp 和该 committed HEAD 的前 12 位：

```bash
D6_PYTHON=.venv-uvbolt-backup/bin/python3.13
"$D6_PYTHON" -I -B docs/research/w0_power_cycle_domino_d6_20260728/run_d6_research.py \
  --strict docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json \
  --framework /home/zhuran24/下载/w0回复/1/W0_power_cycle_domino_framework_v1.json \
  --seed /home/zhuran24/下载/w0回复/1/W0_geometry_only_seed_v1.json \
  --protocol-cohort w0_d6_swap_v3 \
  --class-allocation-profile d6_6b_d9_6g_swap_v1 \
  --attachment-scope all_legal_d6_slots \
  --run-root ".artifacts/research_runs/w0-d6-6b-d9-6g-swap-v3-{UTC}-{HEAD12}" \
  --workers 2 \
  --random-seed 0 \
  --max-time-seconds 3600
```

两份 replay 都必须使用 producer root 内 pinned v3 replayer，并写到 producer root 外的两个
新 no-overwrite locations：

```bash
D6_RUN_ROOT="$(realpath '.artifacts/research_runs/w0-d6-6b-d9-6g-swap-v3-{UTC}-{HEAD12}')"
D6_REPLAY_SIBLING="${D6_RUN_ROOT}-replay"
mkdir "$D6_REPLAY_SIBLING"
"$D6_PYTHON" -I -B "$D6_RUN_ROOT/sources/replay_d6_certificate.py" \
  --run-root "$D6_RUN_ROOT" \
  --output "$D6_REPLAY_SIBLING/replay_receipt.json"

D6_TMP_REPLAY="$(mktemp -d /tmp/w0-d6-swap-replay.XXXXXX)"
(
  cd "$D6_TMP_REPLAY"
  /usr/bin/python3 -I -B "$D6_RUN_ROOT/sources/replay_d6_certificate.py" \
    --run-root "$D6_RUN_ROOT" \
    --output "$D6_TMP_REPLAY/replay_receipt.json"
)
cmp "$D6_REPLAY_SIBLING/replay_receipt.json" "$D6_TMP_REPLAY/replay_receipt.json"
```

## 资源门禁与强制执行顺序（本轮已完成）

正式 run 前与 full preflight 后使用同一组可判定门禁。三把锁必须以 descriptor-relative、
no-follow、nonblocking 方式获取并持有到 producer 和两份 replay 全部结束：

- `/tmp/zmd-pj-codex-heavy-validation.lock`
- `/run/user/<uid>/zmd_pj_prod_scale_solver.lock`
- `/run/user/<uid>/zmd-pj-prod-scale-solve.lock`

每次门禁都必须同时满足：

- `/proc/meminfo` 的 `MemAvailable >= 24 * 2^30` bytes；
- `SwapFree >= 16 * 2^30` bytes；
- repo/artifact filesystem 与 `/tmp` 各自可用空间 `>= 16 * 2^30` bytes；
- `/proc/pressure/memory` 与 `/proc/pressure/io` 可严格解析；间隔 10 秒的两次读数中，
  两者的 `full avg10` 均为 `0.00`，并记录 `some` 指标；
- 没有同 UID、非当前祖先进程的 `Endfield.exe`、`PlatformProcess.exe` 或相关游戏 workload，
  也没有竞争 D6/CP-SAT/AB16/organic solver、preflight 或 pytest；
- 三把锁均由当前执行链持有，且没有相关 active systemd unit；
- `git status` clean、HEAD 已提交且与运行身份一致；
- `PROJECT_LOCK.md` SHA-256 为
  `e7a43fe0509fe853b18e487d36d230b14a0ba856f0f6c745ac33fd7346ac71b7`；
- strict/framework/seed 三份实际 bytes 分别匹配本页固定 SHA。

强制顺序为：

1. 首个实施提交完成全部 solver-free focused、Ruff、定向 mypy、asset/boundary/governance
   检查，确认 clean committed HEAD；
2. 获取并持有三把锁，执行第一次完整资源/竞争进程/项目锁/HEAD/pinned-input 门禁；
3. 运行 `python scripts/preflight_gate.py --full`；任何失败都只修同一链，不启动实验；
4. full preflight 通过后执行完全相同的第二次门禁；
5. 在新的 no-overwrite producer root 上只运行一次上述 swap v3；
6. 先用 coherent CPython 3.13，再从 fresh `/tmp` 用 `/usr/bin/python3 -I -B` 执行两份
   root-pinned replay；两份 canonical replay bytes 和 SHA-256 必须一致；
7. 按上一节三态规则停止，不自动放宽到另一轴或 D7。

H20 row-power oracle、G4 巨型核心拆分、D7、full-graph solve、production 控制流、多轴联合放宽
和 lower-ledger 更新都不在本任务范围。
