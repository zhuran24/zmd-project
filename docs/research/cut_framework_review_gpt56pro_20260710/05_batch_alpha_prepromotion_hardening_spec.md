# 修复批 α:pre-promotion 信任根硬化(GPT Pro 外审第二轮 triage 产出)

- 立项:2026-07-12(owner 批准「开始吧」;源于 7 包外审回包 triage,主会话终审)
- 性质:**全部七项在诚实调用方下当前不可达**(生产 caller 同步紧邻 + `EXACT_CUT_FRAMEWORK_ATTACH` certified 禁用),不是当前 soundness 破洞;但它们是 typed 链晋升 certified 信任根前必须闭合的 API 硬化面,**是 B6 的天然前置**。
- 外审出处:`zmd_deep_freeze_integrity_audit_20260711`(F-01~F-05)、`cut_framework_model_scope_audit`(MS-1)、`certified_exact_typed_cut_audit_20260711_rebuilt`(RB-2)。外来补丁 0001-0007 **只当参考,不直接 apply**(对抗语料卫生惯例,自己重写)。
- 改动面预估:`src/cuts/state_snapshot.py`、`src/cuts/frozen_artifacts.py`、`src/cuts/lifecycle.py`、`src/cuts/typed_platform.py`(全 v99 floor/sink 双钉)→ 完整 reseal 连锁。

## §1 七项拍板

### α-1(F-01)state/bundle 内容绑定
- 病:`build_validated_state_snapshot(state, bundle)` 两入参可代表不同世界;`_freeze_artifact_hashes` 只做 bundle↔state 哈希**注记字符串**子集比较,四份静态 source 的实际内容从不逐项比对。source_digest 反映 state 世界、family inputs/三族投影反映 bundle 世界,可混合。
- 拍板:builder 内对 captured(state 世界)与 bundle 冻结值(bundle 世界)的静态 source 逐内容相等断言——`candidate_placements`、`facility_templates`、`instance_to_facility_type`、`canonical_rules`(bundle 存在该字段时)。比较在两侧都已冻结/规范化后进行(冻结形态直接 `==`)。不一致 → `SnapshotValidationError` fail-closed。
- 落点:`build_validated_state_snapshot`(state_snapshot.py:1541 起)。

### α-2(F-02)动态边界拒绝行为型容器
- 病:动态层 `_require_cell`/`_freeze_cell_set`/`_freeze_cell_sequence`/`_freeze_ghost`/`_freeze_groups`/`_freeze_cell_owner`/`_freeze_artifact_hashes`/`_freeze_oracle_capabilities` 用 ABC(Mapping/Set/Sequence)判型,会调用调用方自定义 `__iter__`/`items()`/`__getitem__`,同一对象可在两处冻结出不同值(hybrid snapshot)。
- 拍板:入口类型收紧为 **exact type**(`type(x) is dict/list/tuple/frozenset/set`,按各字段合法形态取白名单),在任何 hostile 方法被调用前拒绝子类与鸭子类型。BState 各字段的既有合法生产形态先侦察确认再定每处白名单(禁止拍脑袋放宽)。
- 落点:state_snapshot.py:280-466 一片。

### α-3(F-03)投影与 lowerer 私有 cache 的一致性校验
- 病:`_live_master_domain_projection` 从 mandatory_slots/templates/pools/coverer 重建 rows,但 lowerer 实际还读 `_mandatory_groups`、`_template_pose_tuple_by_idx`、惰性 `_pose_idx_by_pose_id_cache`——投影哈希不变不能证明 lowerer 实际输入未漂。
- 拍板:走**校验路线而非扩投影**(投影 schema/字节不动 → fingerprint 不漂 → 不触发 golden 重钉):在 `_live_master_domain_projection` 重算时同步校验上述 cache 与其权威源(slot templates/pool registration)逐项一致,不一致 → ValueError fail-closed。F7 pose-id cache 仅在已 materialize 时校验。
- 落点:lifecycle.py:1372-1484 加校验段(可下沉 helper 到 exact_coordinate_master 侧,按实现侦察定)。

### α-4(F-04)apply 边界重验 live master
- 病:resolver 把 live 投影缓存进 binding,`step_8_apply_to_master` 三连校验比的是**缓存值**,resolver→step_8 间隙 master 被改不会被发现(生产 caller 紧邻同步调用所以当前不可达;API 层面是 stale-binding TOCTOU)。
- 拍板:step_8 在类型门与三连校验通过后、进入 typed_apply 前,**重算 live projection** 与 `scope_binding.master_domain_projection` 相等断言(family 经 §2.6 同款 snapshot 三投影匹配恢复,或 binding 新增 family 字段——实现侦察后取更小改动面者)。开销=每 apply 一次投影重算,量级可接受(B5a 实测投影重算亚毫秒级)。残余窗口(重算结束→lowerer 读取完成)登记为已知边界,单线程同步调用链下无实际面。
- 落点:lifecycle.py:1560-1601。

### α-5(F-05)深冻结 identity memo + cycle/深度受控
- 病:`FrozenArtifactBundle._freeze` 无 identity memo,共享节点重复观察(同一对象两处冻结值可不同),自环直接 `RecursionError`(不受控失败形态)。
- 拍板:`_freeze` 加 identity memo(`id→frozen`,含四 root 共用)+ active set(自环/交叉环显式 `ArtifactValidationError`)+ 显式深度上限(128)。同 identity 只观察一次=共享节点冻结一致。
- 落点:frozen_artifacts.py:44-113。

### α-6(MS-1)ghost 身份锚
- 病:`_locate_master_ghost_rect` 按 bbox 摘要定位平行容器索引,binding 只记 rect_idx——不独立证明该索引上的 u_var 仍是当时那个对象。
- 拍板:binding 已持 `condition_lits=(u_var,)`;step_8/apply 前补**身份重验**:`master.u_vars[binding.rect_idx] is binding.condition_lits[0]`(对象同一性,非相等),失败 fail-closed。agnostic 路径无此义务。
- 落点:lifecycle.py(resolver 存 rect_idx 已有;校验加在 step_8 重验段,与 α-4 同一段落地)。

### α-7(RB-2)binding 绑定 master 身份
- 病:`ModelScopeBinding` 不记 master 身份,resolver 对 master A 出的 binding 可被喂给 master B 的 step_8,foreign BoolVar 按 proto index 静默别名。
- 拍板:binding 新增 master 身份字段(`weakref.ref(master)`;frozen dataclass 存 weakref 可行,不入 repr/比较),由 `_build_model_scope_binding` 填充;step_8 校验 `binding 持有的 ref() is master`(死引用或不同对象均 fail-closed)。AST 守卫(B1.5 Counter allowlist)对新字段无扰动——构造点不变。
- 落点:typed_platform.py(字段+工厂)、lifecycle.py step_8(校验)。

## §2 测试义务

1. 每项至少一正一负:负例=敌对输入/篡改被 fail-closed 拒绝(参考外审 PoC 的攻击形态,**代码自己写**,不 copy 包内脚本);正例=诚实链路照旧全绿。
2. α-4/α-6/α-7 合并一组「binding 时效与身份」红测:resolve 后篡改 pool → step_8 拒;跨 master 搬运 binding → 拒;u_vars 索引换对象 → 拒。
3. α-2 每个收紧点一个子类/鸭子负例(dict 子类、UserDict、自定义 Set)。
4. α-1 混合世界负例:bundle 冻结后改 state 静态 source → builder 拒。
5. α-5:共享节点冻结一致性断言 + 自环显式错误类型断言(非 RecursionError)。
6. 全量回归:`src/tests/cuts/` 全绿 + fast lane 全绿 + 慢 lane 31 条全绿;三族既有 stage_b 测试零改动通过(accept-set 零变化——本批全部是**收紧**,若任何既有绿测转红即为 accept-set 变化,停下上报)。

## §3 不做面(登记)

- F-06(digest v2 纳入三族投影):无实际路径(唯一 tokenized builder 确定性派生),v2 迁移代价大(golden/envelope/replay 全动)——**推迟到批 E 后评估**。
- P-01(三族投影两两不等断言):现 schema 结构性域分离已足,不加。
- typed_legacy 包 3 BLOCK:FP(harness 类型错配),不动。
- 文档/记忆债 ~14 项:修复批 β 单独走(无 reseal,轻量)。
- α-4 残余窗口(重算→lowerer 读取完成):单线程同步链下无实际面,登记不闭合;真并发化是遥远的另一批。

## §4 双审裁决与处置(2026-07-12,双 opus:设计位+攻击位)

- **设计位:AGREE_WITH_AMENDMENTS**(零 BLOCK 零 HIGH)。七项拍板全部如实落地,「方案偏离:无」逐条验实;6 个既有测试改动全合法(攻击载荷适配 ×3 / schema 适配 ×1 / 收紧例外 ×2,无 skip/xfail/吞异常/删诚实正例);AST 守卫(B1.5 Counter allowlist)零扰动;5 条边界观察独立深挖全部准确(含命名痕迹 `powered_facility_types` 经确认校验覆盖面恰等于 lowerer cache 读取面、无功能缺口)。
- **攻击位:PASS**(44 项对抗探针,0 BYPASSED;每项零 master 变异经 proto SerializeToString 指纹坐实)。七道门在诚实数据 API 下全部严密;id() 复用/tuple-vs-list 归一化盲区/129 层深环等均构造上不可达或 fail-closed。

**amendment 处置(本批落实)**:
1. **reseal**:四 sealed 文件(state_snapshot/frozen_artifacts/lifecycle/typed_platform)走完整五层连锁(floor 4 条重钉+sink 2 条+checker 自钉最后)。
2. **step_8 显式 master 卫哨(设计位 LOW)**:已加 `master is None` 与 `master_ref() is None` 两道显式 fail-closed,病态 master=None 得干净 ValueError 而非下游 AttributeError。α-7 错误串相应拆为三条(expired/different),`test_alpha_7` match 已同步。
3. **格式重排(设计位 LOW·sealed 卫生)**:typed_platform.py 的 telemetry_tag 行 α 批由多行折成单行——经查**单行才是 ruff-format canonical**(HEAD 的多行是 pre-existing 格式债,α 批碰该文件时 ruff 顺带清了),revert 回多行会制造 ruff 违规,故**保留单行**。该行 1 行 churn 不可避免(ruff 强制),非可去除的无关 churn。
4. **FORGE-rect-vs-ghost 纵深加固(攻击位威胁模型边界 1)**:step_8 bound 分支新增 `rect_idx == _locate_master_ghost_rect(live_master, ghost_rect_digest)` 重验,让 apply 边界自足、不依赖 resolver 的 rect↔ghost 对应。**负测登记**:该门仅在多-ghost-rect master 下可被伪造 binding 触发,单-rect fixture `_f1_world` 下 α-6 的 u_var 身份检查已堵死该路径,诚实 resolver 恒满足 rect==locate;专门负测需多-ghost-rect fixture,随修复批 α2(碰 exact_coordinate_master + 更全 master fixture)一并补。诚实路径由现有 826 回归覆盖。

**攻击位威胁模型边界 2(私有工厂/token 可 import)**:既有 B5b 模式(模块私有+AST allowlist 托底,非 token 本身),本批未回归,登记不动——敌意代码能 import 者本可直接调 `_lower_*`,不属敌意数据面。

**第二波外审 triage 对 α 的影响(lockaudit/master_lockdown/F5 三包)**:F7 pose-id cache 拒绝路径非原子(BLOCK,B5b §4.11 漏网)、AST owner-scope lambda/comprehension 逃逸(BLOCK)、CALL 计数器引用搬运绕过(BLOCK)、assert `-O` 剥离+duplicate slot key(CONCERN)——同性质 pre-promotion 硬化但集中在 `exact_coordinate_master.py`(α 未碰)+ AST 守卫,归**修复批 α2**(α 收口后开,避免同改 test 文件打架)。F5-01(group→operation 绑定)/F5-02(profile 浅冻结)归 F5 转正批。
