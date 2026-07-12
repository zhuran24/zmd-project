# 批 D 实施规格:F5 独立 verifier(RFC-002 verifier 面)

> 2026-07-11 深夜立,基于 bd-recon 六问侦察(file:line 全实证)+ 五悬念拍板。
> 权威上位文档:`design/RFC-002_f5_independent_proof.md`(评审建议稿)+
> `02_rfc_adoption_assessment.md`(采纳评估,与 I1 独立性哲学同构)。
> 阶段 B(B0-B5b)已全部落地,HEAD=1635248;本批 promotion-independent,
> 不依赖 B6 owner 门。

## §0 范围拍板(侦察拆批建议采纳)

**批 D 只做 verifier 面**;F5 转正面(compiler/typed_apply 第 4 行 operation/master
`_lower_pattern_nogood_cut` 原子重建/COMPILABLE 翻转/PIC-2 ghost-agnostic 语义
sound 重建)**整体剥出**,与 B6 合批或 B6 后单立(owner 拍板项压 B6;B6 前转正
零操作收益,且缺独立 verifier 时转正=把未独立验证链通到证明面)。

## §1 病根与目标(RFC-002 摘要)

- 病根:generator 经 `query_liftable()` 得 INFEASIBLE,validator(legacy 7 段第
  7 段 `_reverify_sub_problem_oracle`,pattern_nogood.py:360-405)与 typed 复验
  (`_reverify_f5_oracle`,typed_platform.py:1199-1256)都**重问同一进程同一
  adapter**——共同失效,ShadowValidated 自标 `_COMMON_MODE_UNTRUSTED`。
- 目标:对 F5 cert 指认的窄结论 `binding_empty_domain_v1`(某 (operation_type,
  pose) 的端口绑定枚举域为空,布局无关、frozen-artifact 派生)建**不经 oracle/
  registry/adapter 的独立复验**。独立性边界=换算法,不是进程隔离(那是 I1/L0)。

## §2 五悬念拍板

1. **verifier 从零写**(不复用 `enumerate_pose_level_port_bindings`):彻底避开
   共同 TCB;复验对象窄(单 pose 的 port-binding 匹配可行性),独立穷举/二分图
   匹配实现成本可控。生产枚举器与新 verifier 做**双实现 differential**(RFC §7
   红测 #6 的等价物,方向反转:两实现对拍而非 TCB 列名豁免)。
2. **recompute 型 verifier,不动 cert schema**:输入=现 `bounded_deletion_core`
   cert 的指认字段(forbidden_pose_pattern/literals)+frozen artifacts
   (candidate_placements/canonical_rules),独立重算绑定域空性——与 I1 哲学一致
   (重建复验,非 proof-checking)。RFC §3/§6 的专用 `BindingEmptyDomainProofV1`
   proof-carrying 形态**留转正批**(compile 面动 cert 时一并设计)。
3. **registry 降级(RFC §5)不进本批**,归 RFC-003 账本批;本批 verifier 自身
   零 registry 依赖,已在结构上绕开跨 session 复用旧 mapping 的缺陷面。
4. **转正归属 owner**:登记于 §0,本批零转正动作。
5. **PIC-2 ghost-agnostic 重建方案属转正批**:本批仅登记设计约束——转正的
   master lowering 必须给 GHOST_AGNOSTIC literal-multiset(含 BLOCK-2 ≥2 copies
   语义)一个 sound 的全 ghost-rect 禁排编码,方案先出设计再动手。

## §3 交付物

1. **新文件 `src/cuts/verifiers/binding_empty_domain_verifier.py`**(TCB,入
   floor):纯函数 `verify_binding_empty_domain(cert 指认, frozen bundle) ->
   verdict`。硬约束:零 import oracle/adapter/registry 模块;零 env 读取;
   fail-closed(任何解析/域构造异常=REFUTED 不是跳过);确定性。
2. **typed_platform F5 复验链叠加**:`_PatternNogoodPlugin` 在 `_reverify_f5_oracle`
   之后**叠加**独立 verifier 段(原重问保留=防御纵深);两段都过才出
   ShadowValidated。telemetry_tag 升级:verifier 通过的 shadow 标
   `_INDEPENDENTLY_VERIFIED`(新常量),不再是 `_COMMON_MODE_UNTRUSTED`;
   verifier 拒绝=CutRejection(stage="proof")而非降级 tag(fail-closed)。
3. **双实现 differential**:新 verifier vs 生产 `enumerate_pose_level_port_bindings`
   在采样/构造域上逐 (op,pose) 对拍(空性判定一致);不一致=测试红。
4. **RFC §7 六红测**(照 RFC 原文清单落地,含"verifier 不可达 oracle"的 import
   守卫红测——AST 层照 B5b TRIPWIRE 范式钉 verifier 文件禁 import 面)。
5. **e2e skip 解除**(attach_wiring:635-643):测试内
   `build_binding_empty_domain_adapter`+`register_sub_problem_oracle` 真接线,
   走完整编排到 shadow_validated 桶断言。**⚠ 07-12 文档外审 F03 校准——本条结论
   必须拆两层读**:该 full-chain 测试注册的是测试类 `_DifferentialF5Oracle`、不是
   生产 `BindingEmptyDomainAdapter`,它只证明「兼容测试 oracle 可贯通 typed
   编排」;真实 adapter 因 frozen tuple/list 形态差异在 verifier 前 fail-closed
   (§5 MEDIUM,可达性哨兵钉死),**不得称为 real-adapter e2e、不得当生产链背书**。
6. **reseal**:新 verifier 文件入 v99 floor+mypy targets;typed_platform(sink
   双重)重钉;checker 自钉。

## §4 边界

- 不碰:F5 转正全部面(§0);EXACT_CUT_FRAMEWORK_ATTACH 门控/unsafe-map;
  certified 阻断主锚;I1 reverifier(独立 TCB,别动);benders_loop 的
  `_add_exact_whole_layout_nogood` I1 硬门链。
- F5 保持 shadow-only:本批做完 F5 仍不 mutate master,唯一变化=shadow 的
  可信度从「共同失效不可信」升级为「独立验证」。**⚠ 07-12 文档外审 F03 校准**:
  「独立验证」当前只在**测试 oracle 链**上成立——真实 adapter 在 verifier 前
  fail-closed(§5 MEDIUM),`independently-verified` tag 在生产路径上暂不可达;
  该升级对生产链的成立以转正批清单①(adapter 修复+真-adapter e2e)为前提。

## §5 双审裁决(2026-07-12 凌晨,双 opus:数学位+攻击位均 AGREE_WITH_AMENDMENTS)

**verifier 本体 soundness 稳固**:数学位证明「域空」判定与生产枚举器严格等价(枚举器
无 commodity/cell 相性约束,域空⟺某侧计数短缺;verifier 的 need/have 与枚举器逐位
一致,完全图上匹配退化为计数比较);攻击位六向全跑,「非空域误判为空=错误背书」的
致命方向反例构造失败;op 剥离链(group_id 前缀+冻结 facility_type+profile 交叉核对)
无法被伪造 group_id 欺骗,规避了 RFC-002 §1 的 stale-mapping 病根;fail-closed 彻底
(Undecidable 绝不翻成通过,非预期异常传播=崩溃无背书)。修复处置:

1. **MEDIUM(双位共同,已修)**:真 adapter 路径下 verifier 当前不可达——latent gap
   坐实(`BindingEmptyDomainAdapter._find_pose` 的 `isinstance(pool,list)` 对冻结
   tuple 恒 None→恒答 FEASIBLE→前置的 `_reverify_f5_oracle` 恒拒,verifier 段只被
   测试 oracle 演练)。已补**可达性哨兵测试**
   `test_real_adapter_currently_rejected_before_verifier_reaches_it`:钉死当前
   fail-closed 行为;**adapter gap 修复(转正批)时此测必红,须换成真-adapter e2e
   断言 independently-verified tag,不得静默删除**。
2. **LOW(已修)**:verifier docstring「未来相性下 remains correct」改为
   「remains sound (conservative)」——完全图匹配在未来相性边下会高估可行性,
   方向 SAFE(高估→refute)但非 complete。
3. **LOW(已修)**:differential 补 bool 坐标角落用例——verifier `_require_int_like`
   拒 bool 抛 Undecidable,枚举器 int(True)=1 计入,分歧方向 SAFE,断言 verifier
   侧 refuse(而非与枚举器 ==)。
4. **LOW(已修哨兵+登记)**:`shadow_telemetry_tag` 静态类属性与 verifier 实跑解耦
   (当前不可利用:parse_and_validate_proof 线性无早退+fail-closed)——已补 AST
   哨兵 `test_tag_grant_is_downstream_of_verifier_call_linear_chain`(锁 verifier
   调用=顶层线性语句+其前无 return);**tag 授予动态化(token/返回值驱动)登记为
   转正批必做项**(转正批动 compile 面时一并做)。

**转正批(F5 promotion)必做清单沉淀**(本批+双审产出):①adapter frozen-tuple gap
修复+真-adapter e2e(接可达性哨兵);②tag 授予动态化;③PIC-2 ghost-agnostic
literal-multiset lowering sound 方案设计先行;④BindingEmptyDomainProofV1
proof-carrying cert;⑤verifier witness_literal 对接 lowering 编码。
