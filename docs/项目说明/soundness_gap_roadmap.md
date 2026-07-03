# Certified soundness 状态矩阵

**基线：当前工作树，2026-06-26。**  
状态词只描述实现与证据，不替代 owner release gate。`IMPLEMENTED` 不等于 P1.2 CLOSED。

| ID | 当前状态 | 代码证据 | 仍需注意 |
|---|---|---|---|
| WS / fixed-witness identity | **IMPLEMENTED** | `terminal_fixed_witness_capsule.py`; `terminal_fixed_witness_verifier.py`; `exact_campaign.py:3399-3593` | verifier/解释器/OS 仍是命名 TCB；PR2 仍要收缩 loader/snapshot TCB |
| OPEN-GATE | **IMPLEMENTED, gate currently BLOCKED** | `certified_surface.py:482-531`; `phase_1_2_spike_close.json` | 当前 owner 状态不是 closed，所以 public publish 仍必须拒绝 |
| producer/supervisor mint split | **IMPLEMENTED** | `outer_search.py:855-954`; `exact_campaign.py:3399-3593` | producer 内部 candidate verdict 不能被误写成 durable/public CERTIFIED |
| supervisor operational wiring | **IMPLEMENTED**（2026-07-04） | `scripts/run_supervisor_seal.py`（`349c56c`，独立命令、从 proposal-ready marker 驱动）；`main.py` 仍只返回 proposal | 入口存在只满足一条机器条件，不等于 P1.2 closed / 端到端发布流程；尚无真实生产 campaign→seal 实跑记录 |
| central public publisher | **IMPLEMENTED** | `certified_surface.py:563-680` | generic writer、viewer/report、adapter、compat export 均非认证 authority |
| I1 whole-layout independent reverify | **IMPLEMENTED** | `benders_loop.py:7538-7585`; `independent_infeasibility_reverifier.py` | 只覆盖登记的 whole-layout nogood 路径，不自动证明未来 cut family。I1 重建的 binding 子问题与生产侧共读 `EXACT_BINDING_USE_OVERLOAD_SEPARATION`——此项为 **guarded、非 live**：该 env 不在 certified operational allowlist，certified 入口（`benders_loop.py` 闭合白名单守卫）对其开启 fail-closed 拒绝，故 certified 运行中 I1 不可能被该 env 污染；该深度防御缺口已补齐（`a731764`：`PortBindingModel.build()` 加 `use_overload_separation` 参数，I1 复验调用点显式传 `False`，不再依赖 env 守卫层） |
| connector cell body exclusion | **IMPLEMENTED at terminal fixed-witness boundary** | `terminal_fixed_witness_verifier.py:863-866`; fixed-witness tests | solve-time 更早拒绝仍可作为性能/纵深增强，但 public false-CERTIFIED 路径已被终端闸拦截 |
| PYC execution/source binding | **IMPLEMENTED** | isolated replay/capsule 使用 `-B -X pycache_prefix=<fresh>`；obligation `PO-ISOLATED-EXEC-BYTECODE-BINDING` | Python、stdlib、OR-Tools native extension、父 relay、OS 隔离仍是命名 TCB |
| proof obligation close-kernel | **IMPLEMENTED structural gate** | 14 active obligations；checker + sink hashes/guards/allowlist | PASS 只表示登记结构一致，不证明 owner 已 close 或 full suite 已过 |
| PR2 small/read-once verifier TCB | **OPEN** | 设计文档有目标，当前无完整 controlled-loader/read-once implementation | P1.2 关闭前仍需实现、红测和重新封存 |
| immutable review snapshot | **PARTIAL（代码已修，缺专门回归测试）** | `package_review_snapshot.py` 的 `build_package()` 已将 treeish 一次 resolve 为 immutable commit，provenance/manifest/`_materialize_tree` 三处统一用该 resolved commit | 补一条 mutable-ref TOCTOU 回归测试后才算正式收口；PROJECT_LOCK §1A 对应旧表述待 Update-Rule 同步 |
| archive policy completeness | **PARTIAL** | 已过滤 prompt、旧包、嵌套 archive、`.artifacts`/packet 等 | 仍需按 review policy 补齐敏感/非审查面覆盖，并加回归 |
| boundary-placement independent rederive | **OPEN/PARTIAL** | generation-time guard + pinned artifact；没有统一 terminal rule rederive | 进入 P1.2 close 判断前按 owner scope 决定是否列入 required verifier |
| canonical→geometry shared primitives | **PARTIAL / NAMED TCB** | active path 有局部重导；cut helpers 仍可能各自解释覆盖/方向 | 在 F1–F9 真接入 certified master 前必须统一 canonical primitives |
| discrete throughput / belt bandwidth | **OUT OF SCOPE BY DESIGN** | `flow_subproblem.py` diagnostic-only；benders 不以 flow verdict gate | 不是“待补一条测试”的 gap；若要纳入需改变 theorem scope 和新 proof paradigm |
| P1.2 owner gate | **BLOCKED** | `status=blocked_manual_review_count`, `p1_3b_entry_allowed=false` | 只有 owner 显式 decision 可打开，仓库不得从测试、receipt 或 seal 自动推导 |

## 发布闭合条件

P1.2 只有在以下条件同时成立时才能改写为 closed：

1. producer 只提交 proposal，并存在受支持、可审计的独立 supervisor invocation surface；public publisher 保持单入口；
2. fixed-witness、sink replay、terminal evidence 和 disk-current checks 全部 fail-closed；
3. P1.2 publish gate 明确 owner-closed；
4. PR2 TCB、snapshot immutability 和 archive policy 未决项完成并有红测；
5. close-kernel checker、targeted soundness tests 和要求的 full gate 在同一工作树通过；
6. owner 显式关闭 manual gate。

当前只满足其中一部分，因此本文件不得出现“所有 LIVE BLOCK 已修完，所以 P1.2 可关”之类推导。

## 历史映射

旧文中的 P1.2-FIX-1/2/4 大致对应 WS、OPEN-GATE、I1，当前已实现；FIX-3/5 的部分 capsule/TOCTOU
加固已落地，但不能被扩张成 PR2 全部完成。旧的人类名 `P1.3B` 现在统一称 P1.3；机器字段保持兼容。
