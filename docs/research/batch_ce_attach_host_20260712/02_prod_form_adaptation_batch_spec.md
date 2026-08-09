# prod 形态适配批 — 设计规格(roadmap 台账#8;2026-07-14)

> 状态:设计定稿,待实现+对抗审查+reseal+双 lane。执行侧按台账#8「默认按推荐推进」开工;唯一 owner-only 门(B6 flip)不在本批。
> 权威根因记录:`01_batch_c_execution_plan_draft.md` §7 零头清账节 + cc_memory `prod-form-snapshot-fail-closed-gap`。

## 1. 问题(门6 prod 注入式演习坐实)

certified cut 框架的共享 snapshot 构建 `build_validated_state_snapshot`(`src/cuts/state_snapshot.py`)**无条件**在任何 family 生成/enablement 过滤之前构建 F1/F6/F7 三投影,F1 最先跑。F1/F6 投影经 `_master_domain_pose_registrations` 用默认 `master_scalar_coercions=False`(严格标量:`type(orientation) is str`、`type(anchor) is int`),而 prod frozen `candidate_placements.json` 的 `boundary_storage_port`(placement_rule=`left_or_bottom_boundary`,落在 `_F1/_F6_MASTER_DOMAIN_PLACEMENT_RULES`)其 `orientation` 是 **int 0**(实测全 136 pose 均 int)。→ F1 投影构建即 `SnapshotValidationError`,**整条 attach 在 prod 数据上 fail-closed 中止(所有族含 power 都到不了生成)**。

fixture 全绿是因为 fixture 手造 exact-str orientation,`str("x")==x` 幂等,严格与强转在 fixture 上结果全同,从没踩到真数据的 int。定性:fail-closed 方向、certified 默认关、零 soundness 风险,但 **flip 后框架在 prod 上每次 attach 都在 snapshot 处 raise = 空动作**。

## 2. 根因 = 投影未忠实镜像 live master

`_master_domain_pose_registrations` 的 docstring(state_snapshot.py:1111)明确其目的:"Mirror template pose registration without importing a live master"。但 live master 的 mode-token 构造 `_pose_mode_token`(`exact_coordinate_master.py:1195-1201`)对**所有族**一律 `str(orientation)`、`str(port_mode)`;anchor 处理(997/1024/1055 等)一律 `int(anchor.x/y)`。

即 live master 是**通用强转**的。F1/F6 投影的 `coercions=False`(严格 `type() is str`/`type() is int`)**比 live master 更严** = 不忠实镜像 = 潜伏 bug。docstring 里"F7 才镜像 live master 归一化"的表述不准:line 1195 是通用路径,不分族。

## 3. 修法 = 对称翻转两处调用点为 `master_scalar_coercions=True`

`_master_domain_pose_registrations` 函数本身不改(已支持该 flag、F7/power 已在用)。只改**三个调用点**的关键字实参:

| 文件:行 | 调用者 | 现状 | 改为 |
|---|---|---|---|
| `state_snapshot.py`:1285 | `_build_f1_master_domain_projection` | (默认 `False`) | `master_scalar_coercions=True` |
| `state_snapshot.py`:1369 | `_build_f6_master_domain_projection` | (默认 `False`) | `master_scalar_coercions=True` |
| `lifecycle.py`:1604 | resolver(live pools 投影) | `master_scalar_coercions=is_power` | `master_scalar_coercions=True` |

`bidirectional` 保持不变(state_snapshot F1/F6 保持默认 `False` 单向行格式;lifecycle 保持 `bidirectional=is_power`)——coercions 与 bidirectional 正交,F1/F6 单向冻结行格式不动。

**必须对称**:state_snapshot(frozen bundle 投影)与 lifecycle(live pools 投影)两侧必须同时翻转,否则真数据下一侧 raise 一侧成功 → 两投影不再相等 → 破坏 frozen-artifact 忠实性对账(`_validate_live_template_pose_cache`,lifecycle:1610)。这就是台账#8"双文件"的根据。

## 4. soundness 论证 + 对抗自检

**正面**:live master 通用强转(§2 坐实)→ 忠实镜像**必须**同样强转 → `coercions=True` 才是正确镜像,现状严格是 over-tightening。

- **幂等/无回归**:fixture 全为 exact-str/exact-int,`str("x")=="x"`、`int(5)==5` 幂等 → 投影 digest 逐字节不变 → 全部现存 cuts 测试(stage_b_*/lifecycle/…)绿、golden digest 不漂。**实现后必须实测投影 digest 前后一致坐实此点。**
- **prod 正确性**:int orientation 下 `str(0)="0"` = live master 注册的确切值 → 正确镜像(而非之前的 raise)。
- **对抗①(会不会合并 distinct pose 丢 soundness?)**:合并需同池内 `str(a)==str(b)` 但 `a≠b`(如 int 0 与 str "0" 共存)。(a) live master 自己就 `str()` 合并 → 投影合并是忠实、非背离;master 是 ground truth,它合并则据其 domain 建的 cut scope 也合并 = 一致。(b) prod frozen 每池 orientation 类型均一(实测 136/136 int),无混型碰撞。
- **对抗②(会不会放宽纳入 garbage?)**:`str(None)="None"` 等 → 但 live master 同样 `str(params.get("orientation",""))`,投影仍忠实于 master;冻结件"就是 master 所见的同一份数据"由 bundle digest / artifact_hashes 另行强制,coercions 不削弱它。
- **纵深防御**:方向从 fail-closed(raise)→ 正常 attach;即便投影有误,下游 oracle cert / replay / I1 独立复验 / supervisor seal 仍在;且 certified 下 F1/F6/F7 attach 仍禁用(本批为 B6 flip 后铺路,经演习验证),多层兜底。

**为何原作者写严格**:F1/F6 纵切(B2/B3)全用 fixture,fixture 恒 exact-str,"tighter is safer"的选择从未被真数据检验(= 批C 发现"fixture 手造 exact str 从没踩到")。

## 5. 测试计划(已落地,`test_stage_b_region_capacity.py`;全 cuts 855 绿)

**投影三部分**:`facility_pool_projection`(序列化**原始** pool——int→`["int",0]`、str→`["str","0"]`,故 int-form 与 str-form 数字本就不同,非"逐字节相等")+ `mandatory_slot_rows` + `template_pose_registration_rows`(走 `_master_domain_pose_registrations` 强转,int/str 都归一到 `"0"`)。等式只在 registration-rows 层与 consistent-pair 的 frozen==live 层成立。

- **幂等 golden(核心,无回归)**:全 cuts 套件 855 绿、无 golden 漂移。fixture 恒 exact-str/exact-int → `str()`/`int()` 幂等 → 投影不变。
- **state_snapshot 侧翻转守卫**:`test_f1_prod_form_int_orientation_snapshot_no_longer_fails_closed`——int/str 两形态 `build_validated_state_snapshot` 都产合法 sha256、不再 raise(翻转被撤则 F1 投影 raise、测试红)。
- **lifecycle 侧对称翻转守卫**:`test_f1_prod_form_int_orientation_live_projection_no_longer_fails_closed`——`_live_master_domain_projection` int/str 都产合法 sha256(翻转被撤则 `is_power=False` 严格路径 raise)。
- **双模式契约 + 强转等价**:`test_master_domain_pose_registrations_dual_mode_contract_intact`——`coercions=False` 仍拒 int(严格契约不变、证 call-site 翻转是唯一改动),`=True` 接受且 `int_rows == str_rows`(证 `str(0)` 与 `"0"` 归一到同一 registration 行)。
- **frozen==live 对账(真 step-8 等式)**:`test_snapshot_and_live_master_rows_share_one_domain_projection_schema` 参数化增 `prod_form_int_orientation`——consistent pair 下 frozen-bundle 投影 == live-master 重算投影逐字节相等(= resolver `_resolve_live_master_domain_projection` 的 domain-fingerprint 等式在真数据形态成立)。
- **回归**:`--slow-tests` 慢 soundness lane 全过 + `--full`(reseal 后跑)。

## 6. reseal 计划(代码定型后执行)

两文件均 sealed。reseal 链(sha 按 LF 字节 `git show HEAD:<f>|sha256`,绝不 write_text):
1. 定位并更新 `state_snapshot.py`/`lifecycle.py` 的 source_sha256 pin(V99 dict in checker + JSON sink_files[])。
2. 实测 `semantic_projection_sha256` 是否移动(仅改 kwarg 值、未加符号/token;若投影剥离这两文件的 sha 则不动,类比 layer-2 benders)——按实测结果决定是否更投影 pin + certified_artifact_contract。
3. checker 自 sha 最后算(改 V99 dict 后)。
4. 双 checker 绿(15/67/65/83 口径核对)+ 无旧 sha 残留。

## 7. 排期位置

批C 收口(已)→ **本适配批** → B6 flip(owner 手动)→ F5 转正批。不修则 B6 flip 是空动作(台账#8)。

## 8. 双对抗审查结果(2026-07-14)

**codex(soundness 攻击,security-diff-scan 只读技能):OVERALL 0 BLOCK / 2 CONCERN**
- ①域坍缩 SOUND:投影与 live master 同语义;live master 的 duplicate-coordinate gate(exact_coordinate_master.py:1897)拒碰撞,不会少建约束;完整 fingerprint 含带类型标签的原始 pool,`0` 与 `"0"` digest 不同。
- ③frozen vs live 对称 SOUND:resolver 仅识 3 fingerprint + 从 live 重算,step-8 fingerprint 比对**只 fail-closed 无 fail-open**。独立复现了"tiny master 未设 placement_rule → 选中域空"的测试覆盖瑕疵(与 opus 同发现,已修)。
- ⑤其它调用点 SOUND:穷举仅 F1/F6/F7/power + 共享 live extractor 四处全 True;真数据 66,405 pose 全 exact-int anchor、int orientation、无 normalized pose-tuple 碰撞。
- ②/④CONCERN(强转放宽输入 schema:接受 None/float/bool/dict orientation、anchor 接受数字串/bool/float):**codex 自判非 CERTIFIED bypass**——(a) 正是忠实镜像 live master(投影更严反而是本批要修的 bug);(b) 原始类型仍被完整 pool fingerprint 绑定;(c) 亲手构造嵌套值案例证实任何背离在 step-8 fail-closed;(d) prod 冻结件 100% int、schema 由 freeze-ritual/strict_json 另行保证。

**opus(镜像忠实性 + 完整性):OVERALL 0 BLOCK / 2 AMENDMENT**
- Q1 镜像忠实性 AGREE(逐字段对照 live master `_pose_mode_token`/anchor/footprint/mode_id 全一致)。
- Q2 完整性 AGREE(4 调用点非 3,F7 本就 True;真数据实测 orientation 是唯一非严格标量→翻转必要且充分;`boundary_storage_port` 同时 F1/F6-eligible → F6 翻转真 load-bearing)。非阻塞观察:occupied_cells 有严格/强转不对称,prod cell 100% int 故当前非缺口。
- Q4 reseal 范围 AGREE(数值实证 semantic_projection 剥离 source_sha256 → 不动 27cb3c86)。
- AMENDMENT 1/2(lifecycle 守卫空跑 + F6 无守卫):**已修**——lifecycle 守卫加 `placement_rule="left_or_bottom_boundary"` 真触达强转;F6 守卫 = parametrize shape_packing 对账测试增 int orientation。

**concern 处置**:codex ②/④ 定为已知非阻塞(忠实镜像的必然结果,冻结件 int-only 上不可发生,发生则 fail-closed;若要输入 schema 收紧应在 artifact/freeze 层做,归发布时点防蓄意内鬼硬化桶,非本批)。

**守卫硬化(消解 opus AMENDMENT,变体回退逐个坐实)**:撤 F1→region 两测试红;撤 F6→shape_packing F6 测试红;撤 lifecycle→region lifecycle 守卫红。三翻转均有 mutation-verified 守卫,再不能被静默回退。

## 9. reseal 执行记录

源 sha(工作树 LF,自算 == reviewer 独立算):
- `src/cuts/state_snapshot.py`: `bfa679fa…` → `7ff01d18c049e6b1d2fde89d72afdc7d190426fcd24c0b3175482e6141eb9796`
- `src/cuts/lifecycle.py`: `8f6c1489…` → `9b944572c3bc787317a2e9bfaaf4e3ce472ba8fd953269772b24535bbef1ac1a`

pin 面:checker V99 dict 两条(12965/12971)+ JSON lifecycle sink source_sha256(state_snapshot 不在 JSON)+ checker 自 sha(最后算)。semantic_projection 数值实证不动。certified_artifact_contract / strong-status checker 不引用这俩 → 不动。
