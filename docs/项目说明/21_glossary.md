# 21 — 当前术语表

> 当前 authority 与状态以 `PROJECT_LOCK.md`、`06_current_status.md` 和机器 gate 为准。
> 历史研究术语可在 `docs/research/` 查阅，但不能覆盖下列发布语义。

## 认证与发布

- **candidate verdict / `RUN_STATUS_CERTIFIED`**：单个候选在 benders 求解层通过当前声明检查的
  内部结果。不是 durable campaign `CERTIFIED`，也不是 public certification。
- **producer**：`outer_search`。记录候选并在 strict frontier exhaustion 后提交 proposal。
- **`CANDIDATE_PROPOSED`**：待 supervisor 审核的 terminal proposal 状态，明确不是认证终态。
- **supervisor seal**：`ExactCampaign.supervisor_seal()` 从 canonical disk authority 重读并复验
  proposal 后，唯一可以铸造 durable terminal `CERTIFIED` 的路径；独立 production CLI 为 `scripts/run_supervisor_seal.py`，普通 solver run 仍不自动调用。
- **fixed witness**：为 terminal result 固定、序列化并可独立复验的 witness material；防止
  producer/consumer 对“同一结果”使用不同对象或解释。
- **terminal frontier evidence**：strict candidate frontier 已穷尽且最终候选与记录绑定的证据。
- **public certified surface**：sealed campaign、`final_solution.json`、`optimal_blueprint.json`、
  manifest、当前 hashes 与 publish gate 共同组成的 fail-closed surface。
- **central verified publisher**：`publish_verified_certified_delivery_surface()`，唯一 canonical
  public writer；失败清理三件套。
- **OPEN-GATE / publish-open gate**：owner 控制的 P1.2 发布闸。当前实现已存在，且已于
  2026-07-07 owner-closed；“gate implemented”不等于“gate closed”，本次 closed 只认
  `owner_manual_decision`，不得从测试、receipt、seal 或 checker 绿灯自动推导。
- **P1.2 CLOSED**：技术 close、要求验证、包材边界和 owner gate 同时满足。当前已成立
  （2026-07-07 `owner_manual_decision`）。

## 求解层

- **master**：placement 与 ghost rectangle 主问题。
- **binding**：端口/slot 绑定子问题。
- **routing**：离散网格 routing 子问题，并含 selected-graph connectivity acceptance guard。
- **flow diagnostic**：`src/models/flow_subproblem.py` 的连续多商品流 LP。仅诊断，不门控
  certified verdict，不产生 proof-bearing Farkas/min-cut cut。
- **power / whole-layout checks**：候选与 terminal evidence 中的电力和全布局复验边界。
- **independent infeasibility reverify**：对 whole-layout proof-bearing elimination 的独立重算；
  generator 的失败声明本身不够。
- **ghost rectangle**：目标空矩形，objective 为 `max_lex(area, min_side)`；`min_side >= 6` 是
  default admissibility，不是替代 objective。
- **pose**：facility instance 的候选位置、朝向、port mode 与 occupied cells。

## 数据与状态

- **canonical rules**：`rules/canonical_rules.json` 的 owner-reviewed 语义真源。
- **preprocess plan**：`rules/preprocess_plan.json`，既参与 regeneration，也被当前 runtime/hash
  closure 消费。
- **candidate placements**：当前工作树中存在的 45,774,305-byte hash-bound pose artifact；拐角修复前的 45,773,799-byte / SHA256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0` 版本已 superseded，且 hash-incompatible。
- **campaign resume compatibility**：checkpoint 与当前规则、artifact 和 proof-bearing source
  closure 一致；不一致必须 reset/新建证据链。
- **compatibility export / viewer / adapter output**：派生消费面。即使文件名或字段看起来像
  canonical artifact，也没有自行认证 authority。

## Controls

- **proof obligation**：把声明、关键 source/sink、测试与 hash 绑定的结构契约。PASS 不等于
  full-project proof 或 owner close。
- **strong-status allowlist**：deny-by-default 的扫描登记与理由。allowlisted 只表示该写入点的
 角色被显式审计，不表示它可绕过 supervisor/publisher。
- **close-kernel**：P1.2 结构 gate、关键文件与解释器/OS 等命名 TCB 的集合。
- **PR1**：当前工作树已落的 producer/supervisor split、fixed-witness、independent reverify、
  publish gate 与 central publisher hardening。
- **PR2**：仍开放的更小 controlled-loader/read-once verifier TCB 工作。
- **P1.3**：面向人的当前实施阶段，涵盖 cut-family attach、Stage B/PIC 与最终 promotion。机器 JSON 中
  保留的 `p1_3b_*` 是兼容字段，不应继续扩散成人类状态名。

## Cut framework

- **active cut families**：当前为 F1-F7+F9；F8 因游戏规则前提为假于 2026-07-08 退役。F1/F5/F6/F7 direct Step-8 已实现，但 bridge 仍 unsafe/default-off，尚未成为默认 certified path。
- **validator trust boundary**：对 cut certificate 做 fail-closed 重算的边界。实现存在不自动
  意味着该 family 已进入 production theorem。
- **held / active / quarantined**：cut lifecycle 状态；应按实际 lifecycle 与 phase scope解读。
- **GHOST_AGNOSTIC / source digest / replay**：cut scope/currentness 机制，不能替代 campaign
  supervisor 或 public publisher 的 currentness contract。

## 测试词

- **collected**：pytest 发现了测试，不表示测试执行通过。
- **passed**：指定命令在指定工作树退出 0。必须附命令/日志，不能复用历史计数。
- **targeted suite**：只覆盖列明模块的局部测试，不可描述为 full suite。
