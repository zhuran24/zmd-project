# RFC-001 阶段 B 实现规格书——ValidatedStateSnapshot + typed 单入口 + F1/F6/F7 迁移

> 2026-07-11 主会话亲写(分工卡:计划书=主会话)。供料:①`02_rfc_adoption_assessment.md`
> 正式判定节;②stageb-recon(codex)三条只读侦察〔侦〕;③RFC-001 原文。
> **v3(两轮双审定稿)**:v1 经一轮双审(opus 7 条+codex 27 条,6 BLOCK)重写为 v2;
> v2 新拍板经二轮复核(opus 6 条+codex 13 条,4 BLOCK)修订为 v3。两轮 53 条 findings
> 全部采纳、无一驳回,traceability 见文末 §10。涉 PROJECT_LOCK 的项(promotion/CUT-*
> 权威)全部显式挂 owner。文中行号以 2026-07-11 HEAD 为准,实现批开工时须对当时 HEAD 复核。

## 0. 靶与定位

判定节定稿的靶,一句话:

> **同一份深冻结 snapshot 同时供 verifier 与 compiler 使用,master 只接 typed compiled
> result。**封的是 state 侧 validate→compile 漂移(TOCTOU)与 condition identity 缺口
> (Step 8 只查 condition 非空、不验它与验证时 scope 的身份绑定〔侦 1/3 F6 漂移场景〕)。

不是靶的(正交声明):cut 侧漂移(`Cut`/`CutScope`/`OracleCert` 已 frozen);cut 池
持久化/restart replay/跨 epoch 失效(RFC-003/批 E+PIC-4/批 C);F5 独立 proof
(RFC-002/批 D);promotion 本身(lock:487 三前置+owner,B6 独立批)。

## 1. 范围

**In**:FrozenArtifactBundle+snapshot 层(GhostRect/GroupSnapshot/ValidatedStateSnapshot+
唯一 builder+digest);typed 平台层(CutEnvelope v1 adapter/ConstraintPlan/CompiledCut/
ShadowValidated/CutRejection/FamilyCapabilityRegistry 镜像/单入口);F1/F6/F7 三族
**纵切迁移**(parser+typed validator+compiler+registry 升级,B2-B4 逐族与旧路径并存,
B5 切换);**验证与评估层签名迁移**(typed 四族 validator+Step-7 全域 evaluator+Step 6
attest 化+assumption verifiers,见 §4——此范围经双审修正,大于 v1);master add API
两层私有化;raw Step 8 关闭(B5);differential 测试族(与 M2 合并)。

**Out**:F5 compile(阶段 C/RFC-002;本阶段处置 §5.4);F2/F3/F4/F9 的 **validator** 迁移
(拆入 legacy diagnostic 表,§4.2;其 Step-7 evaluator 仍迁,§4.5);schema v2 持久化
(阶段 D);ledger/epoch(RFC-003);unsafe map 翻转/红测预期翻转/PROJECT_LOCK 改写
(B6,owner);registry 取代族数权威(owner)。

## 2. 类型层拍板

### 2.1 FrozenArtifactBundle(静态工件层,双审 BLOCK 修订;v3 定 BState 表示)

v1 的「静态工件引用共享、靠 freeze-ritual 保证不可变」被双审击破:freeze-ritual 只钉
**load 时磁盘字节身份**,不阻止 in-memory 改写;「无 writer」是经验事实(主会话自查+双审
复核:生产零 mutation 命中,`__pose_id_cache__` 已是进程级私有 cache 双 deep-copy)而非
结构保证。(注:v2 曾引 test_p1_2_fix_5_toctou_atomic_snapshot.py 为内存篡改证据,二轮
复核纠正其实质是**磁盘二次读 swap** 的 load→hash TOCTOU;冻结后内存改写的专门红测由
B0 新增,见 §6。)**修订拍板**:

- **session 级一次性递归冻结**:在 ExactSearchSession 读入 frozen bytes 做 hash+解析的
  既有位置(read-once+parse 实际在 benders_loop.py:2205-2216,二轮修正)构造
  `FrozenArtifactBundle`——canonical_rules/candidate_placements/facility_templates/
  instance_to_facility_type 的递归不可变投影(dict→深转换后 `MappingProxyType`,
  list→tuple,set→frozenset),按 artifact digest 键控缓存。**一次性成本**(45MB 级,
  秒级,每 session 一次)。
- **BState 表示拍板(v3,二轮 A① 两条 HIGH 的消解)**:**BState 完全不动**——它按 RFC
  TCB 声明本就属 **untrusted 生成侧**(「Cut generator 与搜索 oracle 均不可信」),字段
  保持裸 Dict,oracle/generator/`_source_jsonable` 的 isinstance(dict) 消费链零波及,
  既有 52 处裸 `BState(` 测试构造不因 bundle 失效。**bundle 不经 BState**:由 session
  直接传给 snapshot builder(`build_validated_state_snapshot(state, bundle)`),typed
  TCB(单入口/typed validator/compiler/evaluator)只读 snapshot——信任边界立在 builder,
  不立在 BState。换 proxy 进 BState 的方案被二轮否决(power_cover_oracle.py:91-117 等
  逐层 dict 检查会炸、`_source_jsonable` 对 proxy 落 `repr` 改变 source_digest 语义)。
- **纵深保留**:AST 负断言扩为**赋值+mutation 双形态**(二轮 #6:只禁 mutation 方法
  捕获不到 `state.candidate_placements = {...}` 整字段替换)——生产代码对 BState 静态
  工件字段禁 Assign/AugAssign/mutation 方法,进 B0 壳。

### 2.2 ValidatedStateSnapshot

字段 = RFC-001 §2 七字段,修订两点:

- ~~`active_assumptions`~~ **删除**(v1 事实错误:Assumption 是 key/value frozen dataclass,
  住在 `cut.scope.active_assumptions`(lifecycle.py:169-189),BState 无此字段;Step 6
  迭代的是 cut 侧清单,state 只是验证时的事实源)。snapshot 需要装的是 **assumption
  verifier 的事实读集**(verify_placement_rule/verify_boundary_saturation 读的 BState
  投影,src/cuts/assumptions/verifiers.py:48/:72),归入公共动态层/family_inputs。
- 增 `groups: Mapping[str, GroupSnapshot]`(GroupSnapshot 含 `selected_poses:
  tuple[str, ...]`——Step 7 literal evaluator 读它,必须冻入)与 `cell_owner` 投影。
- **公共动态层显式含 `ghost_cells`/`exterior_blocks` 本体**(B1 实现上报补,2026-07-11:
  F7 validator 的 full/ghost-only CoverSet 直接读 `state.ghost_cells`
  (power_hitting_set.py:365 域),ghost_rect 无法还原任意 ghost_cells;F1 同读本体)——
  frozenset 深冻结进公共层,所有族共享,不在 family_inputs 重复;RFC 的
  `blocked_cells_digest`/`exterior_blocks_digest` 字段保留作身份。下方 F1/F7 清单中的
  ghost_cells/exterior_blocks 项即指向公共层,不另存副本。
- **builder 两原则**(同批拍板):①groups 投影**全量**(builder 与 proof 解耦,不预知
  contributing 集,由 proof/validator 选择);②candidate pose 投影以
  `(facility_type, pose_id)` 为键(与生产 pose cache 键形态一致,防跨设施类型 pose ID
  冲突)。

动态层深冻结拷贝(ghost/groups/cell_owner/artifact_hashes/oracle_capabilities),静态层
经 bundle(§2.1)。**snapshot 私有构造与 CompiledCut 同款 AST 门**(双审 #26:RFC 明文
「只能由 builder 创建」,普通 frozen dataclass 构造器可伪造 digest——生产构造点恰一处
=builder 内部)。

`family_inputs` 三族逐字段(双审 #27,禁止只引侦察;来源=四族读集表〔侦 1/3〕):

- `F1RegionInputs`:ghost_cells、exterior_blocks、contributing groups 的 demand/pose_domain、
  候选 pose→occupied_cells 投影(经 bundle accessor)、instance_to_facility_type、
  template placement_rule/dimensions。
- `F6HallInputs`:groups demand、group→facility_type、template placement_rule/dimensions、
  ghost_rect、ghost_cells/exterior_blocks(baseline partition 由 validator 从这些重算)。
- `F7PowerInputs`:ghost_rect/exterior_blocks、groups pose_domain、group→facility_type、
  template needs_power、候选 pose occupied_cells、cell_owner、pole radius/dimensions
  (canonical SoT 投影)。

字段的规范化/digest 覆盖规则在 B1 实现时随 schema 定稿,但**字段集以本清单为准**,增删
须回写本规格。

### 2.3 snapshot builder(唯一)与 digest 编码

```python
def build_validated_state_snapshot(state: BState, bundle: FrozenArtifactBundle) -> ValidatedStateSnapshot
```

- 落点 `src/cuts/state_snapshot.py`(新文件);失败抛 `SnapshotValidationError`(fail-closed,
  绝不返回 None/部分 snapshot);非方形 ghost 轴序 round-trip 自检内置。
- **digest 编码(双审 #24 修订,v1 有事实错误)**:现有 `canonical_bytes_for_cert` 用
  **默认带空格** json.dumps(lifecycle.py:541-542),且现有 ghost/blocked/exterior 标识
  **截断 16 hex**(lifecycle.py:444-462)——两者都**不复用**。新定义 `snapshot_digest_v1`:
  版本化+domain-separated(前缀 `zmd.snapshot.v1:`)+`sort_keys`+紧凑分隔符+拒
  NaN/Infinity+UTF-8;**所有新 digest 一律完整 64-hex SHA-256**(RFC-001 §4 明文)。
  投影=动态层全字段+bundle digest 集。不改写既有 `compute_source_digest` 语义(它是
  note/cache 且刻意排除 selected_poses,动它=更深 reseal,阶段 B 不动)。

### 2.4 ConstraintPlan / ModelScope / operation 闭集

- `ModelScope` = frozen:`ghost_policy` + `ghost_rect_digest: str | None` +
  `domain_fingerprint: str`。**fingerprint 覆盖面(双审 BLOCK #12 修订)**:仅 group/
  pose-domain ID 集不够(pose ID 不变而 occupied_cells 变→eligible 集变而指纹不变)。
  v2 定义:fingerprint = sha256 over(bundle 中 facility_pools 的 digest + 相关 group 的
  mandatory slot 结构 + template pose-tuple 登记 digest)——使 F6/F7 master 重查读的
  每个真相源都在指纹内。若 B3 实现时发现该覆盖仍有洞,**退路=plan 直接携带排序后
  eligible pose IDs**(阶段 C 收紧候选提前),以 differential 测试裁定。
- `operation` 闭集 = `{"region_capacity_le", "shape_packing_hall_le",
  "power_pose_exclusion"}`,枚举校验,未知拒绝。
- `parameters` 每族 typed(F1=`group_cell_weights/capacity`,F6=`group_id/region_kind/
  capacity`,F7=`group_id/pose_id/blocked_cells_digest`);condition literal 不进 plan。

### 2.5 结果代数(双审 #14 修订:三分支)

```python
ValidateAndCompileResult = CompiledCut | ShadowValidated | CutRejection
```

- `CompiledCut` 照 RFC 字段;`CutRejection` 含 `stage/reason/cut_id`;新增
  **`ShadowValidated`**(含 `cut_id/proof_digest/snapshot_digest/telemetry_tag`)——
  表达「验证通过但本族无 compile 资格」(F5 的合法出口,v1 的二分代数表达不了它,
  实现者只能伪装成 rejection 或错产 CompiledCut)。
- 三个 typed 工件(CompiledCut/ShadowValidated/ModelScopeBinding)+snapshot 全部私有
  构造+AST meta-test 钉生产构造点恰一处(strong-status allowlist 同哲学)。

### 2.6 ModelScopeBinding 与 resolver(双审 BLOCK #6/#7 修订)

v1 的三连校验第三条(snapshot digest 比对)在 v1 签名下**无法实现**(binding 无
snapshot_digest 字段,step_8 又拿不到本轮 snapshot——只能与自身比较);且 binding 公开
可构造=伪造向量(caller 仍可像今天在 :8119-8128 取 opaque u_var 一样拼假 binding)。修订:

```python
@dataclass(frozen=True)
class ModelScopeBinding:
    rect_idx: int | None
    ghost_rect_digest: str | None
    condition_lits: tuple
    blocked_cells: frozenset | None
    snapshot_digest: str            # resolver 从传入 snapshot 现场计算
    master_domain_projection: str   # v3:MasterDomainProjectionV1,resolve 时从 live master 复算
```

- **MasterDomainProjectionV1(v3,替换 v2 的 master_build_token——二轮双 BLOCK:
  「构建期身份」既无 preimage 定义,又约束不了 apply 时 lowering 重读的 live master 域
  (master 对 pools 只浅拷贝 :2354-2361,F6 重读 live occupied_cells :8151-8165、F7 重读
  live coverer table :7988-8011))**:版本化、domain-separated 的规范化投影,preimage=
  master **实际索引**的 facility_pools digest + mandatory slot 结构(CoordinateSlotSpec,
  exact_coordinate_master.py:723-743/:2468-2498)+ template pose-tuple 登记 digest——
  与 §2.4 `domain_fingerprint` **用同一投影函数**:snapshot 侧在 build snapshot 时对
  bundle 算(进 plan.model_scope.domain_fingerprint),master 侧在 **resolve 时对 live
  master 复算**(进 binding.master_domain_projection),完整 64-hex SHA-256 严格相等。
  「resolve 时复算」即二轮 fix 的「首次 mutation 前重算 live digest」——master 域 apply
  前若已漂,当场 fail-closed。投影函数实现分配:B3(F6 首个消费方)定稿函数,B5 接线
  master 侧;differential 增「master 用异构 domain 构建时校验②必须拒」用例。
- **唯一构造点 = apply adapter 私有 resolver**:
  `_resolve_model_scope_binding(model_scope, snapshot, master) -> ModelScopeBinding`——
  agnostic→空条件;bound→按 ghost_rect_digest 定位 rect_idx→`u_vars[rect_idx]`+
  `_ghost_domains[rect_idx]`,**逐项核对 master var 对象身份与 ghost domain digest**。
  binding 私有构造+AST 钉(§2.5)。
- step_8 校验三连(全部可实现):①`plan.model_scope.ghost_rect_digest ==
  binding.ghost_rect_digest`;②`plan.model_scope.domain_fingerprint ==
  binding.master_domain_projection`(同一投影函数、两个独立算点:snapshot 侧 vs live
  master 侧);③`compiled_cut.snapshot_digest == binding.snapshot_digest`(单入口时 vs
  resolve 时)。缺一 fail-closed。
- `_selected_ghost_context()` 在 attach 路径的双读(build state :7893 / attach :8119)
  收敛为单次读入 snapshot;其余三个调用点(_selected_ghost_cells×2/
  _run_power_placement_subproblem)不在 attach 路径,不参与本次收敛。

### 2.7 CutEnvelope v1 adapter(唯一)与 frozen proof

- `cut_to_envelope_v1(cut: Cut) -> CutEnvelope` 全仓唯一(AST 钉调用面);语义照 RFC §3
  (v1 body 与 proof canonical 投影严格相等后丢弃);ephemeral 不落盘。
- **frozen family proof(双审 #25 补)**:每 envelope 的 proof 解析**恰一次**为 frozen
  proof 对象,validator 与 compiler 读同一对象(RFC 测试义务第 1 条);compiler 禁读
  raw envelope/cert bytes(现状的双解析——validator 读 geometric body、Step 8 再解
  cert(:1217-1227)——正是要消除的)。

### 2.8 FamilyCapabilityRegistry(镜像,不夺权)

stage:F1/F6/F7→`COMPILABLE`、F5→`VALIDATED`(shadow,单入口按 stage 分派到
ShadowValidated 分支)、F8→`RETIRED`、F2/F3/F4/F9→`VALIDATED`(legacy diagnostic,
§4.2)。无族 `ENABLED`(=promotion=B6/owner)。CI 一致性校验(registry vs dispatch 表
vs step_8 分支 vs 文档);**不触碰 PROJECT_LOCK CUT-\* 权威**,冲突时 lock 赢。

### 2.9 测试 seam 与模块路径拍板(B0 实现上报后补,2026-07-11)

B0 实现方上报:§6 的同一对象 id 断言类测试需要可拦截 seam,黑盒 API 观察不到。根源=v3
漏列 RFC-001 §3 的 family plugin 链为显式类型,现补拍板:

- **FamilyPlugin 协议正式化**(RFC 原文四方法,作为 typed 平台的显式 Protocol):
  `parse_and_validate_proof(proof_payload, snapshot) -> FrozenProof` /
  `derive_body(proof)` / `compile(body, proof, snapshot) -> ConstraintPlan` /
  `validate_plan(plan, proof, snapshot)`。单入口按 registry 中的 plugin dispatch。
  **测试 seam = 构造 registry 时注入 spy 包装的 plugin**(装饰器记录入参 id)——
  不是后门:registry 本就是单入口的显式参数,依赖注入是既有设计用足。
- **registry 构造协议**:`FamilyCapabilityRegistry` 显式构造(capability+plugin 映射);
  生产唯一工厂 `build_production_registry()`(AST 钉生产调用点恰一处);测试直接构造
  实例。**不设 `for_testing` 类后门方法**。
- **模块路径**:bundle=`src/cuts/frozen_artifacts.py`(`FrozenArtifactBundle`+工厂
  `build_frozen_artifact_bundle(...)`,实例带 `digest` 属性与各工件只读 accessor);
  snapshot=`src/cuts/state_snapshot.py`(§2.3);typed 平台=`src/cuts/typed_platform.py`
  (envelope/plan/compiled/shadow/rejection/plugin 协议/registry/单入口/v1 adapter)。
- **digest 访问**:bundle/snapshot/plan/compiled 的 digest 一律为 frozen dataclass 字段
  (构造时算定),无独立 accessor 协议。
- **通用钉③的 B0 形态澄清**:单入口是纯函数不接 master,「rejection/shadow 零 master
  调用」在入口层天然成立;B0 可测形态=**step_8 类型拒绝**(raw Cut/ShadowValidated 传入
  新 step_8 被拒,与钉④合流);编排层(_maybe_attach 三路 match 的零调用)是 B5 接线后
  的补充测试,B0 只留骨架注释。
- **B0 双审补拍板(2026-07-11)**:①xfail 一律带 **condition 哨兵**(目标模块/符号
  不存在时才 xfail;符号落地后标记自动失效、断言错当场红——封 strict xfail「只防意外
  转绿不防永远红」的盲区);②B0 拒绝类测试只断言**异常类型**(TypeError/ValueError 级),
  不写死文案;拒绝异常的精确类型/错误码由 B5 实现定稿并回写本规格;③三连校验的负例
  必须**单项不匹配**(仅错①/仅错②/仅错③各一,错绑用例保持另两维一致——负例的单变量
  纪律);④B1.5 解除 shadow xfail 时须补「生产 registry+真实 F5 envelope」测试(spy 版
  只证 dispatch);B5 解除时须新增 _maybe_attach 编排零调用独立测试,不能只靠骨架转绿。

## 3. 单入口与执行序

```python
def validate_and_compile_cut(
    envelope: CutEnvelope,
    snapshot: ValidatedStateSnapshot,
    registry: FamilyCapabilityRegistry,
) -> CompiledCut | ShadowValidated | CutRejection
```

执行序照 RFC §6 步骤 1-6(纯函数,零 master mutation;PREPARED/APPLIED ledger 是
RFC-003 面,留 hook 位不实现)。项目化:

1. **Step 7 独立于单入口,但收 CompiledCut**(双审 #9 修订):Step 7 是 attach 时机决策
   (读 incumbent),不属 compile;但 v1 让它收 raw Cut 会造成「evaluation 的 cut 与
   apply 的 CompiledCut 错配」。v2:`step_7_evaluation_attach_decision(compiled_cut,
   snapshot)`——evaluation 与 apply 绑同一 typed 对象(cut_id/proof_digest/
   snapshot_digest 三字段随身),不再有第二条 raw 路径。
2. **Step 6 的 attest 化(v3,二轮 BLOCK #1 消解)**:checker 契约强制 decision 委托
   canonical step_6,而 CompiledCut 没有 scope 对象可传——类型冲突真实。消解:完整的
   scope 完整性/currentness 校验本就是**单入口步骤 3** 的活(对 envelope.scope 做);
   attach 时刻的 `step_6_attach_scope_check` **保名、语义收敛为 digest attestation**:
   新签名 `(compiled_cut, snapshot)`,校验 `compiled_cut.snapshot_digest ==
   snapshot digest` 且 `compiled_cut.scope_digest` 与 plan.model_scope 一致——即「这颗
   compiled cut 确实产自当前这份 snapshot」的重申,CompiledCut 的 digest 字段就是
   attestation 载体,不需要新的 ScopeAttestation 类型,decision→step_6 的 call-graph
   委托结构原样保持。
3. **名字锚定机制(双审修正表述;v3 收窄)**:`step_7_evaluation_attach_decision`/
   `evaluator_scope_matches_current_state`/`step_7_evaluate_cut`/`evaluate_literal_multiset`
   四节点由 sealed obligations manifest 的 step_7_contract(p1_2_proof_obligations.json:10-13)
   经 check_p1_2(:2929-2941)做定义+call-graph 校验,委托结构必须保持;checker 对
   `step_6_attach_scope_check` **仅做词法调用检查**(`_calls_function`,不验定义/签名,
   二轮 #12 修正);`step_8_apply_to_master` 仅被 check_phase_review_gate.py:237-264 的
   blocked 分支按名查(当前 gate allowed=true 不激活)。操作纪律不变:**名字不改,只换
   参数类型**;B5 顺手补 step_6 唯一定义检查与 step_8 不依赖 gate 状态的 AST 名称+签名
   契约测试。

## 4. 签名迁移矩阵(双审大幅扩面后的完整版)

| # | 对象 | 现状 | 目标 | 备注 |
|---|---|---|---|---|
| 4.1 | typed 四族 validator(F1/F5/F6/F7) | `(Cut, BState, JsonDict)`(第三参四族均丢弃,region_capacity.py:372 first-line `del canonical_rules` 实锤) | `(frozen_proof, snapshot)` | F5 同签名,出口=ShadowValidated |
| 4.2 | legacy 四族 validator(F2/F3/F4/F9) | 同上(replay.py:63-71 八族一张表) | **不迁**;dispatch 表拆 typed/legacy 两张,legacy 仅 replay/诊断可达。**隔离强化(二轮 #8)**:registry 增 `execution_path: TYPED \| LEGACY_DIAGNOSTIC` 字段,两组 family key 集精确互斥且穷尽(机器钉);legacy replay 返回独立 `DiagnosticResult`,**禁止 reactivate/进 active store/selector/promotion 计数**(现状 replay ok 即 `store.reactivate_cut`→`is_active()` 为真,replay.py:160-163/store.py:195-207——该路径对 legacy 族必须切断) | AST+红测机器证明 legacy 表不可达单入口与 step_8(生产 attach 链本就只产 F1/F5/F6/F7,benders_loop.py:8130-8183+lifecycle 四族分支〔二轮复核为净〕) |
| 4.3 | `step_6_attach_scope_check` | `(cut, state)` | `(compiled_cut, snapshot)`,语义=digest attestation(§3.2) | 保名;完整 scope 校验移入单入口步骤 3 |
| 4.4 | `assumption_holds` **及 assumptions/verifiers.py 全体**(Verifier 协议 :31-34、verify_placement_rule :48、verify_boundary_saturation :72 及其 canonical helpers) | `Callable[[BState, str], bool]` | snapshot-native | v1 只列 assumption_holds=后门残留(双审 #5);verifier 读集入 §2.2 公共层 |
| 4.5 | **Step-7 全域**:`step_7_evaluation_attach_decision`/`evaluator_scope_matches_current_state`/`step_7_evaluate_cut`(真实生产入口,benders_loop.py:8213)/`evaluate_literal_multiset`/五个 `evaluate_geometric_*`(region_capacity/cutset/component_reach/density_envelope/shape_packing_hall,lifecycle.py:1099-1108) | `(cut, state)` 族 | `(compiled_cut, snapshot)`(编排三件)与 `(frozen_proof 或 compiled_cut, snapshot)`(evaluator 按需) | v1 「三件」严重低估(双审 opus HIGH-1/codex #8);F2/F4/F9 evaluator 读集⊂公共动态层,其 validator 仍 legacy(4.2)不冲突 |
| 4.6 | `step_8_apply_to_master` | `(cut, master, *, ghost_condition_lits, ghost_blocked_cells)`(lifecycle.py:1163-1169) | `(compiled_cut, master, *, scope_binding)` | 保名;binding 只能来自私有 resolver(§2.6) |
| 4.7 | `_maybe_attach_framework_cuts` | 内部手工五连(:8196-8221) | 外签名不变;内部=一次 build snapshot→逐 cut 单入口→**三路显式 match**(二轮 #7/opus):`CompiledCut`→step_7→step_8;`ShadowValidated`→记 common-mode-untrusted telemetry 后跳过;`CutRejection`→记 rejection telemetry 后跳过;budget 短路保持在 snapshot 构造前 | shadow/rejection 结构上进不了 step_7(它只收 CompiledCut),类型即防线 |
| 4.8 | `replay_cut`/`regression_sweep` | `(cut, state, store, *, canonical_rules)`(replay.py:75-81/:182-213);CutStore 调用面 store.py:275-280 | **签名改收 `ReplayContext(snapshot, registry, legacy_state)`**(二轮 BLOCK #2:只删 canonical_rules 拿不到 bundle/snapshot/registry,单入口无法调用):replay 触发方(campaign 启动/source rotate)构造 bundle→`regression_sweep` **循环外一次** build snapshot 装入 context;typed 四族内部调完整单入口(**成功即丢弃 CompiledCut,绝不 apply**),legacy 四族走 legacy 表(出口=DiagnosticResult,4.2);外部仍返回 AttachDecision;**store.py 调用面同批迁移** | v1「只复用 verifier 核心」被双审 #10 击破:verifier 过而 compiler/plan-validation 拒的 cut 会被 replay 错误接受;RFC 明文 replay 在 TCB 内同链 |
| 4.9 | `run_lifecycle` 参考管线的 raw step_6(lifecycle.py:1477) | raw state | 同步迁 snapshot | 防第三条 raw 路径(opus HIGH-1 附带) |
| 4.10 | 四个 `add_*_cut`(master_model.py:12147-12249 公开转发 facade+delegate 四函数 backend) | public API 两层 | **两层分别私有化、各自钉边**(二轮 #10:单一「唯一调用者」规则在两层结构下无法照字面实现):typed apply adapter→facade `_lower_*`(唯一);facade `_lower_*`→backend `_lower_*`(唯一);全仓 AST 拒绝其余调用与 `_coordinate_delegate` 属性获取旁路 | v1「保留为私有 API」无机制(双审 BLOCK #16);B5 波及双 master 文件**确认** |
| 4.11 | lowering 原子性 | `add_*_cut` 在多次 `_pose_present_literal`(造 presence 变量/AddImplication,:7683-7689)之后仍有失败分支(如 add_region_capacity_cut :7887/:7890 return False;二轮修正:_pose_present_literal 自身的 None 出口在 mutation 前,残留风险在调用者) | **precheck 前移**:全部失败分支在首次 mutation 前判定,mutation 段零失败分支;differential 失败测试钉 model proto+内部 cache 字节不变 | v1「解析后单次 Add=原子」只对最终 cut 约束成立(双审 BLOCK #17);presence 辅助结构语义中性(仅定义新变量)但 RFC 字面要求零残留,以 precheck 前移满足 |

## 5. 三族迁移拍板

### 5.1 F1(小到中)
Step 8 现 cert→参数段(lifecycle.py:1217-1254)抽成纯 compiler;ghost scope 归 binding;
lowering 保留。**4.11 的 precheck 前移属 B5**(动 sealed master 文件;B2 明确不 mutate
master——B0 双审曾误归 B2,此处消歧)。

### 5.2 F6(中)
domain_fingerprint 按 §2.4 v2 定义(covering facility_pools digest+slot 结构+pose-tuple
登记);master apply 重查 eligible baseline poses 保留,fingerprint 绑定使之成为「同一
真相的两次读」;differential 裁定,不足则退 plan 携带 pose IDs。

### 5.3 F7(中到大)
plan 带 `blocked_cells_digest`,binding 带本体(resolver 从 snapshot 冻结值复原+digest
校验);runtime master coverer gate(:7988-8011)保留为 master 域独立防线。M2 合并见 §6。

### 5.4 F5 处置(双审三条修订)
- 单入口对 F5 出口=`ShadowValidated`(§2.5 三分支,消解「VALIDATED 但不 compile」的
  表达矛盾);`_maybe_attach_framework_cuts` 记 telemetry 后**不调 step_8**。
- **telemetry 标 `common-mode-untrusted`**(双审 #15:F5 复验与生成共用同一 oracle/
  adapter registry——复验共享 adapter 在 pattern_nogood.py:448-483,同名注册静默覆盖在
  **pattern_nogood_oracle.py:141-162**(二轮修正文件归属),不是独立验证)——shadow
  结果不得进 active store/ledger/selector/任何 promotion 计数。
- lifecycle 的 F5 step_8 分支(:1356-1408)**随 raw step_8 关闭一并删除**(v3 反转 v2
  的「保留标 unreached」——二轮 #7:新 step_8 只收 CompiledCut 而 F5 永远只产
  ShadowValidated,新世界里该分支不存在,保留即与代数矛盾);test_step_8_apply_to_master
  的 F5 用例(:574-576 现期待 raw F5 真 mutate)**反转为红测**(raw F5 拒),master
  `add_pattern_nogood_cut` 随 4.10 一并私有化。
- spike harness(e2_harness.py)是研究工件不在生产链;B5 后重跑需适配新 step_8 签名,
  记入 harness 文件头注释,不阻塞。
- 与三硬门「F5 shadow」、REVIEW.md:266-270、RFC-002(批 D)自洽〔双审 #13 复核为净〕。

## 6. differential 测试族(与 M2 合并,B0-B4 逐批落)

统一 parameterized family contract:

```text
raw Cut → v1 adapter → snapshot → validate_and_compile_cut → ConstraintPlan
  → 独立 plan interpreter(测试侧第二实现)
  → 真实 tiny CP-SAT master adapter
```

小实例穷举 relevant presence/ghost 赋值,三方比对(interpreter 判定 vs apply 后 master
实测可行性 vs family helper/verifier 预期)。

- **每族最低覆盖**:F1=capacity 边界/agnostic/ghost-bound active+dormant;F6=left+bottom/
  interior pose 不计入/cap 0 与 1/ghost-bound;F7=CoverSet empty+non-empty/missing+
  live+dead coverer/condition scope。
- **通用钉(六条,双审 #25 增补⑥)**:①verifier 与 compiler 收到同一 snapshot 对象
  (id 断言);②改 builder 输入 dict/list 后 snapshot/plan digest 不变;③rejection/
  shadow 时 master 零调用;④raw Cut 直达 apply 被拒;⑤condition 错绑(u_B 配 scope_A)
  被拒;⑥**同一 frozen proof 对象**(id 断言)+compiler 禁读 raw envelope/cert bytes。
- 失败路径原子性测试(4.11):proto+cache 字节不变。
- **冻结后改写攻击红测**(v3 补,二轮 #11:现有 TOCTOU 测试打的是磁盘 swap 不是内存
  别名):bundle 构造后改写源 dict/list→bundle 内容与 digest 不变;归 B0 壳。
- **M2 合并边界**:F7 Layer 2(20×20 真实 coverer table vs helper)与 F1/F6 Step-8 行为
  case 改造为 family fixtures;F7 Layer 1+方圆分歧带**单独保留**(定位 canonical geometry
  漂移);「4761 anchor 全量」指 generator vs master 公式、helper 本体只抽验,合并后
  表述不得放大。
- **telemetry taxonomy**:现 integrity/validator/scope/evaluate 四类,增 compiler/
  plan-validation/model-scope/master-rejection/shadow 五类映射(wiring 测试同步)。

## 7. 分批与 reseal 纪律(双审修订:+B1.5,B5 清单实化)

| 批 | 内容 | 碰 sealed? | reseal |
|---|---|---|---|
| B0 | 契约测试壳:alias/digest、非方形 ghost、same-object(snapshot+proof)、condition 错绑、rejection-zero-mutation、静态工件 AST 负断言(赋值+mutation 双形态)、冻结后改写红测。**全部 `xfail(strict)` 标注**,实现批逐条解除(双审 #23:裸红测会破坏主干 CI) | 否 | 无 |
| B1 | FrozenArtifactBundle+snapshot 层(§2.1-2.3):bundle/GhostRect/GroupSnapshot/ValidatedStateSnapshot/builder/深冻结/digest v1;bundle 不经 BState(§2.1);不改 attach 链 | 新文件 | **新 TCB 文件无条件注册+hash-pin**(双审 #21:词法 token 扫描可能漏掉不含关键词的 lazy-import 模块;RFC 明文 snapshot builder 在 TCB) |
| B1.5 | **typed 平台层**(双审 #20 补批):CutEnvelope+v1 adapter/frozen proof/ConstraintPlan/CompiledCut/ShadowValidated/CutRejection/registry(execution_path 字段)/单入口骨架+plan validation/四件私有构造 AST meta-tests;**含 F5 typed validator+shadow 分支**(验证 ShadowValidated 通路,F5 无 compiler 正合适);无 F1/F6/F7 compiler | 新文件 | 同 B1 |
| B2 | **F1 纵切**(v3 重排,二轮 BLOCK #3:v2 把 typed validator 全推 B5 导致 B2-B4 的 differential 链断头——单入口无 validator 产不出 CompiledCut):F1 parser+typed validator+compiler+registry 升 COMPILABLE+differential 全链;**与旧 raw 路径并存,生产链不动** | 新文件 | 同上 |
| B3 | **F6 纵切**(同型)+MasterDomainProjectionV1 投影函数定稿(§2.6) | 新文件 | 同上 |
| B4 | **F7 纵切**(同型)+M2 合并 | 新文件+测试迁移 | 同上 |
| B5 | **wiring cut-over**(职责收窄,二轮 #3/opus#3):生产链改接单入口(4.7 三路 match)、旧签名迁移与旧路径删除(§4 全表:step_6 attest 化/Step-7 全域/assumptions/replay ReplayContext/store 调用面/legacy 双表)、raw Step 8+F5 分支删除、master API 两层私有化、telemetry 扩展、step_6/step_8 独立 AST 契约、全部 pin 重钉 | **已知下界 ≈16 个 pinned 文件**(二轮 #9 实化,v2 的 ≈10 是低估):lifecycle.py+benders_loop.py+replay.py(source-hash floor,二轮 #12 修正分类:非 sink 表成员)+store.py+assumptions/verifiers.py+四族 typed 文件+三个 legacy evaluator 文件(cutset/component_reach/density_envelope)+两个 helper(canonical_rules.py/canonical_sot.py)+exact_coordinate_master.py+master_model.py;**floor 文件一改必 re-pin**(checker :13181-13191 无条件比较 floor SHA,不存在「以实跑为准」的余地);另计既有测试语料迁移面(52 处裸 BState 构造中受签名影响的 8 个文件的 (cut,state) 调用点) | 完整 reseal 连锁;**开工前先跑 impact 扫描生成最终文件清单**;若拆批,拆分线=**functional-rewire(B5a:单入口接线+全签名迁移+测试语料)/AST-lockdown(B5b:raw step_8 与 add_* 私有化+allowlist 钉)**(opus#3:verifier 签名一迁,旧调用点当场失配,单入口接线推不到后批;v2 的 verifier-vs-raw 拆分线不可行),各自 reseal |
| B6 | promotion(unsafe map/红测翻转/PROJECT_LOCK/lock:382 校准) | lock+checker | **owner 批**;排在批 C/D/E 全部完成之后 |

纪律:①中间态(B0-B4)attach 保持 certified unsafe/default-off,红测零翻转;新 typed
路径与旧 raw 路径并存期间,typed 路径不得被任何生产入口调用;②每个碰 pinned 文件进主干
的批各自 reseal,禁止「source drift 稍后再封」;③B5 若拆批,中间态的正确表述是
「**certified reachability 阻断**仍然成立」(unsafe gate 拦住 raw 路径),不是「raw API
本身 fail-closed」(双审 #22:raw Step 8 对合法 Cut 本就真改模型,该说法不可测)。

预期批型(分工卡):B0-B4 codex 实现+opus/codex 双审;B5 codex 实现+双审+主会话终审
reseal(PIC-3 同型放大);B6 owner。

## 8. 风险登记与处置(v2 增补)

| # | 风险 | 处置 |
|---|---|---|
| 1 | 浅冻结冒充深冻结 | §2.1 bundle 一次性递归冻结+§2.2 动态层深拷贝+通用钉② |
| 2 | snapshot 不自动证明 master 一致 | §2.4 fingerprint 覆盖面 v2+§2.6 三连校验 |
| 3 | condition identity | §2.6 私有 resolver+binding 身份核对+通用钉⑤ |
| 4 | F5 旁路 | §5.4 ShadowValidated+raw 关闭+4.10 私有化 |
| 5 | 多 v1 adapter | §2.7 唯一函数+AST 钉 |
| 6 | typed 工件伪造 | §2.5 四件(snapshot/CompiledCut/ShadowValidated/binding)私有构造+AST 恰一处 |
| 7 | apply 非原子(辅助结构残留) | 4.11 precheck 前移+proto 字节不变测试 |
| 8 | registry 夺权 | §2.8 镜像只报不裁;owner 项 |
| 9 | 阶段 B 边界误读 | §0 正交声明 |
| 10 | strong-status allowlist | 预期零新增 CERTIFIED/INFEASIBLE writer;B5 收口第二 checker 实跑核实(当前未核实) |
| 11 | evaluation/apply 对象错配 | §3.1 Step 7 收 CompiledCut |
| 12 | replay 弱于生产链 | 4.8 replay 内部调完整单入口 |
| 13 | legacy validator 表泄漏进生产 | 4.2 双表拆分+execution_path 互斥钉+AST/红测不可达证明 |
| 14 | F5 shadow telemetry 被误读为独立验证 | §5.4 common-mode-untrusted 标注+禁入 promotion 计数 |
| 15 | master 域在 build 与 apply 之间漂移(浅拷贝 pools,lowering 重读 live) | §2.6 MasterDomainProjectionV1 resolve 时对 live master 复算 |
| 16 | legacy 诊断成功污染 active store | 4.2 DiagnosticResult+禁 reactivate |

## 9. 与 checklist/lock 的衔接

- checklist:阶段 B=通电线工程主线;PIC-1.2/PIC-2 顺位批 D 不变;PIC-6(replay subset
  残留)**搭车 B5**(replay.py 反正必改);PIC-4/PIC-5(批 C)可与 B0-B4 并行侦察。
- PROJECT_LOCK:382 过时叙述校准=B6 随批(lock 是 owner 权威文件)。
- 本规格与 lock 冲突时以 lock 为准。

## 10. 修订记录与 traceability

- **v1→v2(2026-07-11)**:opus(AGREE_WITH_AMENDMENTS,7 条)+codex(BLOCK,27 条)双审。
  6 BLOCK 全部采纳:静态工件层改 FrozenArtifactBundle(#3);binding 增 snapshot_digest+
  master_build_token、resolver 私有唯一(#6/#7);F6 fingerprint 覆盖面实定义(#12);
  master add API 私有化+AST allowlist(#16);lowering precheck 前移(#17);B5 reseal
  清单实化≈10 文件(#18+opus replay.py)。HIGH 全采纳:Step-7 全域迁移面(opus#1/
  codex#8/#9)、active_assumptions 删除(#4)、assumption verifiers 全迁(#5)、replay 调
  完整单入口(#10/#11)、三分支代数(#14)、common-mode-untrusted(#15)、legacy 双表
  (#19,取选项 2)、B1.5 平台批(#20)、TCB 无条件 pin(#21)、digest 编码修正(#24)、
  同一 proof 钉(#25)、snapshot 私有构造(#26)、family_inputs 逐字段(#27)。LOW/INFO:
  checker 锚定表述修正(opus#5/codex#1)、行号 8119(#2)、F5 step_8 分支去留(opus#6,
  该处置后被 v3 反转)、B5 中间态表述(#22)、B0 xfail(#23)、双读点澄清(opus#7)。
  opus 其余三条(#2 evaluator 文件 sink 辨析并入 #18 处置/#3 B5a-b 拆分线,v3 重述/
  #4 F6 fingerprint 与 codex#12 合并)。**无一驳回**。

- **v2→v3(2026-07-11)**:二轮复核 opus(AGREE_WITH_AMENDMENTS,6 条)+codex(BLOCK,
  13 条),靶=v2 新拍板。traceability(编号→v3 落点):

  | 二轮 finding | 处置 → v3 落点 |
  |---|---|
  | codex#1 BLOCK(Step 6 与 CompiledCut 类型冲突) | 采纳轻量版:step_6 保名 attest 化(§3.2) |
  | codex#2 BLOCK+opus#4 LOW(replay 拿不到 bundle/snapshot/registry) | 采纳:ReplayContext+循环外一次 build+store.py 迁移(4.8) |
  | codex#3 BLOCK+opus#3 HIGH(B2-B4 依赖断头/B5a-b 拆分线不可行) | 采纳:B2-B4 改逐族纵切(parser+validator+compiler+registry),B5 收窄为 wiring cut-over;拆分线重述 functional-rewire/AST-lockdown(§7) |
  | codex#4 BLOCK+opus#1 HIGH(master_build_token 同型病:preimage 未定义+约束不了 live 域) | 采纳:MasterDomainProjectionV1,同一投影函数、snapshot 侧与 live master 侧独立算、resolve 时复算(§2.6) |
  | codex#5/#6 HIGH+opus#2 HIGH(BState 表示未拍板/proxy 波及/AST 只禁 mutation 不禁赋值) | 采纳 codex 选项 2:BState 不动=untrusted 生成侧,bundle 不经 BState;AST 负断言扩赋值形态(§2.1);测试语料面计入 B5 清单(§7) |
  | codex#7 HIGH+opus#5 LOW(三路控制流未成文/F5 分支保留矛盾) | 采纳:4.7 三路显式 match;F5 step_8 分支删除+专测反转(§5.4,反转 v2) |
  | codex#8 HIGH(legacy 进 active store) | 采纳:execution_path 互斥钉+DiagnosticResult+禁 reactivate(4.2) |
  | codex#9 HIGH(≈10 低估;floor 必 re-pin) | 采纳:下界 ≈16 文件实名+「floor 一改必 re-pin」改述(§7 B5) |
  | codex#10 HIGH(facade/delegate 两层钉边) | 采纳(4.10) |
  | codex#11/#12 LOW+opus#6 INFO(TOCTOU 证据性质/行号 2205-2216/replay.py 分类/step_6 锚定强度/pattern_nogood_oracle 归属/_pose_present_literal 定位) | 全部采纳修正(§2.1/§3.2/§5.4/4.11/§7);B0 补冻结后改写红测(§6) |
  | codex#13 LOW(traceability 矩阵) | 采纳=本表 |
  | opus#5 LOW(三路 dispatch 未成文) | 并入 codex#7 处置 |

  **无一驳回**。v3 的三个再拍板(BState 选项 2/MasterDomainProjectionV1/step_6 attest 化)
  均取自二轮 fix 方向,标记为 B1/B3/B5 实现批的首件验证项。
