# 23 — 规则与 cut 演化 shadow 协议

rule_cut_evolution_status: full_preflight_passed
authority_effect: non_authorizing
authority_digest_change: none
p1_2_reseal: not_performed

## 定位

本协议把 [REASONING_METHOD.md](REASONING_METHOD.md) 的规则归属与 cut 演化判据
映射为 test/offline-only 静态覆盖。迁移前 `§0b` 原文保存在
[冻结 roadmap 快照](../history/status/00_master_roadmap_pre_phase3_20260812.md)。production runtime 不导入或消费这些 shadow
规格；静态门从外部核验既有硬编码，不改变 owner、stage、capability、控制流、
generation 顺序、trusted apply 闭集或 family 晋级状态。

`rule_cut_evolution_status` 是本协议自身的 bounded marker，不是项目 phase gate。项目当前实现与 gate 见
[CURRENT](../CURRENT.md)，目录入口见 [README.md](README.md)，规范术语边界见
[TERMINOLOGY](../TERMINOLOGY.md)。

## 本批提供的维护面

- `RuleSemanticSpec` 位于测试树，登记语义版本、显式版本化信息层序、authoritative
  owner、representation owner、必要投影/充分限制/精确语义极性、完整前件、假设、
  失效条件与 exact twin checker 可用性。owner 校验基于信息层序，不读取字符串排序
  或遥测。
- `FamilyTrustSpec` 与 `FamilyGenerationSpec` 位于测试树，以相互校验的静态规格映照
  既有 capability、plugin identity、proof schema、精确 snapshot field dependencies、
  generator、replay、lowering operation、lifecycle、telemetry 与 required contracts。
  缺失能力显式登记为 unavailable，shadow 消费遇到矛盾时 fail-closed。
- 静态一致性门只读取并核验既有 registry、cert schema、generator 签名和版本常量、
  Benders branch/order、replay 集合、lifecycle projection switch 与 lowering 闭集。
  production runtime 不从 shadow 规格接线。
- onboarding fixture 增加一个未获 production admission 的 test family，复用既有
  `region_capacity_le` operation，覆盖 proof → plan → independent interpreter →
  tiny real CP-SAT master → exact checker 的差分链，以及 malformed proof、版本/前件/
  snapshot 漂移、错误强化、未知类型、HOLD/QUARANTINE、replay 与 apply 原子性负路径。
- `RejectionRecordV1` 及 adapter 只存在于 test/offline audit sidecar。记录以既有
  `cut_id` 或 semantic fingerprint 为 subject，不含 `record_id`，不进入任何 authority
  digest，也不能生成、晋级、replay、compile 或 apply cut。typed platform、replay
  与 CutStore 仅由测试侧 observer 验证；Benders 为 `DECLARED_DEFERRED`，binding、
  routing 与 power 仅有静态后续迁移合同。
- generator、family verifier 与 exact checker 保持独立信任角色。遥测不能决定
  owner，rejection facts 不能自动晋级为可信 cut。

对应实现集中在 `src/tests/cuts/rule_cut_evolution/`；原先尝试放入
`src/cuts/` 与 `src/search/` 的 manifest/audit 模块不属于 production 终态。

## F1–F9 能力登记

| Family | 当前执行面 | Exact checker | Projection / lowering |
|---|---|---|---|
| F1 `region_capacity` | `COMPILABLE` / typed | unavailable | 既有 projection / `region_capacity_le` |
| F2 `cutset` | validated legacy diagnostic | unavailable | unavailable |
| F3 `port_exposure` | validated legacy diagnostic | unavailable | unavailable |
| F4 `component_reach` | validated legacy diagnostic | unavailable | unavailable |
| F5 `pattern_nogood` | validated typed shadow | `verify_binding_empty_domain` | unavailable / unavailable |
| F6 `shape_packing_hall` | `COMPILABLE` / typed | unavailable | 既有 projection / `shape_packing_hall_le` |
| F7 `power_hitting_set` | `COMPILABLE` / typed | unavailable | 既有 projection / `power_pose_exclusion` |
| F8 `power_grid_reach` | retired | unavailable | unavailable |
| F9 `density_envelope` | validated legacy diagnostic | unavailable | unavailable |

该表只复述当前硬编码。它不为 legacy、shadow 或 retired family 合成不存在的
production checker、projection、lowering 或 replay 能力。

## Authority 不变量

本批不修改 `PROJECT_LOCK.md`；其 SHA-256 保持
`33632dfdb2297425e42066b2cf0749ca6b9ab1f8653e810b6f2e53ded1025410`。本批不重开、
不 reseal P1.2，也不修改其 manifest/hash。六个曾被 runtime-wiring 尝试触及的既有
运行面恢复为 `398f872` 的逐字节内容，且相对该基线没有任何非测试 Python source
差异。

静态 authority gate 与 known vectors 继续约束既有 public wire schema、digest、
signature、`ConstraintPlan`、semantic fingerprint、generation order、apply、replay、
失败阶段与文本、序列化 bytes 及 master-independent plan/compiled/snapshot digests。
任何 shadow 登记缺失或矛盾只使测试侧 gate 失败，不改变 production fallback、
异常传播或 master mutation。TCB 异常仍沿既有路径进入 `POISONED` 并抛出。

## Production 延期项

以下事项不属于本批：

- production runtime 从 family/rule manifest 接线；
- registry、resolver、Benders dispatch、replay、lifecycle、lowering 或 trusted apply
  的 production 迁移；
- `Cut`、`CutEnvelope`、proof、`ConstraintPlan`、snapshot、`StoredCut`、replay 或
  rejection persistence 的 wire/schema/digest 版本升级；
- binding、routing、power 等其余失败 seam 的 audit 接入；
- family owner、stage、capability、checker 待遇或 promotion 状态的改变；
- P1.2 reseal、phase gate 变更或 `PROJECT_LOCK.md` 政策变更。

这些变更必须进入独立的 owner-authorized 批次并重新满足各 family 的独立证明门槛，
不能由本 shadow 协议或测试绿灯推出。

## 终态验收状态

本批维护面已通过 production byte/hash parity、P1.2 checker、known vectors、聚焦合同、
targeted Ruff/mypy 与 authoritative-numbers currency 白名单。`src/tests/cuts` 的
collection currency 由生成器更新为 958；这只是 collected 数，不是 full pass 数。

验收基线为 commit `fd015a9ac49a182b242895433a2ff2d2e5ee57de` 的干净工作树。使用 coherent
backup venv、显式清除 `PYTHONPATH` 与 `PYTHONHOME`，并持有独占资源互斥锁时，
`scripts/preflight_gate.py --full` 返回 `0`；总体结果为 `PASSED`（19 passed），其中
pytest 为 `4701 passed, 74 skipped in 98.52s`。完整 stdout/stderr 日志的 SHA-256 为
`fedf7de80905b47c626b874213f0471a2e499a7fdd56bbc862bab47027138bc1`；该日志是外部
验收记录，不进入 authority digest。验收后 `PROJECT_LOCK.md` 的 SHA-256 仍为
`33632dfdb2297425e42066b2cf0749ca6b9ab1f8653e810b6f2e53ded1025410`。

`full_preflight_passed` 只验收本文所述 test/offline shadow 维护面。它不授权 production
接线、family 晋级、P1.2 reseal、owner flip、持久化 schema 变更或新的数学结论，也不降低
任何 family 的独立证明门槛。
