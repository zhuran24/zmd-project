# W0 一元 lowering 金丝雀协议 v1

> **状态：** `FROZEN_PRE_IMPLEMENTATION`
> **日期：** 2026-08-16
> **性质：** `research_only / non_authorizing`
> **授权坐标：** [`00_OWNER_AUTHORIZATION_20260816.md`](00_OWNER_AUTHORIZATION_20260816.md)；执行边界投影见 [`00_OWNER_SIGNAL_AND_BOUNDARY.md`](00_OWNER_SIGNAL_AND_BOUNDARY.md)。
> **对象：** `J-W0-GHOST-FRONT-BOUNDARY-041-V1`
> **协议冻结纪律：** 本文件进入独立提交后，implementation 与 run 不得原地修改本协议；偏差必须记 `PROTOCOL_VIOLATION`，不能追写协议迁就结果。

## 1. 实验问题

本实验只回答：

> 一个已经由独立 checker 证明的 W0 单原子 Judgment，能否被精确编译为 PortBindingModel 中的一元约束，在真实 binding→routing 路径前消灭其授权拒绝的全部观测循环，同时不扩大拒绝集合，并把后续热点与端到端代价完整记账？

它不检验跨布局普遍性，不检验通用 theorem compiler，也不要求终点上下界移动。

## 2. 钉死对象与输入

运行前必须核验以下 SHA-256；任一不符即 `INPUT_IDENTITY_MISMATCH`：

| 角色 | 路径 | SHA-256 |
|---|---|---|
| Judgment | `experiment_one_w0_ghost_front_offline_certificate_20260815/01_JUDGMENT.json` | `853c7aa9df3939e8eea97afebbf34c4c453a8e641d186ec75af82af291d0ebc3` |
| 证明正文 | `experiment_one_w0_ghost_front_offline_certificate_20260815/02_PROOF.md` | `2d8c5d608bdcf9c2ad80ba5561591d17679db52203a11cddbc76ab48486fedfb` |
| 独立 checker | `experiment_one_w0_ghost_front_offline_certificate_20260815/03_check_w0_ghost_front_certificate.py` | `c53e882ab7b2d6bfa96dacefd510ae708f926116475cb0d74aa18d3d40591ba7` |
| Phase -1 corpus | `phase_minus1/corpus_manifest.json` | `8f7e33ffb477ebea7152f3163b7754eddcc64596fe67949b6f5bdfde8061de91` |
| 输入适配 harness | `phase_minus1/phase_minus1_harness.py` | `81e8960738ba2c0b81f86cefb96bc87da9b2e2f81ac9073e2135192b7fb905c2` |
| 签名压缩 helper | `phase_minus1/phase_minus1_harness_r3.py` | `8aafe4016bd89649f31d466abab7edbd0f3fbe19c2beacfb4da29a6506221e28` |
| binding model | `src/models/binding_subproblem.py` | `1c89f6ee2cb958568c7365289a0b3d6e69a32f3162d4c925f02695705efc7ee9` |
| routing model | `src/models/routing_subproblem.py` | `7554b0f24176b86104095ee47b8ec8ed5dfc4098c3df2f661231b0cf2f0ae718` |
| canonical rules | `rules/canonical_rules.json` | `c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0` |
| candidate pool | `data/preprocessed/candidate_placements.json` | `f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3` |
| mandatory instances | `data/preprocessed/mandatory_exact_instances.json` | `545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6` |
| generic I/O | `data/preprocessed/generic_io_requirements.json` | `ad5125b50e607a7f3f3bf0b54fea64f93edf87cedb62e8d24f5590e1c895c44e` |
| W0 raw layout | `.artifacts/w0_fixrerun_20260804/band22_alignment/registration_placement_solution.json` | `db85d3e18fd0fc12ba743e0fd86e38183262a24c90d28805634c952cf27103c7` |
| W0 rectangle | `.artifacts/w0_fixrerun_20260804/band22_alignment/max_empty_rect_for_this_placement.json` | `aeb3a046a23309db845c238372d3b0a8e442c2ac7c94eb9de18ab0f1d9420fc6` |

固定 normalized layout SHA-256 为 `d199c88e6d65582a269ec5142b33e3d9db9294eeb0b1a25f9ee05005ff1a26aa`。

运行每个 arm 前必须先以 `--coverage off` 执行 W0 独立 checker；不是 `PASS` 则该 arm 不启动。

## 3. lowering 合同

Theorem trigger：

```text
active_output_slot(binding_selection, boundary_port_041, 0)
```

现有 binding model 将该物理 slot 表示为：

```text
slot_id = boundary_port_041:out:0
ExactlyOne(required-output commodities ∪ {__unused__})
```

Treatment 只允许增加一条一元约束：

```text
boundary_port_041:out:0 == __unused__
```

等价表示为对应 `__unused__` BoolVar 等于 1。禁止添加其他约束、改变搜索策略、改变 required counts、预删其他 slot、复用 routing 观测结果或注入 selection hash 黑名单。

安全合同为：

\[
\operatorname{RejectSet}(L_J,c)
\subseteq
\operatorname{AuthorizedRejectSet}(J,c).
\]

本对象要求更强的精确等值：lowering 只拒绝且拒绝全部 `Active_041` selection。implementation 必须比较 baseline 与 treatment CpModel proto，证明除一条目标 unary constraint 外无其他结构差异；变量、原有约束、search strategy 与 objective 必须逐字节等值。

## 4. 三臂

每个 arm 在独立 Python 进程中从相同字节重新 build 模型。

| arm | 动作 | 用途 |
|---|---|---|
| `A_BASELINE` | 不求值 theorem trigger，不加约束；保留共同事件计量 | 当前真实循环基线 |
| `B_OBSERVER_NOOP` | 每份 selection 便宜求值 `Active_041`，但不加约束 | 隔离 trigger／receipt 观测成本 |
| `C_UNARY_LOWERING` | 与 B 相同，并在第一次 solve 前加唯一 unary constraint | 测定理真实消费与成本迁移 |

运行顺序冻结为 `A_BASELINE → B_OBSERVER_NOOP → C_UNARY_LOWERING`。单次序列不提供统计显著性；墙钟只作描述性资源账，确定性结构计数与 proto 合同是主判据。

## 5. 运行预算与共同设置

- layout：`W0-ALIGNMENT`；
- event cap：`1007` 份 FEASIBLE binding proposals；
- 每 arm 端到端 watchdog：`900 s`；
- 单次 binding solve cap：`20 s`；
- 单次 routing solve cap：`30 s`；
- binding workers：`1`；routing workers：`1`；
- alternative cap：无；
- overload separation：强制 `False`；
- 任何已登记的 unsafe／exploratory env override：必须为空；
- full event journals 留 `.artifacts/solver_reasoning_outer_loop_w0_unary_canary_20260816/`；tracked 只保留 compact summary、hash 与判读。

每份 FEASIBLE selection 依次：提取 selection → 可选 trigger 求值 → exact routing precheck 双重 replay → precheck 拒绝则加现有完整 selection point nogood 继续；precheck 放行则 build 并 solve routing。Treatment 不取消下游精确本体与 point-nogood fallback。

## 6. 冻结观测量

### 6.1 切面语义

- `distinct_selection_count`；
- `j_trigger_true_count`；
- `j_trigger_false_count`；
- `boundary_port_041_active_port_spec_count`；
- precheck status 与 local-signature 分布；
- point nogood 数及 literal 总数；
- first non-J event index；
- first routing-build／routing-solve milestone；
- terminal 与 censor status。

### 6.2 残余 envelope

在 model build 后、第一次 solve 前记录：

- proto variable count；
- proto constraint count；
- generic output slot count；
- target slot domain labels；
- target slot可选值数；
- treatment 新增 constraint 数；
- 目标 unary constraint 的 proto canonical hash。

这些是 `MODEL_SIZE`／`BOX_DOMAIN` 指标，不冒充联合可行 binding 数。

### 6.3 资源轨迹

- binding build／solve；
- routing precheck／build／solve；
- trigger evaluator；
- theorem checker；
- journal；
- total wall、process CPU、peak RSS；
- 各 stage 占总成本比例。

热点迁移本身不判失败。未被观测的迁移、或终点中性情况下超过冻结容差的净成本回归才判负。

### 6.4 终点行

概念与公式由 [`02_ENDPOINT_METRICS_PROTOCOL_V1.md`](02_ENDPOINT_METRICS_PROTOCOL_V1.md) 定义；本 canary 的机器身份、当前账本 hashes 与合成扰动向量由 [`02_ENDPOINT_METRICS_PROTOCOL_V1.json`](02_ENDPOINT_METRICS_PROTOCOL_V1.json) 冻结。W0 Judgment 不产生完整 witness，也不产生 rectangle-level 全称排除；因此预注册预期为：

```text
ΔL = ZERO_BY_SCOPE
ΔU = ZERO_BY_SCOPE
ΔM = N/A_LOWER_BOUND_ABSENT, delta ZERO_BY_SCOPE
```

必须同时核验 tracked exact-status、research ledger source 与所有认证／发布表面在运行前后哈希不变。该终点中性只能写“编译与测量基建”，不得写成全局 exact 进展。

## 7. 判词

### `CANARY_PASS_LOCAL_CONSUMPTION`

必须全部成立：

1. W0 independent checker 在三个 arm 前均 `PASS`；
2. proto diff 证明 treatment 只增加目标 unary constraint，且拒绝集合与 theorem trigger 等值；
3. A 与 B 都在 event cap 内得到 `1007` 个不同 selection，且 `j_trigger_true_count=1007`；
4. C 达到 terminal 或 `1007` proposals，且 `j_trigger_true_count=0`、目标活动 port spec 数为 0；
5. A/B 的一号家族观测与 frozen prefix 不发生承重身份冲突；
6. 无误杀证据、无输入漂移、无协议偏差；
7. 终点表面全部哈希不变，终点行按 `ZERO_BY_SCOPE` 报告；
8. B 相对 A 的共同里程碑墙钟回归不超过 `15%`；C 相对 B 的共同里程碑墙钟回归不超过 `25%`，或 C 获得更强 terminal milestone。

该 PASS 只表示“一条已证 theorem 在固定 W0 上被正确编译并产生因果局部效果”。

### `LOCAL_EFFECT_WITH_COST_REGRESSION`

1–7 成立，但 C 的共同里程碑端到端成本回归超过 25%，且未获得更强 terminal milestone。它证明编译闭环成立，但不购买扩线。

### `LOWERING_UNSOUND_OR_OVERREACH`

proto diff、trigger 等值、context、输入身份或零越权任一失败。立即停止，不得用性能结果抵消。

### `NO_LOCAL_EFFECT`

lowering sound，但 C 仍出现任一 `Active_041` selection，或未消灭目标 port spec。说明 consumer 接线未生效。

### `INCONCLUSIVE`

A/B 未达到 1007、arm watchdog／solver timeout、运行环境污染、日志损坏或不同 arm 无共同可比 milestone。不得改写为通过或失败。

## 8. 决策敏感性

- `CANARY_PASS_LOCAL_CONSUMPTION`：允许提交 owner 考虑下一件已证 theorem 或更窄 family canary；不自动打开通用 D3/D4。
- `LOCAL_EFFECT_WITH_COST_REGRESSION`：保留 lowering 成品，停止扩线，先处理住址／表示／成本迁移。
- `LOWERING_UNSOUND_OR_OVERREACH`：退回器官⑤设计，不运行后续 treatment。
- `NO_LOCAL_EFFECT`：退回 consumer 接线与变量 grounding。
- `INCONCLUSIVE`：只允许修实验装置或缩小可比里程碑，不升级架构判词。

不同结果对应不同动作，因此本实验不是为展示“定理有用”而强行接线。

## 9. 禁止事项

- 修改本协议迁就数据；
- 修改 tracked `src/` 或 certified source；
- 启用通用 D3/D4；
- 把 treatment 约束写入生产默认路径；
- 把点状 fallback 的存在写成 family compiler 普遍成立；
- 用 1007 frozen observations 当 theorem 前提；
- 把 `NOT_REACHED` 记录为 0；
- 把终点中性写成 bounds 进展；
- 运行 preflight、supervisor、publisher 或任何认证 mint。
