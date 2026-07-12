# B6 前置工程批:session-bundle 所有权 + sink 注册升级 + F-05 alias 追踪

- 立项:2026-07-12 晚(owner「先b6」——B6 线开工;flip 本身的 lock 前置未齐,先清工程前置)
- B6 线总排序(本批拍板,依据 lock:489 前置清单与 02_rfc §RFC-003 正交声明):
  **①本批(工程前置)→ ②批E(RFC-003:dedup+ledger+replay;flip 前置且是 PIC-4 的实测对象)→
  ③批C(PIC-4/PIC-5 生产层 prod-scale 实测)→ ④B6 flip(owner 手动门,promotion 包先备好)→
  ⑤F5 转正批(owner 排期,「与 B6 合批或紧随」;等 adapter 修复,五项清单=批D 规格 §5)**。
  「剩下两个」的顺序即:批E 在前、F5 转正在后。
- 本批三项 + 两搭车:

## §1 范围

1. **session-bundle 所有权**(Stage B 规格 §2.1 F02 校准段登记的 promotion 前 BLOCK):
   `FrozenArtifactBundle` 构造从每 `_maybe_attach_framework_cuts` 调用一次(benders_loop.py:8150-8161)
   提升到 session 级一次并复用,按 artifact digest/会话身份钉复用与失效规则;
   `ValidatedStateSnapshot` 仍 per-round(绑 per-round BState,α-1 内容绑定语义不变)。
   实现侦察进行中(scout-session-bundle),拍板待补:所有权宿主对象/缓存键/失效规则/触碰面。
2. **frozen_artifacts/state_snapshot 升完整 close-kernel sink 注册带 obligation**(α2 B6 清单①):
   两文件当前仅在 v99 floor 字节钉;升到 obligations JSON `close_kernel_contract.sink_files[]`
   完整注册。实现侦察进行中(scout-sink-registration),拍板待补:条目 schema/obligation 挂接/
   sink 台账 67→69/reseal 步序。
3. **F-05 delegate alias-dataflow 追踪**(α2 B6 清单②,纯测试侧):
   现行 `_coordinate_delegate_acquisition_use_digest`(test_stage_b_contracts.py:798-830)只封
   acquisition 语句形状,alias-then-write(`d = self._coordinate_delegate` 后独立 `d.model.Add(c)`)
   不追。**拍板(方案 A,digest 扩展)**:对每个「acquisition 以赋值绑定名字」的站点,在其
   enclosing function 作用域内收集全部引用该名字的语句(含嵌套 scope 保守纳入;重绑定后
   继续追新值来源不豁免),这些别名引用语句的规范化 AST 一并纳入 digest——任何新增/改写
   别名使用语句即红。与既有 seal 风格同型,封死 α2 攻击位描述的**一跳** alias 缺口(含嵌套 RHS 绑定,双审 amendment A);digest 常量重钉。传递多跳残留见 §3.3。
4. **搭车 F14**(文档外审 NOTE,β 裁定「下一个 reseal 批带掉」):frozen_artifacts:1
   「Session-scoped」docstring 在 item 1 落地后成为真话(不改注释改实现);benders_loop:8150
   「ONCE per attach round」注释随 item 1 改写;lifecycle/benders 其余旧 F5/round 注释实现时
   逐处核对订正。
5. **搭车小瑕疵**:05 规格 §6 标题「codex=第三视角」与正文矛盾 + 结尾「_(待填)_」——已随本批修正。

## §2 不做面

- B6 flip 本身(owner 手动门,前置未齐;promotion 包在批C 后另备)。
- RFC-003 全部(批E)。
- F5 一切转正面(批D 规格 §5 五项,owner 排期)。
- PIC-4/PIC-5 生产实测(批C)。

## §3 侦察拍板

### 3.1 session-bundle(scout-session-bundle 回报后拍板,方案 A=最小面)

侦察硬事实(file:line 已核):①`ExactSearchSession`(benders_loop.py:2172,普通 dataclass,per-process,服务多 ghost rect);`LBBDController` 每 ghost rect 新建(:9061)且当前**不持 session**,构造点作用域内有 `exact_session` 可穿线。②bundle 五输入(canonical_rules/candidate_placements=facility_pools/templates/instance_to_facility_type/artifact_hashes,:8154-8160 经 `_build_cut_framework_state` :7865)**全部 session 恒定**,逐 round 可变字段(ghost/selected_poses)不进 bundle→digest 全 session 恒定。③snapshot 绑 per-round 状态,仍每 round 构建(α-3 设计)。④~~benders_loop.py 非 SHA-pin~~ **侦察此条有误,实现期实测纠正**:benders_loop.py 除 needle 锚外**同时在 v99 floor 与 close-kernel sink 台账**(改动后 checker 双红实测坐实:sink hash drift + floor drift)——本批需完整 reseal 连锁(与 item 2 的 obligations JSON 改动合一次做)。⑤α-1 逐内容相等校验(state_snapshot.py:695-734)对复用 bundle 恒过且**兼作 fail-closed 失效闸**(陈旧 bundle→SnapshotValidationError);α-5 memo 是构造内部行为与复用零交互。⑥无测试断言构造次数;attach_wiring 的 `_controller` 助手无 session 构造。

**拍板**:
- **方案 A(本批)**:改动全关在 benders_loop.py——`LBBDController.__init__` 加可选 `session` 参(默认 None→回退现行 per-round 构建,attach_wiring 测试零改动);`ExactSearchSession` 加懒构造缓存槽(key=`artifact_hashes` 映射的规范化 JSON,本就是四工件 SHA-256+homogeneity digest;缓存字段 `repr=False, compare=False` 防日志灾难);生产构造点穿 `exact_session`。改动面仍单文件,但 benders_loop.py 是 v99 floor+sink 双钉文件→随批 reseal(见 §5 修订)。
- **失效规则**:key 失配→重建;内容漂移兜底=α-1(fail-closed,已有 test_alpha_1 钉)。
- **防回退钉**:新测试断言(a)同 session 两 attach round 只构造一次 bundle(计数 monkeypatch);(b)生产构造点真的把 session 穿进 controller(源码级断言或行为断言)。
- **登记不做(随批C 复评)**:snapshot builder 每 round 仍深冻结同一份 45MB facility_pools(state_snapshot.py:581-638/695-734)——迭代路径的残余重活。若 PIC-4/5 生产实测显示不可接受,另立批把 session 级已冻结投影喂给 snapshot capture(碰 SHA-pin 的 state_snapshot.py,reseal 面上升,须独立双审)。本批不动,忠于 F02 登记的原始 BLOCK 范围(bundle 所有权)。

### 3.2 sink 注册升级 → **改判:字节钉即正确档,B6 清单①降为 won't-do+理由**(owner 2026-07-12 拍板)

侦察硬事实(scout-sink-registration,file:line 已核):
- `frozen_artifacts.py`/`state_snapshot.py` 当前仅在 checker v99 源哈希 floor(check_p1_2_proof_obligations.py:12957/12971)+mypy strict targets(preflight_gate.py:598-599),不在 JSON `sink_files[]`、不在 64 条 v99 sink 分类冻结字典。
- **checker 的 sink 模型强制 sink 文件含 proof-bearing token**:①`terms`≥1 须出现在文件文本(:13812);②registered sink 必在扫描面 `found`(含 16 个 sealed token 之一,:13852)。
- **两文件逐一 grep 16 个 token 零命中**——它们是 typed cut 链的**上游基建**(纯深冻结 / 快照校验),**不发认证判决**(不 emit CERTIFIED/INFEASIBLE/proof-bearing),天然无 token。直接注册会 fail-closed 两次(:13813 缺 term + :13854 不在扫描面)。
- **安全等价性(本会话实读 :13190-13200 坐实)**:v99 源哈希 floor 已对这两文件做「字节漂移→checker 红→重开 P1.2 close claim」,与 sink 注册的 `source_sha256_drift_reopens_p1_2_close_claim`(:13806-13807)**防篡改完全等效**。升 sink 注册**不新增任何安全属性**,只加对无 token 文件无意义的 token/term/obligation 元数据。

**拍板(方案 c,owner 选定)**:
- **B6 清单①从「做」改判为「won't-do + 理由」**:字节钉 floor 是无 token 基建文件的**正确档**;两档差异(proof-emitting sink vs 上游基建 byte-pin)是**刻意的、非疏漏**。α §4 遗留的「两档待遇统一」诉求由**文档化澄清**关闭,而非把基建文件强塞进不合身的 proof-bearing sink 模型。
- **不做**:不扩 checker 加「无 token 结构性 sink」新档(方案 b,徒然扩 close-kernel TCB 信任面换零安全收益);不为过门塞假 token(方案 a,违反 reseal「别好心」纪律)。
- **05 规格 §6 与 §1 item 6 里「sink 双钉」的措辞是作者误记**(以 §104 权威清单「仅 v99 floor 字节钉」为准),本批一并订正为「byte-pin floor=正确档」。
- 若将来 F5 转正批让 state_snapshot 真正承担 proof-emitting 语义(显式 INFEASIBLE/proof_bearing 作为真实行为),届时再评估升 sink——但那是**语义驱动**,不是为统一而统一。

### 3.3 F-05 alias 追踪(inline 侦察 + 双审 amendment A)

方案 A(digest 扩展):对「acquisition 绑定名字」站点(**从 acquisition 上溯到最近 Assign/AnnAssign/NamedExpr、只要 acquisition 落在其 value 子树即绑定 target 名**——一次覆盖直接右值 + 嵌套 RHS 的 IfExp/BoolOp/Call/getattr-method/comprehension 共 21 形态,双审设计位 MEDIUM-1 指出并采纳),收集 enclosing scope 内全部引用该名字的语句纳入 digest;digest 常量重钉;alias-then-write 复现负例必红。

**覆盖边界(仍开放,在 F-05 tripwire 威胁模型内、非 soundness 洞)**:本 digest 封**一跳** alias(名字直接由 acquisition 绑定)。**传递多跳链**——预存的 `d = <acq>; e = d;` 再新增 `e.model.Add(c)`——不追(`e` 非 acquisition 绑定,其下游不封;但新增 `e = d` 会因加载 `d` 被封)。残留可接受:F-05 是转正前 tripwire 非 certified soundness 门,certified 下 typed attach 关停、acquisition 在 phase3b 诊断模块、注入 review 可见。**F-05 转硬门(B6)仍需完整传递 alias-dataflow 追踪**——已登记进 F-05 转正清单(批D 规格 §5)与本节。双审(攻击位 LOW + 设计位 MEDIUM-1)均指向此边界,措辞已从「完备封死」订正为准确覆盖声明。

## §4 测试义务(初稿,拍板后细化)

- item 1:bundle 复用正例(同 session 两 round 同一对象/零重建)+失效负例(artifact digest 变→
  重建或 fail-closed,按拍板)+α-1/α-5 语义保持(复用 bundle 过新 round snapshot builder 校验)+
  构造次数断言(防回归 per-round)。
- item 2:checker 双绿(sink 67→69)+新 obligation 红测(若挂 obligation)。
- item 3:alias-then-write 复现负例必红(α2 攻击位的两语句形式)+诚实基线绿+digest 重钉。
- 全量:cuts 回归+fast lane+慢 lane(pytest-forked)。

## §5 reseal 面(实况,2026-07-12)

item ② 改判 won't-do 后,唯一碰 sealed 文件的是 item ① 的 benders_loop.py 改动,reseal 面**远小于预估**:
- **benders_loop.py**(v99 源哈希 floor + JSON sink 双钉,同 sha):`02c30e95`→`2a5fa3c9`——checker floor 行 + JSON sink `source_sha256` 各钉一次。terms/guard token 未动(7 个 token 改动后仍在)。
- **checker 自钉**(最后算):floor 行编辑改了 checker 源→JSON 里 checker sink `source_sha256` `524fb8f3`→`cb5d4cb6`。checker 不在 v99 源哈希 floor(仅 JSON 自钉,named-TCB 不自证)。
- **语义投影三写:不触发**——投影按 `:3319-3326` 对每 sink 剥离 `source_sha256`,本批只改 source_sha256、不加 sink/不改结构,投影 hash 不变→checker `P1_2_PROOF_OBLIGATION_SEMANTIC_PROJECTION_SHA256` 与 `certified_artifact_contract.py:31` runtime anchor 都不动。
- **frozen_artifacts.py / state_snapshot.py:零改动**——item ② won't-do;且 item ① 让 frozen_artifacts:1 的「Session-scoped」docstring 由 wining **自动变成真话**(bundle 现真 session 级复用),无需编辑该 sealed 文件(F14 该处顺带关闭)。
- **测试文件**(test_cut_framework_attach_wiring / test_stage_b_contracts):非 sealed,alias digest 常量 `158fd3f0…`(双审 amendment A 后重钉,原 `9d112ead…`)已钉,无 reseal。
- **双审 amendment 追尾 reseal**:LOW-1 给 benders_loop.py 缓存 key 加注释 → benders_loop sha 二次变 `2a5fa3c9`→`<最终>`,v99 floor + JSON sink + checker 自钉一并重钉(投影仍不触发)。
- 结果:checker 15/67 绿(sink 数不变)、strong-status 65/83 绿、cuts+wiring 全绿。

## §6 落地记录(2026-07-12)

- **item ①**(session-bundle 所有权):`benders_loop.py` 单文件——`ExactSearchSession` 加 artifact-digest 键控懒缓存 + `cut_framework_bundle` 访问器(`repr=False,compare=False`);`LBBDController` 加可选 `session` 参(默认 None→per-round 回退);生产构造点穿 `exact_session`。失效规则=key 失配重建 + α-1 内容绑定 fail-closed 兜底(白拿)。新测试 3 个(缓存单次/wiring 复用/无 session 回退)。
- **item ②**(sink 注册):改判 won't-do + 理由(§3.2,owner 方案 c)。
- **item ③**(F-05 alias):`test_stage_b_contracts.py` 加 `_coordinate_delegate_alias_use_digest`(封 delegate alias 名下游引用语句)+ `test_coordinate_delegate_alias_dataflow_is_sealed`;alias-then-write 注入实测触红。双审设计位 MEDIUM-1 后按 amendment A 扩为「上溯绑定+嵌套 RHS 全覆盖」(见 §3.3),覆盖边界诚实登记。
- **F14**:benders_loop「ONCE per attach round」注释重写;frozen_artifacts「Session-scoped」docstring 由 item ① 转真;lifecycle 无危险 F5-apply 旧注释,不动。
- **搭车瑕疵**:05 规格 §6 标题「codex=第三视角」矛盾 + 「_(待填)_」+ §1 item6「sink 双钉」误记,全部订正。
- **双审(双 opus:设计位+攻击位,2026-07-12)**:
  - **设计位:AGREE_WITH_AMENDMENTS**(0 BLOCK/0 HIGH/1 MEDIUM/3 LOW)。session 缓存 soundness(两层:弱 key + 每轮 α-1 fail-closed 复验)/回退逐字节等价/缓存字段 per-instance 安全/reseal 五点自洽/item② won't-do sound——全部无保留通过。**MEDIUM-1**:item③ 原 digest 只认 acquisition 为赋值直接右值,漏嵌套 RHS 绑定,同文件现存活写反例 `_lazy_delegate = self.master._coordinate_delegate if cond else None`(benders_loop.py:7076)+ 下游 `:7098` 真加 cut——falsify「完备封死」。**已按 amendment A 修复**(上溯绑定+21 形态全覆盖,`_lazy_delegate` 注入实测触红),措辞订正。3 LOW:①缓存 key 非完整内容身份→已加注释点明 α-1 才是闸;②alias digest 嵌套 over-include(维护摩擦非 soundness,可接受);③`_bare_session` core=None(仅测试侧,可接受)。
  - **攻击位:PASS**(零 soundness 穿透)。缓存投毒不可达(bundle 是 session-恒定输入的纯函数)、α-1 兜底不可绕(每轮对复用对象重验、内容分歧 fail-closed)、无跨 session 泄漏、session=None 无回归。1 LOW:F-05 acquisition-site docstring 删了边界措辞→**已恢复**传递多跳残留 + tripwire 边界 + B6 硬门需完整传递追踪的诚实说明。
  - **codex**:未派(攻击/对抗审查绕不开构造演示,cyber 门两层拦,派 opus)。
