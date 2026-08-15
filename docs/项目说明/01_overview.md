# 01 — 项目概览与认证命题

> 本页只定义稳定的问题外延、`CERTIFIED` 命题与认证链职责，不保存 gate、hash、
> 阶段进度、研究上下界或实验计数。当前取值见 [`../CURRENT.md`](../CURRENT.md)，
> 稳定 claim、decision 与证据见 [`../CATALOG.md`](../CATALOG.md)。知识脊柱启用前的
> 原文保存在
> [`../history/status/01_overview_pre_knowledge_spine_20260811.md`](../history/status/01_overview_pre_knowledge_spine_20260811.md)。

## 1.1 形式问题与六个 gating 谓词

令 `G` 为 canonical rules 定义的网格，`I` 为 mandatory exact instance 集合。对每个
`i ∈ I`，从同一冻结输入闭包给出的候选 pose 中选择 `π(i)`；同时选择满足 canonical
admissibility 的轴向矩形 `R ⊆ G`。一个候选只有同时满足以下六个谓词才是整例可行：

1. **设施空地**：每个已选 pose 的 `occupied_cells` 与 `R` 不相交；
2. **设施不重叠**：不同 instance 的 `occupied_cells` 两两不相交；
3. **放置规则**：每个 instance 的 canonical `placement_rule` 成立；
4. **端口绑定**：binding 可行，且 generic slot 的 exact-count 与 provider-instance 约束成立；
5. **精确路由**：所有 required commodity 的 source/sink front 在离散网格中满足有向连通，
   且被接受的 route cells 不占用 `R`；
6. **供电覆盖**：由真实已选供电设施按 canonical coverage 语义覆盖所有受电设施。

“空矩形”是谓词 1 与谓词 5 的联合条件：既不能有设施机身，也不能有已接受路由占用。
精确 objective、网格尺寸、mandatory 数量、minimum-side floor、coverage 与 emptiness 的当前
机器值只读 `rules/canonical_rules.json`、`data/preprocessed/mandatory_exact_instances.json`
及其 [`../CURRENT.md`](../CURRENT.md) 投影。

## 1.2 `CERTIFIED` 精确证明什么

只有同一冻结输入闭包上的候选通过终端证据复验、fixed-witness verification、
`ExactCampaign.supervisor_seal()` 与 canonical publisher 的 fail-closed 检查后，公开交付面
才可携带 proof-bearing `CERTIFIED`。该标签只证明：

1. 发布的确切 `(R*, π*)` 满足 §1.1 的六个谓词；
2. 完整 admissible candidate frontier 中不存在 objective 上严格更优的可行解；
3. solution、blueprint、manifest 与 terminal evidence 来自同一 disk-current supervisor seal。

它不证明离散吞吐、单位时间产率、带宽、电网吞吐、未列入六谓词的游戏机制，或任何独立
研究账本中的可达性。超时、资源耗尽、证据缺失、worker 失败或 verifier `UNKNOWN` 只能产生
`UNKNOWN` / `UNPROVEN`，不能改写为 `INFEASIBLE` 或 `CERTIFIED`。

`src/models/flow_subproblem.py` 是诊断性连续 LP；它不在 certified acceptance 的必经链上，
也不能单独生成 proof-bearing elimination。

## 1.3 Soundness 与 authority 链

```text
canonical rules + frozen exact inputs
  -> placement master
  -> binding
  -> exact routing + power + terminal whole-layout checks
  -> producer proposal: CANDIDATE_PROPOSED
  -> independent supervisor seal
  -> owner-controlled publish gate
  -> canonical transactional publisher
  -> public certified surface
```

各层职责不可互相替代：

- producer 可以提交 proposal 与 replay material，但不能铸造 durable/public `CERTIFIED`；
- proof-bearing whole-layout elimination 必须经过独立重算，generator 自报失败不够；
- supervisor 必须从 canonical disk authority 重读并验证 proposal、frontier 与 fixed witness；
- owner gate 只能由机器 gate 中登记的显式 owner 决定改变，测试、receipt、seal、Markdown 或
  checker 绿灯不能代替该决定；
- public writer 只能是 `publish_verified_certified_delivery_surface()`，派生 serializer、viewer、
  report、adapter 与 compatibility export 没有认证 authority。

## 1.4 研究、production 与发布边界

研究 claim、cut-family 生命周期、production attach 安全性和 P2.0 吞吐账本各有独立作用域。
它们是否当前有效、是否获 authority、是否 superseded，以及直接后果和明确不推出的内容，
统一登记在 [`../CATALOG.md`](../CATALOG.md)。任何单次实验、内部 solver verdict、paper proof
或历史文档都不能凭文件名自行升级为 production theorem、研究账本更新或公开认证。

## 1.5 查询入口

- 当前 gate、冻结规则摘要、checked-in exact 状态与精选承重 claim：
  [`../CURRENT.md`](../CURRENT.md)
- claim、decision、dossier、supersede 与证据反向索引：
  [`../CATALOG.md`](../CATALOG.md)
- 机器真源：`rules/canonical_rules.json`、`data/proof_obligations/`、
  `data/review_gates/phase_1_2_spike_close.json`、`data/solutions/exact_full_scale_status.json`
- 任务式文档入口：[`../START_HERE.md`](../START_HERE.md)
