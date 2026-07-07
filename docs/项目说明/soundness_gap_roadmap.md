# Certified soundness 状态矩阵

**基线：当前工作树，2026-06-26。**  
状态词只描述实现与证据，不替代 owner release gate。`IMPLEMENTED` 不等于 P1.2 CLOSED。

| ID | 当前状态 | 代码证据 | 仍需注意 |
|---|---|---|---|
| WS / fixed-witness identity | **IMPLEMENTED** | `terminal_fixed_witness_capsule.py`; `terminal_fixed_witness_verifier.py`; `exact_campaign.py:3399-3593` | verifier/解释器/OS 仍是命名 TCB；PR2 仍要收缩 loader/snapshot TCB |
| OPEN-GATE | **IMPLEMENTED, gate OWNER-CLOSED** | `certified_surface.py:482-531`; `phase_1_2_spike_close.json` | 2026-07-07 owner 显式 `owner_manual_decision` 已关闭 P1.2（`status=closed_manual_owner_decision`，`p1_3b_entry_allowed=true`）；public publish 不再因 owner gate 本身拒绝，但仍只能走 central publisher / supervisor seal，且不得从测试、receipt、seal 或 checker 绿灯自动推导 closed/released |
| producer/supervisor mint split | **IMPLEMENTED** | `outer_search.py:855-954`; `exact_campaign.py:3399-3593` | producer 内部 candidate verdict 不能被误写成 durable/public CERTIFIED |
| supervisor operational wiring | **IMPLEMENTED**（2026-07-04） | `scripts/run_supervisor_seal.py`（`349c56c`，独立命令、从 proposal-ready marker 驱动）；`main.py` 仍只返回 proposal | 入口存在只满足一条机器条件，不等于 P1.2 closed / 端到端发布流程；尚无真实生产 campaign→seal 实跑记录 |
| central public publisher | **IMPLEMENTED** | `certified_surface.py:563-680` | generic writer、viewer/report、adapter、compat export 均非认证 authority |
| I1 whole-layout independent reverify | **IMPLEMENTED** | `benders_loop.py:7538-7585`; `independent_infeasibility_reverifier.py` | 只覆盖登记的 whole-layout nogood 路径，不自动证明未来 cut family。I1 重建的 binding 子问题与生产侧共读 `EXACT_BINDING_USE_OVERLOAD_SEPARATION`——此项为 **guarded、非 live**：该 env 不在 certified operational allowlist，certified 入口（`benders_loop.py` 闭合白名单守卫）对其开启 fail-closed 拒绝，故 certified 运行中 I1 不可能被该 env 污染；该深度防御缺口已补齐（`a731764`：`PortBindingModel.build()` 加 `use_overload_separation` 参数，I1 复验调用点显式传 `False`，不再依赖 env 守卫层） |
| connector cell body exclusion | **IMPLEMENTED at terminal fixed-witness boundary** | `terminal_fixed_witness_verifier.py:863-866`; fixed-witness tests | solve-time 更早拒绝仍可作为性能/纵深增强，但 public false-CERTIFIED 路径已被终端闸拦截 |
| PYC execution/source binding | **IMPLEMENTED** | isolated replay/capsule 使用 `-B -X pycache_prefix=<fresh>`；obligation `PO-ISOLATED-EXEC-BYTECODE-BINDING` | Python、stdlib、OR-Tools native extension、父 relay、OS 隔离仍是命名 TCB |
| proof obligation close-kernel | **IMPLEMENTED structural gate** | 14 active obligations；checker + sink hashes/guards/allowlist | PASS 只表示登记结构一致，不证明 owner 已 close 或 full suite 已过 |
| PR2 small/read-once verifier TCB | **OPEN** | 设计文档有目标，当前无完整 controlled-loader/read-once implementation | 该硬化桶仍 OPEN，但已由 owner 裁定延期到发布时点，非 P1.2 close 前提；#9a 属部署时点任务 |
| immutable review snapshot | **IMPLEMENTED** | `package_review_snapshot.py` 的 `build_package()` 将 treeish 一次 resolve 为 immutable commit，provenance/manifest/`_materialize_tree` 三处统一用该 resolved commit；回归测试 `test_package_review_snapshot_ref_move_after_resolve_keeps_packaged_commit` 钉住 ref-move TOCTOU 场景 | archive policy 覆盖完整性另见下一行（仍 PARTIAL）；IMPLEMENTED ≠ P1.2 CLOSED |
| archive policy completeness | **PARTIAL（主缺口已收窄）** | 已过滤 prompt、旧包、嵌套 archive、`.artifacts`/packet 等；**协作记忆子系统 `cc_memory/` + `cc_memory_vnext/` 已补入排除表并加回归（`28d9d2c`：与已排除的 `.claude/`/`.codex/`/`_cc_live_memory/`/`cc_context/` 同类补全；真树 77 路径全 excluded）** | 主泄漏面（owner 私下裁定 / 内部 gap 地图经 memory 子系统外泄）已堵；残余留冻结那轮 owner 拍板：`paths/` 探索 probe 与 `.githooks` 去留、secret-scan 类内容面（`28d9d2c` 后已只读扫描 tracked 树、无私钥/AWS/token/赋值型密钥暴露→加扫描器属纵深防御非现洞）、把这次新覆盖再 obligation-anchor（现走已锚定测试断言体、未新增 obligation 名） |
| boundary-placement independent rederive | **OPEN/PARTIAL** | generation-time guard + pinned artifact + 封印期字节重推 gate（`16495f4`，child 无条件、同生成器重推全 pools 断言 sha==被钉字节） | 统一 terminal 字节重推已补；独立重实现 / 移出证明权威（Option B）属发布时点延期桶，非 P1.2 close 前提 |
| canonical→geometry shared primitives | **骑墙：字节半 P1.2 已落 / 语义半 P1.3** | **P1.2 相关半**：字节级 canonical→geometry 已由重推 gate 交叉验证（`16495f4`，candidate_placements 字节须等于 canonical 重推），属当前证明面。**P1.3 相关半**：F1-F9 cut helpers 各用旧欧氏覆盖/方向模型、未与 live master 语义统一 | 语义统一在 F1-F9 真接入 certified master（`src/cuts/lifecycle.py` `step_8` 仍 NotImplementedError=P1.3 主体）**之前不可测/不可做**，故是 **P1.3-before-F1-F9 前置、非 P1.2 外审前 blocker**（定位辨析见卡 `p1-2-pre-external-review-open-items`） |
| discrete throughput / belt bandwidth | **OUT OF SCOPE BY DESIGN** | `flow_subproblem.py` diagnostic-only；benders 不以 flow verdict gate | 不是“待补一条测试”的 gap；若要纳入需改变 theorem scope 和新 proof paradigm |
| P1.2 owner gate | **CLOSED（owner 2026-07-07）** | `status=closed_manual_owner_decision`, `p1_3b_entry_allowed=true`（P1.3 已开放） | owner 显式 owner_manual_decision 已关闭 P1.2、开启 P1.3;三轮收口外审(权限/语义/TCB线)0 上-TCB 洞;stay-blocked sentinel 按设计撤除(fixed-witness binding 保留)、已 reseal;此关闭是 owner 手动决定非自动推导 |

## 发布闭合条件

P1.2 只有在以下条件同时成立时才能改写为 closed：

1. producer 只提交 proposal，并存在受支持、可审计的独立 supervisor invocation surface；public publisher 保持单入口；
2. fixed-witness、sink replay、terminal evidence 和 disk-current checks 全部 fail-closed；
3. P1.2 publish gate 明确 owner-closed；
4. PR2 TCB、snapshot immutability 和 archive policy 未决项完成并有红测；（owner 2026-07-06：其中「仅防蓄意内鬼」的 PR2 TCB 硬化——#8 深化/#3/#9b/#9c/#5-F/Option B/#2——已移至**发布时点、非 P1.2 close 前提**，见卡 `deliberate-insider-hardening-deferred-to-release`；此处 PR2 TCB 未决项不再含它们，snapshot immutability/archive policy 等常开项照旧。）
5. close-kernel checker、targeted soundness tests 和要求的 full gate 在同一工作树通过；
6. owner 显式关闭 manual gate。

以上闭合条件已于 **2026-07-07 全部满足**（三轮收口外审 0 上-TCB 洞、close-kernel checker + full + slow gate 同树通过、owner 显式 owner_manual_decision 关闭 manual gate）；**P1.2 已 CLOSED，P1.3 已开放**。历史上"不得从测试/receipt/seal 自动推导闭合"的纪律仍成立——本次是 owner 显式手动决定,非自动推导。

## 历史映射

旧文中的 P1.2-FIX-1/2/4 大致对应 WS、OPEN-GATE、I1，当前已实现；FIX-3/5 的部分 capsule/TOCTOU
加固已落地，但不能被扩张成 PR2 全部完成。旧的人类名 `P1.3B` 现在统一称 P1.3；机器字段保持兼容。
