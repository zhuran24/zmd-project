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

**B1 双审后补拍板(2026-07-11)**:
- `family_inputs` 正式定性为**纯派生字段**(由 bundle/groups/ghost/cell_owner 确定性
  派生,非独立身份来源,不进 digest preimage);该假设由等价性测试钉死(从 snapshot
  其他字段重构造 family_inputs,断言相等)。
- **builder 原子捕获**:先对 BState 动态字段做**一次性冻结投影**,source digest 输入、
  groups、family_inputs 全部从同一份投影派生(封 side-effect 容器在两次遍历间改值的
  hybrid snapshot 缝);调 `compute_source_digest` 前对 source payload 严格验证
  (exact-str keys/精确标量类型/有限数,fail-closed)——旧编码的 str() 化 key 与
  NaN 接受性不得进入身份层。
- **bundle 工厂只吃四工件显式入参**(移除 from-BState 入口——B1 任务书曾写「可从
  BState 投影」与 §2.1 冲突,以规格为准)。
- **公开 digest primitive 单射性**:`snapshot_digest_v1` 对外接受域收严(type-tagged
  canonicalizer 或拒绝非 exact 类型),防 key coercion/容器折叠碰撞。
- **残余风险入档(按 owner 2026-07-06「仅防故意内鬼的硬化暂缓到发布时点」拍板)**:
  ①构造 token 是可导入模块全局,进程内显式引用可绕过(AST 门补钉「生产代码引用 token
  即红」的便宜防线;运行时防护缓);②Python frozen dataclass 可被重跑 `__init__` 原地
  篡改(全项目 frozen dataclass 通病,含 Cut/CutScope;真一次性构造风格留发布硬化批)。
- **性能实测**(codex,45MB candidate_placements):bundle 构造 ~15s、峰值 RSS ~2.3GiB、
  snapshot builder ~4.2s——「每 session 一次」可接受;B5 接线时 bundle 构造须放
  session 建立期(master build 前的内存低谷),不得进 benders 迭代路径。
- **⚠ 2026-07-12 审计校准(文档实态外审 F02;登记 promotion 前 BLOCK)**:本节权威拍板
  仍是「每 ExactSearchSession 构造一次并复用」,但 B5a 实际落地为**每次
  `_maybe_attach_framework_cuts` 调用重建** bundle/snapshot/registry
  (`benders_loop.py:8150-8161`,源码注释「ONCE per attach round」是 per-round 单次、
  不是本节的 per-session;工厂无 session-owned 字段、无 artifact-digest 键控缓存)。
  实现偏离没有留下显式「推翻 session-once」的裁决理由,两套说法一度并存——按上行实测
  ~15s/~2.3GiB,per-attach-round 在 production campaign 下的重复成本与内存尖峰不可
  接受为终态。**处置**:B6 前须把 bundle 所有权提升到 session(按 artifact digest/
  会话身份钉复用与失效规则,并保持 α-1 内容绑定与 α-5 深冻结语义),或由 owner 显式
  改判本节拍板;在此之前不得把「once per attach round」注释解读为已满足本节。
  该项是**实现债**,不属于修复批 β(纯文档)的关闭范围。

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
- **CutRejection 刻意公开可构造、不在私有构造之列**(B1.5 双审 codex#10 消歧):伪造
  rejection 只能造成保守 false-negative(自拒),无 soundness 危害;「四件私有构造」
  正字=snapshot+CompiledCut+ShadowValidated+ModelScopeBinding。
- **异常边界(B1.5 双审 codex#1)**:单入口只允许捕获**专用语义拒绝异常类型**转
  CutRejection;proof frame 非法、插件签名/返回类型违约、深冻结失败、TypeError/
  AssertionError/RuntimeError/MemoryError 等表示层与 TCB 故障**必须传播**(fail-closed),
  禁止宽泛 `except Exception` 洗成 rejection(fail-open)。

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
- **v1 scope identity 禁 rehash 截断值(B1.5 双审 codex#4)**:lifecycle 的 16-hex 截断
  digest(64-bit)不得经再哈希冒充完整 proof identity;adapter/currentness 必须从 raw
  preimage(ghost tuple、完整排序 cell set)以 domain-separated SHA-256 重算,与
  snapshot 侧完整 digest(state_snapshot 已有)比对;仅 16-hex 可用的 legacy 形态
  fail-closed。
- **adapter 准入(B1.5 双审 codex#5)**:`payload_schema_version == 1` 严格相等;
  `is_quarantined=True` 或非空 `quarantine_reason` 一律 fail-closed(PROJECT_LOCK
  :404-407 quarantine 不进 active resolve),禁静默擦除。

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

**B2 侦察补拍板(2026-07-11,codex 三缝上报后)**:

- **raw scope preimage=方案 A**:`CutScope` 增 versioned frozen carrier
  `ScopeIdentityPreimageV1`(`ghost_rect: tuple|None` + `blocked_cells`/`exterior_blocks`
  排序不可变 tuple),字段 `identity_preimage: ScopeIdentityPreimageV1|None`(默认 None)。
  oracle 在构造 CutScope 的**同一次读取**里同时捕获 legacy 16-hex 与 raw carrier;typed
  adapter 先由 raw 重算并核对 legacy 16-hex(一致性防伪),再算 Stage-B domain-separated
  64-hex;`identity_preimage=None` 的旧 cut 反序列化合法但 typed 路径 fail-closed(仅
  legacy 诊断可达);agnostic 同样必须携带完整 exterior preimage,禁止「当前恰为空」的
  常量特判;不动 benders_loop、不进 F1 proof digest。方案 B(塞 cert)撕破 cert 闭集
  schema(cert_schema.py:26/113 allowed=required),方案 C(sidecar/双参 adapter)破
  replay 与唯一 adapter 拍板——均拒。
- **F1 assumptions 校验前移 B2**(侦察缝 2:F1 oracle 必带 boundary-saturation 与
  placement-rule assumptions(region_capacity_oracle.py:155),typed currentness 对非空
  assumptions 的 fail-closed 若留 B5,真实 F1 永远到不了 plugin):snapshot-native
  assumption 复验(对 snapshot 冻结值按 legacy 语义逐条验证)进 B2,校验通过才放行、
  失败 fail-closed;禁止删 assumptions 或用空-assumption 测试绕过。
- **MasterDomainProjectionV1 的 snapshot 侧投影前移 B2**(F1 plan 需 domain_fingerprint,
  原排 B3 时序倒挂):投影函数 B2 落地(F1 所需子集,domain-separated 前缀+canonical
  投影),master live 侧 resolve 复算仍留 B5(§2.6 不变)。
- **冗余 bound scope=typed fail-closed 收严**:legacy 接受「标 bound 但 ghost 实际不与
  R 相交」的非规范 Cut,typed 路径拒绝之;differential 中记为预期差异,不扩 FamilyPlugin
  seam。
- **semantic fingerprint 编码**:B2 给出实定义提案(domain separator+operation/参数
  schema/compiler version 的 canonical 投影),随批双审把关。
- **differential 语义锚**:现存 capacity=2/demand=2 用例不是合法 F1 proof(validator 要求
  demand>capacity),只作 plan-interpreter/lowering 边界测试;全链正例用 capacity=1;
  demand==capacity 验证 oracle 不发 cut。

**B2 双审补拍板(2026-07-11)**:

- **三项 typed accept-set 收窄追认为正式拍板**(codex#3 抓到实现未经拍板收窄,终审裁定
  追认而非回退——三项均 fail-closed 方向、生产正例不受影响,typed 边界哲学即收紧表示层):
  ①combinatorial proof 携带非空 LP 字段=拒(proof 类型纯净);②contributor pose_domain
  必须等于完整 pool(oracle 生产形态即全 pool,子集=非规范);③occupied cardinality gate。
  全部登记 differential 预期差异表;流程教训=实现方新增任何 accept-set 变化必须先上报拍板,
  哪怕方向保守。
- **assumptions/completeness 复验无条件化**(codex#1 BLOCK):复验不得受
  validator_version 分支控制——版本不匹配=直接拒绝,不是跳过安全义务的 seam;所有
  COMPILABLE/ENABLED 出口无条件执行。
- **MasterDomainProjectionV1 必含 slot 身份**(codex#2 BLOCK):mandatory slot 的
  canonical 行至少含 slot_key/slot_kind/domain-channel 字段(lowering 的 literal cache
  以 key 为身份,漏 key=alias 盲区);配漂移红测。
- **16-hex 全量核对先行**(codex#6):blocked/exterior/ghost 三项 legacy identity 全部
  核对通过后才允许计算任何 Stage-B 64-hex digest;顺序红测钉住。
- **differential 双拒矩阵**(codex#5):对 legacy 每项验证义务(capacity/demand/
  contributor/P(g)/cells_per_pose/gap)做参数化 tamper,断言 legacy 与 typed 共同拒绝;
  预期差异表只含正式拍板项。

### 5.2 F6(中)
domain_fingerprint 按 §2.4 v2 定义(covering facility_pools digest+slot 结构+pose-tuple
登记);master apply 重查 eligible baseline poses 保留,fingerprint 绑定使之成为「同一
真相的两次读」;differential 裁定,不足则退 plan 携带 pose IDs。

**B3 侦察补拍板(2026-07-11,三路并行侦察 file:line 实证后定;codex 通道中断期由主会话
fan-out 读者产出)**:

1. **preimage 捕获 = F1 减 ghost-policy 分支**:oracle(`shape_packing_hall_oracle.py:290-297`)
   改用 `capture_scope_identity_preimage_v1(state)` 一次捕获 + `compute_scope_identity_legacy_hashes`
   派生三 legacy 16-hex;`CutScope(..., identity_preimage=preimage)`。**不得**照抄 F1 的
   `GHOST_AGNOSTIC iff ghost∩R==∅` 政策——F6 永远 GHOST_BOUND(validator 语义硬约束,
   `shape_packing_hall.py:450-454`)。cert payload 的 `exterior_blocks_digest` 与 scope 的
   `exterior_blocks_hash` 必须出自同一次捕获(值同、不改 cert 字节)。
2. **无 scope-assumption 路线**:F6 legacy oracle 不产 assumptions(validator 对 boundary/
   placement 无条件源真值现算),typed 同构——scope.assumptions 保持空;**不扩**平台
   assumptions dispatch(`:1682`/`:1895` 两处 F1 硬分支不动),**不加**顶层
   `envelope.family=="shape_packing_hall"` 硬分支;F6 全部语义义务**无条件**收进 plugin
   `parse_and_validate_proof`(无任何 validator_version 条件化 = 无 version-seam 可绕,
   B2 codex#1 教训的结构性消除)。双审专项攻击面:证明 plugin 义务在 COMPILABLE dispatch
   下不可绕。
3. **snapshot-native 语义平价**:typed validator 复验 legacy 12-phase 全部义务,数据源换
   snapshot——partition 重算读公共 `snapshot.ghost_cells ∪ snapshot.exterior_blocks`
   (F1 先例);静态读集走 `F6HallInputs`(B1 已铺,**不扩字段**;pose-baseline 归属由
   projection 的 occupied_cells 派生,不需要 pose_occupied_cells 进 inputs)。cert 14 字段
   闭集解析不变(不动 cert_schema);`exterior_blocks_digest` 照验但重算源=snapshot 数据
   (单一来源,禁两套 digest 约定并存)。
4. **region_kind 收窄追认**:`_validate_plan_parameters` 的 `shape_packing_hall_le` 分支从
   「非空 str」收紧到闭集 `{left_baseline,bottom_baseline}`(legacy step_8 `:1505` 平价对齐,
   属拍板授权的 fail-closed 对齐、非私自收窄)。
5. **projection 另发 F6 子集**:新增 `family_subset="shape_packing_hall"` 的
   MasterDomainProjectionV1 投影,**不改** F1 那份(防 F1 fingerprint 漂移);复用 builder
   helper,含 pose-tuple 登记+occupied cells(baseline 归属可派生);fingerprint 编码平行
   F1 先例,domain separator/字段序等编码细节随 B3 双审把关。
   **semantic fingerprint 编码定格(2026-07-11 追记)**:codex 中断前的设计备注事后送达,
   经与 B2 落地实现逐项核对一致(`region_capacity_typed.py:42,348-377`),升格为正式编码规格——
   前缀 `zmd.semantic-fingerprint.v1:` + 完整 SHA-256;projection 覆盖 compiler_version、
   family、operation、parameters+parameter_schema、model_scope(domain_fingerprint/
   ghost_policy/ghost_rect_digest)、snapshot_source_digest+snapshot_artifact_identities;
   **排除** cut ID、时间戳、oracle 名称、raw proof bytes;编码走平台共享 type-tagged
   canonical 原语(`_canonical_node`+`_domain_digest`,拒 NaN/Infinity)。F6 的
   `shape_packing_hall_semantic_fingerprint_v1` 照此模式,替换 family/operation/
   parameter_schema 三处族相关值。
6. **registry 三件同批**:F6 row(`typed_platform.py:1337-1346`)翻 COMPILABLE + 正式
   validator/compiler version 常量 + plugins 挂 `shape_packing_hall_typed`;**不升 ENABLED**
   (B6 owner 门)。
7. **测试借名统一迁 cutset**:B2 中性化把机制测试借到了 F6 名下,B3 落真 plugin 必撞——
   借名 helper(typed_platform 测试 `_make_region_cut:273`/`_plan:401`/`_capability:441`、
   contracts `_make_region_capacity_cut:586`/probe plan `:727` 等)默认 family 统一迁
   **cutset(F2)**:geometric、永久 LEGACY_DIAGNOSTIC、无专门分支,B4(F7)及以后不再撞;
   三分支代数的 CutRejection 臂迁 cutset 后走「legacy diagnostic family cannot enter typed
   dispatch」= 跨批稳定拒绝源。生产 registry 断言三处同步(`_EXPECTED_STAGES:128`/
   nine-family mirror `:921`/replay-step8 一致性 `:974`)。snapshot_layer 的真 F6 输入测试
   **不迁**(非借名)。
8. **differential 拍板**:F6 恒 ghost-bound → 走 F7 的「anchor 自由=休眠 FEASIBLE→钉
   anchor→INFEASIBLE」范式(`test_step_8:396-440`);FEASIBLE 对照侧必须 master 级构造
   (抬 capacity 或 anchor 自由),**禁**用等号 cert(`total_packable==region_demand` 是
   validator unsound)当正例;fixture 的 1×L pose 必须整 body 水平贴 baseline(master
   `_on_baseline` 只计全贴 pose,`exact_coordinate_master.py:8163`),否则空 terms 被拒;
   `test_step_8` 现无任何 F6 用例=从零建;`test_family_shape_packing_hall.py` 的 happy-path
   cert 已逐谓词核为合法 proof,可直接作全链正例。
9. **连锁提醒**:动 oracle = sealed proof 生产文件 → golden digest/frozen-witness 重钉
   可能触发(B2 `fbc315a` 同类,跑全量测试暴露);新 plugin 文件进 checker floor + preflight
   mypy targets;两个结构 checker 对表后自钉最后。

**B3 双审补拍板(2026-07-11,opus BLOCK 2(均为计划内 reseal 项)/codex BLOCK 2+HIGH 2+MEDIUM 1
全实证;终审裁决)**:

1. **literals 空 tuple gate(codex#0 修复拍板)**:legacy F6 要求 `cut.literals is None`
   (空 tuple = schema_err),但公共 Cut 层 `_has_literal_payload(()) == False` 使 adapter
   framing 丢失 None/() 区别 → `literals=()` 的旧版非法 cut 在 typed 全链产 CompiledCut
   (接受集合真放宽,复现坐实)。拍板:**adapter 层通用 gate**——`cut_to_envelope_v1` 的
   geometric mode 判定严格要求 `literals is None`,`()` 一律拒(信息在 framing 丢失前拦截);
   修复方须核对 F1 legacy 对 `literals=()` 的行为——若 F1 legacy 亦拒则是平价对齐,若 F1
   legacy 接受则该 gate 对 F1 构成 typed-only 收窄、照差异表规程登记;F6/F1 各补
   「legacy 拒 + typed 拒」双断言 differential 红测。
2. **ghost-bound 义务声明式前移(codex#1 修复拍板)**:`parse_and_validate_proof(proof_payload,
   snapshot)` 协议看不到 scope,「义务全进 parser」对 scope 形态义务不可实现;现状靠 compiler
   产 bound plan 后的 equality 巧合补拒,合法 VALIDATED capability 配置(在 compiler 前
   返回 ShadowValidated)可跳过。拍板:**FamilyCapability 加声明式字段**(如
   `requires_ghost_bound: bool` 或等价 ghost-policy 约束),在 `_validate_scope_currentness`
   通用层(一切出口的共同前置)检查——capability 数据驱动,不是 family 字符串硬分支,
   与拍板 2「无顶层 family 分支」的精神一致(该拍板防的是分支蔓延与 version seam,不禁
   声明式平台机制);F6 声明 True,F1/F5 保持允许 agnostic;补 VALIDATED stage 下的绕过
   红测;现有锁在 compiler boundary 的测试改锁 scope 阶段。
3. **accept-set 差异表扩容(codex#2)**:B3 交付登记的三项之外,至少还有 preimage 内部
   不一致拒、外层 cert_kind 漂移拒、`payload_schema_version != 1` 拒、quarantine 拒等
   typed-only 收窄未登记——全部方向正确(fail-closed 防伪,授权保留),问题仅在登记完备性。
   拍板:差异表按「completeness 义务」维护——**每一处 typed adapter/plugin 的显式拒绝
   分支都必须对应差异表一行或 legacy 平价说明**,本批补齐并逐项配 differential 用例。
4. **测试攻击点修正(codex#3/#4)**:validator_version 绕过红测的攻击目标从
   `Cut.validator_version`(audit-only provenance,不控制任何分发)改为
   `registry.capabilities[family].validator_version`(真实分发控制源);cutset 三分支
   探针 fixture 依赖键改用生产 canonical 八键,断言收紧到 `stage=="registry"` + reason
   文案(现命中前置 scope 拒绝分支,锁错臂)。
5. **计划内 reseal 项(opus#0/#1)**:checker v99 floor 三文件 drift + 新 plugin
   `shape_packing_hall_typed.py` 未登记 floor——按既定分工归 team-lead 终审 reseal 连锁
   执行(oracle/typed_platform/state_snapshot 重钉 + 新 plugin 与 F1 先例同格入 floor +
   checker 自钉最后)。
6. **留痕**:codex 的 F6 legacy 12-phase vs typed 逐阶段映射全表与十二攻击面逐项结论
   存 workflow 转录(wf_8a9f65dd-b7b journal),不复制入规格。
7. **修复批新收窄追认(scope.exterior_preimage_snapshot_currentness)**:codex 修复中新
   发现并直接落地的 typed-only 收窄——cut 携带自洽但相对 snapshot 过时的 exterior preimage
   (删元素+重算 hash 保持内部一致)时,legacy 全链接受(validator 只对 cert digest 与
   state 比,不查 scope 身份新鲜度),typed 在 scope 阶段拒 "scope exterior-block identity
   is stale"。终审**追认为正式拍板**(fail-closed 方向,拒绝对旧世界签发的 cut,回退反而
   放宽 TCB;已按差异表新规矩登记 audit 行+专项测试)。流程注记:实现方本应「先报后动」,
   实际动后随交付上报——与 B2 三项收窄同型处置,追认不豁免流程规矩,再次重申。

### 5.3 F7(中到大)
plan 带 `blocked_cells_digest`,binding 带本体(resolver 从 snapshot 冻结值复原+digest
校验);runtime master coverer gate(:7988-8011)保留为 master 域独立防线。M2 合并见 §6。

**B4 侦察补拍板(2026-07-11,codex 八问侦察 file:line 实证后定)**:

1. **零扩面确认**:`F7PowerInputs` 已覆盖 legacy 八段复验全读集,不扩字段;两套 CoverSet
   (full/ghost-only)从公共 snapshot 几何计算,固定 70×70 平价(不读 target dimensions,
   legacy 没读);不扩 cert 闭集、不扩 assumption dispatch。F7 恒 ghost-bound
   (oracle :189/validator :182/旧 Step 8 :1469 三处一致)→ **`requires_ghost_bound=True`**
   (B3 字段直接复用);无 assumptions → F6 无条件 plugin 复验路线沿用;借名残余=零
   (B3 迁 cutset 后无漏网),B4 零搬迁。
2. **pole_radius 数值平价**:legacy 接受 JSON `5` 与 `5.0`——typed parser 归一 float
   接受两者(只收 exact float/int 均为非平价收窄),differential 配 int/float 双正例。
3. **literal slot_index(条件拍板)**:legacy 只核 group/pose 忽略 slot,typed adapter
   现强制 slot 0(:1498,通用 literal frame 机制)。实现方先核实生产 oracle 的 slot 值域:
   **恒 0 → 保留通用强制+登记 typed-only narrowing**(不动通用机制);若存在非 0 →
   停手回报重拍。
4. **Frozen bundle raw 类型**:核实 bundle builder 入口现状——若冻结归一(Mapping→dict)
   会让 typed 接受 legacy 拒绝的非 JSON 容器,则在**归一前**加 JSON-native admitted-domain
   检查(fail-closed,bundle 入口级约束非 F7 特有);若 builder 已拒则零工作,报告确认即可。
5. **B3 通用收窄继承**:missing/bad/stale preimage、schema v2、quarantine、外层
   cert-kind/exterior drift 等 typed-only 拒绝,F7 差异表**逐项列出**并各配 differential
   (B3 完备性义务规矩:每处显式拒绝分支对应差异表一行)。
6. **B4/B5 边界与 digest 校验分层**:B4 产 plugin/plan/projection,sole resolver 与正式
   Step 8 mutation wiring 留 B5(§7 边界不动);校验分层=resolver 核
   `digest(binding.blocked_cells) == snapshot.blocked_cells_digest`(body↔snapshot),
   Step 8 typed lowering 核 `plan.blocked_cells_digest == digest(binding.blocked_cells)`
   (plan↔body)——B4 的 plan digest 必须从 snapshot 可信 `ghost_cells ∪ exterior_blocks`
   派生(:1355),**禁**从 cert 的 exterior digest 拼装。
7. **F7 projection 含 canonical coverer rows(风险拍板)**:侦察实锤——facility-pool
   projection 绑原始 pools 但绑不住 live `_power_coverers_by_template_pose` 派生缓存
   (建模后删改派生表,pool fingerprint 不变而 runtime gate 看到更少 coverer)。拍板:
   新增独立 `family_subset="power_hitting_set"` projection(不动 F1/F6 冻结字节),
   **显式纳入 snapshot 侧规范派生的 coverer rows**(needs_power groups+pools+pose 序+
   occupied/power_coverage_cells+power_pole pool+双向 pose registration);动态 blocked
   mask 不入静态 projection(归 plan digest+binding 本体);master live 表对比留 runtime
   gate(第三防线)与 B5。fingerprint 照定格模式换族值。
8. **blocked digest 公共原语**:snapshot 与 typed_platform 已各有私有编码、B5 resolver
   将成第三消费者——B4 顺手抽 **versioned 公共 digest primitive**(落点实现方提案,
   双审把关),消除三份实现漂移面。
9. **differential 从零构造**:现有 Step 8 F7 world 六坑(facility_cells 与 pose 错位/
   needs_power=False/无生产 power rules/假 hash 无 preimage/anchor 与 blocked body 分裂/
   coverer table 手工注入)不能直接套 typed adapter——B4 fixture 必须 bundle-backed+
   生产八 hash+真实 oracle-v2 capability;最低矩阵含:双 CoverSet 空/非空、missing/empty/
   live/dead coverer、condition false/true、anchor 范式、pole_radius int/float 双正例、
   preimage/exterior/schema/quarantine/cert-kind tamper、projection drift(powered pool/
   pole occupied/coverage/order/coverer row)、non-powered 噪声不变性。

**B4 双审补拍板(2026-07-11,opus BLOCK 1(计划内 reseal)+2 LOW / codex BLOCK 1+HIGH 1+
MEDIUM 1 全双复现;codex 通道中断,修复由主会话执行;终审裁决)**:

1. **JSON-native 原子冻结(codex#0 修复拍板,本批最重)**:B4 落的入口校验是「先校验后
   冻结」两次遍历——①TOCTOU 窗口(校验通过后、冻结前替换容器,race 实测可触发);
   ②深冻结本身宽容(接受 tuple/set/宽泛 Mapping),而 lifecycle 的 source digest 对
   list/tuple 归一同值、legacy validator 却要求严格 list——「构造后把 facility_pools
   的 list 换 tuple」即得 legacy 拒/typed 编译通过的真放宽(双复现坐实)。拍板分层修复:
   (a) `frozen_artifacts.py` 把校验与冻结合并为**单次原子遍历**(每节点验 exact
   JSON-native 即冻结,tuple/set/非 dict Mapping 一律拒);(b) `state_snapshot.py`
   builder 读 state 数据的入口加同款 exact JSON-native fail-closed(挡「bundle 建成后
   state 侧容器形态漂移」——content digest 对类型不敏感,类型校验必须在读取点自立);
   不动 lifecycle 的 source digest 语义(改 digest 编码=全量 pin 重钉,收益不成比例,
   两个入口 fail-closed 后非 JSON 容器进不了 typed 数据面)。
2. **audit 表第 13 行(codex#1)**:`scope.required_dependency_set`(typed 精确匹配
   依赖集合 vs legacy 不查)登记为 typed-only 收窄+missing/extra dependency 双
   differential(锁 stage='scope'+reason);比对基准从 `_PRODUCTION_V1_ARTIFACT_DEPENDENCIES`
   权威定义派生,废除「两份硬编码集合互比」的自证形态。
3. **断言收紧(codex#2+opus#1 合并)**:八组 joint tamper 与 missing-preimage 测试
   废除 `_typed_rejects` 布尔合并,逐用例锁 typed 精确 stage+reason(或可辨识子串)
   与 adapter 异常类型+消息,对齐同文件 CoverSet/ghost/exterior 测试的锁定标准。
4. **needs_power=False 联合拒绝(opus#2)**:补 legacy(unsound)+typed(proof 拒)
   联合用例,补齐 `plugin.snapshot_group_and_template` legacy-parity 行的 differential。
5. **计划内 reseal(opus#0)**:B4 四个 sealed sink(frozen_artifacts/power_cover_oracle/
   state_snapshot/typed_platform)v99 floor+sink 登记重钉+新 plugin 入 floor+checker
   自钉,归主会话终审执行。

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
- **typed F5 validator=语义等价锚(B1.5 双审 codex#0,BLOCK)**:typed 路径必须完整
  执行 legacy F5 validator 的全部义务——oracle registry 解析+version 严格核对+
  `query_liftable` 复验且**仅 INFEASIBLE 可产 ShadowValidated**;弱于 legacy 的
  「结构校验即 shadow」被裁定为语义不等价(codex 双复现:registry 清空/FEASIBLE
  oracle 下 legacy 拒、typed 过)。snapshot 增 F5 family_inputs(state_snapshot.py
  扩展+re-pin 随批 reseal);legacy-vs-typed differential 五形态钉死(registry-missing/
  version-drift/FEASIBLE/TIMEOUT/exception)。完整复验落地前不得产 shadow。

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
| B2 | **F1 纵切**(v3 重排,二轮 BLOCK #3:v2 把 typed validator 全推 B5 导致 B2-B4 的 differential 链断头——单入口无 validator 产不出 CompiledCut):F1 parser+typed validator+compiler+registry 升 COMPILABLE+differential 全链;**与旧 raw 路径并存,生产链不动**(benders 编排零改动);含 §5.1 B2 补拍板四件(ScopeIdentityPreimageV1/assumptions 复验前移/投影 snapshot 侧/收严) | **范围修正(B2 侦察)**:非纯新文件——触及 pinned `lifecycle.py`(CutScope carrier)+`region_capacity_oracle.py`(捕获点)+`typed_platform.py`(adapter/currentness/registry),reseal 随批(floor+sink+自钉) | 同上 |
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

**B5 侦察补拍板(2026-07-11 晚,三路并行侦察 file:line 实证后定;codex 通道中断,侦察由
主会话 fan-out 产出)**:

1. **正式启用拆批**:B5a=functional rewire(resolver+plan interpreter+编排三路 match+
   step_6/7/8 全签名迁移+replay 双表/DiagnosticResult/store 切断(PIC-6 §4.2 处置)+
   F5 lifecycle 分支删除+全部测试语料迁移+编排层等价 differential);B5b=AST lockdown
   (master add_* 双层私有化 §4.10+precheck 前移 §4.11+AST allowlist 钉+无调用者的
   `add_pattern_nogood_cut` 物理退役)。各自完整 reseal。
2. **切换点=方案 X(编排层直切,§4.7)正式确认**:生产双跑对照方案否决(违反纪律①
   「并存期 typed 不得进生产入口」),对照价值下沉差分测试;「只改 step_8 内部」方案
   否决(重现风险 #10 verifier-过-compiler-拒缝)。侦察实证:typed 链当前**零生产消费者**
   (grep 全仓去测试为空),B5a 是首次通电,无隐藏迁移面。
3. **plan interpreter 落点=新文件 `src/cuts/typed_apply.py`**:统一 operation-dispatch
   (`region_capacity_le`/`shape_packing_hall_le`/`power_pose_exclusion` 三行表,与 master
   方法一一对应;F5 无 operation=类型层无 apply 路径),收 `CompiledCut`+`ModelScopeBinding`;
   runtime 材料(CP-SAT condition_lits/F7 raw blocked_cells)由 resolver 从 ghost 上下文
   与 snapshot 冻结值供给,interpreter 在 apply 处复算 digest 与 `plan.parameters
   ["blocked_cells_digest"]` 比对(§2.6 三连+§5.3 拍板 6 分层落点)。新文件=TCB,
   无条件进 floor+mypy strict targets(B1 纪律)。
4. **resolver(`lifecycle.py::_resolve_model_scope_binding`)**照侦察六步清单实现
   (agnostic 短路/bound 按 digest 定位 rect+u_var 对象身份/blocked_cells 从
   `snapshot.ghost_cells ∪ snapshot.exterior_blocks` 复原/live master 复算 domain
   projection/snapshot digest 现场算/私有令牌构造);**blocked_cells 复原语义必须与
   benders 旧 `ghost_blocked_cells` kwarg(=ghost_cells∪exterior_blocks)字节一致**,
   differential 锚死。step_8 签名 `(compiled_cut, master, *, scope_binding)`(§4.6 的
   `:1163-1169` 行号已 stale,现址 `:1363-1369`)。
5. **F5 收口**:B5a 删 lifecycle F5 step_8 分支(:1533-1573),`ShadowValidated` 消费=
   `stats["cut_framework_attach_last"]` 新增与 attached/rejected 平级的独立
   `shadow_validated` 桶(common-mode-untrusted 标签,不进 attached、不进
   `coordinate_framework_cut_count` 预算);F5 不 mutate master 升级为类型不变量
   (ShadowValidated 无 plan 字段,结构上进不了 interpreter)。**PIC-2 语义缝随删除
   一并消失**(不再存在 step_8 放行 agnostic F5/master 拒空条件的不一致);exploratory
   剪枝变弱、soundness 不变,规格 §5.4 既定取舍。
6. **哨兵耦合处置**:B0 五哨兵的 xfail 条件=resolver 符号缺失,B5a 落地后 1-4 应真转绿;
   哨兵 5(§4.11 原子性)引用 `_lower_region_capacity_cut`(B5b 符号)——B5a 内核实其
   激活行为,若红则把其 xfail 条件拆分为「_lower_ 符号缺失」(指向 B5b,非骨架作弊);
   拒绝异常的精确类型/错误码 B5a 定稿并回写 §2.9。
7. **文件清单修正**:port_exposure.py(F3)为疑似第 17 pinned——§7 三 legacy evaluator
   清单漏列而 §4.2 的 legacy 四族含 F3;开工 impact 扫描显式确认。16 文件中 5 个 sink
   (lifecycle/benders_loop/typed_platform/exact_coordinate_master/master_model)双重
   reseal(floor+sink JSON),11 个 floor-only;新增 import 若把 typed_apply.py 拉进
   close-kernel import-time 闭包(:13180-13185)必须同批入 floor。
8. **门控不变量**:B5 全程不碰 unsafe-map 条目与 `check_p1_2` 的成对登记(:12638-12639),
   翻转=B6 owner 仪式;certified 不可达主锚=`test_v62_candidate_frontier_contract.py:173-208`
   (pre-session 阻断,与编排内部无关,B5 后仍绿);`_cut_framework_attach_enabled`
   docstring 与 unsafe-map 注释的表述校准随 B5a 批做(校准非翻转)。
9. **收口纪律**:B5a/B5b 各自收口实跑双 checker(含 `check_strong_status_write_allowlist`
   核实零新增 CERTIFIED/INFEASIBLE writer,风险 #10);telemetry taxonomy 4 类→9 类
   (+compiler/plan-validation/model-scope/master-rejection/shadow)wiring 测试同步。

**B5a 实现定稿追认(2026-07-11 夜,两子块交付后终审;实现=主会话 fan-out opus,codex 通道
中断期)**:

1. **step_7 incumbent violation filter 正式退役(§3.1 回写)**:typed `step_7_evaluate_cut
   (compiled_cut, snapshot)` = digest attestation(ATTACH 即真),不复刻 legacy 的
   「cut 是否切掉当前 incumbent」过滤——validated-but-dormant cut 照 attach。裁决理由:
   ①soundness 不变(完整验证过的 valid inequality,agnostic=物理真/bound=ghost 条件化,
   多挂无害;FP=0 义务在 validator 层把关);②在编排层复刻 filter=手写三族数学第二实现,
   新增攻击面收益为负;③纯剪枝效率/预算消耗差异——**注记:若批 C(PIC-4)prod-scale
   实测显示 dormant cut 挤占 2000 预算严重,再立「typed relevance evaluator」小批**
   (snapshot.selected_poses 已冻入,材料齐)。telemetry 的 `attach_timing` 桶保留。
2. **step_6 定稿(§3.2 回写)**:`step_6_attach_scope_check(compiled_cut, snapshot)` 三查
   attestation(exact CompiledCut/snapshot_digest 相等/scope_digest 与 plan 一致性重申),
   ATTACH|QUARANTINE 二值,保名保 checker 委托结构。
3. **resolver family 判定(§2.6 回写)**:3 参签名下 family 由 `model_scope.domain_fingerprint`
   匹配 snapshot 三个缓存投影字段判定(可信侧),live master 复算该 family 投影做 drift
   检测——「按 plan.family 选投影」的等价落地。
4. **编排异常分层**:仅 `cut_to_envelope_v1` 的 TypeError/ValueError 入 `rejected["adapter"]`
   桶;bundle/snapshot/registry 构建异常、resolver ValueError、step_8 全部异常**传播**
   (TCB 故障不洗成 per-cut rejection)。replay 侧 CutRejection stage=="scope"→HOLD,
   其余→QUARANTINE `typed_rejected_{stage}`。
5. **合法遗留(B5a-transitional,9 skip)**:F6/F7 直调测试的完整 typed-chain 迁移
   (需 domain-consistent snapshot↔live-master fixture)+F5 生产 oracle-registry e2e
   一例——留给 B5b 或收尾子块;F6/F7 typed 面已由各自 stage_b 测试全绿覆盖,resolver
   的 F6/F7 live 投影若 byte 不符只会 fail-closed 过度拒绝,无 soundness 风险。

**B5a 双审裁决(2026-07-11 夜,双 opus:设计位 AGREE_WITH_AMENDMENTS/攻击位 PASS,
codex 通道中断期)**:攻击位对七大面(resolver 错配/三连校验绕过/plan 篡改/ShadowValidated
逃逸/replay 活化/TCB 异常吞没/门控可达性)全部构造实跑复现,零 master mutation,无放宽点;
step_7 violation filter 退役论证经专项复核成立。amendment 处置:

1. **MEDIUM(已修)**:`store.on_ghost_rect_changed` 的 `build_replay_context` 原在
   per-cut 循环内(违反 §4.8「每 transition 一次」+ replay 自身 docstring)——已 hoist
   到循环外(loop-invariant,guard 测试注入分支),纯效率项,correctness 不受影响。
2. **LOW×2(双位共同点名,确认为 B5b 预期缺口,B5b 义务收紧)**:ModelScopeBinding
   在 B5a 只有 construction token 软闸(module-level object(),in-process import 可偷;
   step_8 三查对「字段照抄 plan 的伪造 binding」是同义反复,残余伪造载荷=condition_lits
   错绑 u_var)。这正是拍板 1 把 AST lockdown 分给 B5b 的既定分层——**B5b 义务由此收紧
   为三条**:①AST allowlist 必须把 `_build_model_scope_binding` 的唯一合法 caller 钉死
   (`_resolve_model_scope_binding`);②token 不可达红测(除 resolver 外任何构造路径必红);
   ③master add_* 双层私有化(原 §4.10)。缓解已在位:typed_apply 复检 blocked digest+
   ghost-bound 空 condition_lits 拒绝;框架 certified-disabled。
3. **LOW(文档)**:§7 拍板 9 的「9 类 telemetry」清单被拍板 4(异常传播不落桶)supersede
   ——实际桶=adapter/registry/envelope/scope/proof/plan/attach_timing+shadow_validated
   平级字段,resolver/step_8/master-rejection 异常**传播**而非计数;运行时正确,以本段
   与「实现定稿追认」第 4 项为准,拍板 9 原措辞不再单独作数。
4. 注记两条:reseal drift 集含 `src/cuts/__init__.py`(typed_apply 导出面),终审一并
   处理;resolver family 判定依赖三族 projection 的 family_subset 域分离(攻击位验证
   今天成立)——**新增族落地批必须保持 projection 域分离**,违反即 family 误判
   (fail-closed 方向,登记为结构义务)。

**B5b 开工拍板(2026-07-11 夜,双读者侦察 A=AST/私有化面+B=fixture 面到齐后定,
八项)**:

1. **AST caller 钉(义务①②合并)**:`"_build_model_scope_binding"` 加进
   `_PRIVATE_CONSTRUCTION_SYMBOLS`(test_stage_b_typed_platform.py:1772),expected
   Counter 加恰一条 `("_build_model_scope_binding","src/cuts/lifecycle.py",None,
   "_resolve_model_scope_binding"):1`——现有 collector 机制自动执法,锁死工厂唯一
   caller。运行时 token 拒绝红测已在位(:2346),义务②无新增运行时内容。
2. **add_* 双层改名(§4.10)**:facade(master_model.py:12147/12174/12201)与 backend
   (exact_coordinate_master.py:7823/7942/8032)三方法改 `_lower_region_capacity_cut`/
   `_lower_baseline_packing_cut`/`_lower_power_pose_exclusion_cut`(命名统一
   `_lower_<原名去 add_>`,与哨兵 5 的 F1 锚一致);`MasterModelLike` protocol
   (lifecycle.py:1254-1280)三声明同步;typed_apply.py 调用点(:55/:61/:75)同步。
3. **F5 `add_pattern_nogood_cut` 物理退役**:facade(:12228)+backend(:8104)+protocol
   声明(:1280)三处删除(生产死代码,typed_apply 无 F5 operation;e2_harness.py 研究
   工件引用不算生产面)。
4. **getattr 旁路 AST 拒绝(B5b 主工程量,悬念 1 拍板)**:新 AST 逻辑拒绝全仓
   `_coordinate_delegate` 属性获取旁路,facade 三个 `_lower_*` 方法作用域走
   **owner-scope 豁免**(照 `_PRIVATE_SYMBOL_OWNER_SCOPES` 先例,:36-39 机制)。
   双审重点专项。
5. **§4.11 precheck 前移**:落点=exact_coordinate_master.py backend(与改名收敛为
   同一方法:backend `_lower_*` 即原子版)——全失败分支前移到首次 mutation
   (`_pose_present_literal`)之前,mutation 段零失败分支;F1 残留样例=:7887
   `if not group_terms: return False` 在前组 presence 字面量已建之后。三族同模式;
   哨兵 5 只锚 F1,F6/F7 原子性由新增 differential 测试守(proto+内部 cache 字节
   不变,悬念 2 处置)。
6. **F6/F7 8 skip 迁移与改名合批**(侦察 A 建议采纳,碰同一批测试文件免二次改):
   弃 test_step_8_shape_packing_hall.py 的 `_build_port_master` 自建世界,改从
   stage_b 文件 import 已证同源 fixture(投影等式测试 :1191 为证),套 F1 三行骨架
   (resolver→step_8→build_stats 断言);6 个下降类机械迁移,2 个 fail-closed 类照
   F1 三先例(:184/:200/:213)重定位拒绝阶段、只保留 step_8 边界独有断言;9 处测试
   `add_*` 直调点+`_SpyMaster` 假方法名同步改 `_lower_*`。侦察 B 悬念 3(负例投影
   drift 落点)实现时逐例确认拒绝阶段并断言之。
7. **第 9 个 skip(F5 e2e,attach_wiring:636)不进 B5b**(悬念 3 拍板):F5 需
   real sub-problem oracle registry 接线,归批 D(RFC-002 F5 verifier 线)——B5b
   是 AST lockdown 收尾批,F5 apply 已物理删除,e2e 价值在 F5 转正批才成立。
8. **reseal 集预估**:exact_coordinate_master.py(sink 双重)+master_model.py(sink
   双重)+lifecycle.py(sink 双重)+typed_apply.py(floor)±`src/cuts/__init__.py`;
   AST allowlist 测试文件是执法点不 sha-pin;strong-status allowlist 预计零漂
   (replay 条目与 framework add_* 无关)但收口必须实跑双 checker 复核(悬念 4=
   纪律项)。

**B5b 双审裁决(2026-07-11 深夜,双 opus:设计位 AGREE_WITH_AMENDMENTS/攻击位 PASS)**:
设计位逐分支对照 HEAD 证实 precheck 前移 accept/reject 集合逐点相同(两新纯谓词与原
mint 版 None 条件精确镜像,`_slot_can_take_pose` 纯读);攻击位六攻击面全跑(反射绕过/
accept-set 撬动/Counter 时序/F5 退役残留/coverer 碰撞构造/门控),F5 存量记录经 replay
=HELD/QUARANTINED 不崩溃,coverer 不一致但投影 byte-equal 的输入构造失败。五条 LOW
归并处置:

1. **F7 原子性测试无判别力(已修)**:F7 从无 mint-then-fail 路径(legacy None 分支
   全在 mint 前),§4.11 前移对 F7=vacuous no-op——测试改标签为 clean-rejection
   回归钉,docstring 明记「无行为 delta,判别性 differential 是 F1/F6 两个」。
2. **AST 守卫威胁模型边界(已修,双位共同点名)**:collector+caller pin 只捕自然
   形态(Attribute Load/字面 getattr);attrgetter/字符串拼接/变量名/`__dict__` 逃逸
   ——docstring 明记 TRIPWIRE 定位(绿测≠不存在证明),硬拦截=unsafe-map+facade
   结构。当前生产零动态反射使用(双位 grep 复核)。
3. **F7 subsume 非严格等价(已修措辞)**:well-formed 分歧全部先在 §2.6 拦截,但
   corrupt-table 角落(越界 coverer index)§2.6 IndexError vs gate 干净 return False
   ——两处「subsumed/unreachable/dead code」措辞改为准确表述;**gate 保留**
   (防御纵深+非 typed caller 唯一防线),拒绝阶段迁移不构成 accept-set 变化
   (§2.6 拒绝集 ⊇ gate 拒绝集,先阶段更严)。
4. **`_lower_*` 无 runtime 守卫(注记,不修)**:对比 snapshot 的 token 双层,facade
   `_lower_*` 只有 AST 层执法——这是 §4.10 的既定范围(AST 拒绝层级);runtime
   token 化登记为可选后续硬化,不排批(certified unsafe-map 兜底在位,发布时点
   硬化统一暂缓拍板 2026-07-06 适用)。

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
  **⚠ 2026-07-12 审计校准(文档实态外审 F09,取代上一行的绑定)**:B6 只保留**授权性**
  变更——unsafe map 翻转、红测预期翻转、release boundary 改写、owner promotion 本身;
  lock 与上层文档中**可机器核对的描述性事实**(B0-B5b 是否已落、registry/step_8 当前
  行为、sink 数、测试现值)必须随实现批即时同步,不得延期到 B6 攒着——否则最高权威在
  等 owner 门期间持续失实。修复批 β 已按此把 lock 的 cut-lifecycle 描述段校准到
  07-12 实态;该校准是事实同步,不是、也不得被解读为 owner 关门/promotion 动作。
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

- **B1.5 双审补拍板(2026-07-11)**:opus(PASS_WITH_NOTES,4 LOW)+codex(BLOCK,
  18 条:10 BLOCK+1 HIGH+7 LOW,含主动攻击实证)。traceability:

  | finding | 处置 → 落点 |
  |---|---|
  | codex#0 BLOCK(typed F5 缺 oracle registry/version/query_liftable 复验即产 shadow) | 采纳:语义等价锚+五形态 differential+snapshot F5 inputs(§5.4) |
  | codex#1 BLOCK(宽泛 except Exception 把 TCB 故障洗成 rejection) | 采纳:专用语义拒绝异常,其余传播(§2.5) |
  | codex#2 BLOCK(AST 门反射/pickle/子类假阴性可铸 exact CompiledCut) | 拆分:AST 扫描器强化(别名/反射常量/引用计数)进修复批;运行时反内鬼硬化(拼名 getattr/vars/pickle 篡改/子类覆写)按 owner 2026-07-06 拍板缓入发布硬化批,与 B1 token 残余同档 |
  | codex#3 BLOCK+opus#1 LOW(typed_platform 未进 checker floor) | 采纳=终审 reseal 计划内动作(主会话) |
  | codex#4 BLOCK(v1 scope identity rehash 16-hex 截断值) | 采纳:raw preimage 重算+legacy-only fail-closed(§2.7) |
  | codex#5 BLOCK(adapter 收非 v1 schema+静默擦 quarantine) | 采纳:==1 严格+quarantine fail-closed(§2.7) |
  | codex#6 BLOCK(FamilyPlugin 返回类型合同弱) | 采纳:精确标注+runtime 返回/arity 验证+负测 |
  | codex#7 BLOCK(CutEnvelope 不在全仓唯一性 AST 钉内) | 采纳:CutEnvelope 构造进全仓 allowlist |
  | codex#8 BLOCK(registry 跨表一致性 CI 钉缺失) | 采纳:meta-test(registry vs replay dispatch vs lifecycle step_8 分支) |
  | codex#9 BLOCK(strict mypy 27 错不可复现绿;preflight mypy 不含新 TCB) | 采纳:casts 清理(修复批)+preflight mypy targets 扩面(主会话终审) |
  | codex#10 HIGH(CutRejection 被要求私有=与规格冲突) | **驳回实现改动**:审计任务书笔误,规格为准——CutRejection 刻意公开(§2.5 消歧) |
  | codex#11-#17 LOW(纯函数性表述/Shadow 完整性/digest 攻击失败/registry 矩阵净/测试无空心/公开面净/并发漂移隔离) | 记录性:#13 补三攻击回归防漂移(修复批);#17=主会话自己的 CI 调参,已隔离 |
  | opus#2 LOW(CutEnvelope 调用面钉未落) | 并入 codex#7 处置 |
  | opus#3 LOW(token 模块全局可导入) | owner-deferred 同档入档(同 B1) |
  | opus#4 LOW(顶层类型违法 raise 而非三分支) | 符合 §2.5 异常边界(fail-closed 方向),B5 编排侧注意事项已在 §4.7 |

- **B2 侦察补拍板(2026-07-11)**:codex 纯侦察上报三个全链阻断缝(CutScope 无 raw
  preimage/F1 assumptions 被 currentness 全拒/domain_fingerprint 时序倒挂)+三小项。
  全部采纳,拍板落 §5.1 B2 补拍板段与 §7 B2 行范围修正;要点=方案 A carrier、
  assumptions 复验前移、投影 snapshot 侧前移、冗余 bound scope 收严、B2 非纯新文件
  (三 pinned 文件 reseal 随批)。
