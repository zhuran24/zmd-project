---
id: p3-0-formal-verification-head-start
kind: decision
title: P3.0 形式化线 68 条定理+Q1 分类学设计稿 v2(2026-07-05)——两轮外审全部回收闭环(main 2f6df03);轴 B 证书侧已开工(Day 1 工具链+玩具链路+设计稿 v1);锁面不动
summary: owner 2026-07-05 授权把 Q14(框架形式化证明,原 P3 defer)提前开头,当日 Lean 侧排队项全部清空。①`formal/` **56 条定理**过机器检查、零 sorry、公理审计 56/56 仅经典三公理或无公理(fb771ff 9→5560c39 14→517dbda 30→37965f6 45→ba17355 56;fb771ff 提交信息"7 条"是笔误),五个模块:TnsCoverage+F5OrbitLift(core-only)=TNS 覆盖链+F5 轨道提升与反例;DesignStatements=盲方陈述+本方施工——**anon_lift_sound 全链落地**;CutFamilies=**七个 family 核心 17 条**(第一梯队 F9/F1/F7/F4/F6/F2 各 bound+infeasible+第二梯队 F3 带 all-ports-active 显式量化);FrameworkLemmas=**框架层 9 条**(F5 复合安全引理(零公理)+无 P-HOM 删光反例/frontier lex 剪枝保最优+max_lex 具体化/TP7-S 等式键 sound·不过切·选中集式过切反例)。陈述层修改仅两处(README 记录)。**mathlib v4.31.0 已接入**。②设计稿 v2:轴 B 修正+P3.0c 七阶段(第一落点=binding PB sidecar 4-8 周);**轴 B 已开工(07-05 Day 1):WSL 工具链落地(RoundingSat+veripb 3.0.2 Rust 主线)+玩具链路正反验证+设计稿 v2 落 main 0333fd7(v1 双审 REJECT 回收重写),开发目录 zmd_cert_dev**。③三路审查归档 `p3_0_formal_reviews_20260705/`;④可开工地图归档 `p3_0b_family_formalizability_survey_20260705/`。**CutFamilies+FrameworkLemmas 26 条待独立复审**(陈述本方写,未走盲对拼)。**锁面不动**——16_workflow_review §6.4 政策继续有效。
scope:
  domains:
    - formal-verification
    - roadmap
  paths:
    - formal/README.md
    - docs/research/p3_0_formal_verification_head_start_design_v1.md
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - formal-proof-question
    - plan-next-work
  keywords:
    - 形式化
    - Lean
    - Coq
    - formal
    - Q14
    - P3.0
    - VeriPB
    - VIPR
    - 公理
    - sorry
    - lake
  negative_keywords: []
  paths:
    - formal/
  symbols: []
  error_regex: []
  examples:
    - 形式化证明做到哪了
    - Lean 定理怎么 build/扩展
    - 证书侧 proof logging 什么状态
activation:
  layer_hint: L1
  must_know: false
  reason: 谈形式化/Q14/Lean 时该想起——①这条线已开头且有实物,别再引「零投资纯 defer」旧口径;②扩展纪律=陈述改动必须对照设计稿原文过独立复审(formalization gap 是最大风险面);③锁面没动,别把 formal/ 说成认证 TCB 的一部分。
provenance:
  op: record
  reason: owner 原话「把这个形式化证明试着开个头,或者更好的话再进一步往前推进,记得 gpt pro 是跟你一起的」(2026-07-05)。
  evidence:
    - "main fb771ff(首批)→5560c39(三包回收)→517dbda(anon_lift_sound+mathlib);lake build 绿(8562 jobs);axiom_audit 30/30 仅 propext/Classical.choice/Quot.sound"
    - "GPT Pro 包:C:\\Users\\22957\\pr2_pkg\\p3_0_formal\\(3 zip+3 prompt),三包已回收归档"
updated_at: "2026-07-07"
---
== 这条线是什么 ==
Q14(框架 completeness/soundness 形式化)原判 P3 defer(投资数年级)。owner 2026-07-05 授权开头。策略=**双轴拆分**(详见设计稿):
- **轴 A 定理侧**(已开工):范式数学定理进 Lean。抽象边界纪律=形式化在抽象层,模型侧前提(反单调/P-HOM)作为**假设**接入,成立性由设计稿的机器可查义务(ghost inventory/逐谓词审计/结构门)承担。三层分工:抽象定理层(Lean)+前提审计层(结构门)+工程层(validator/replay)。
- **轴 B 证书侧**(总路线图支线 2b,**已开工——owner 2026-07-05「嗯,开始吧」,Day 1 三件套完成**):求解结果的 proof log+经形式化验证的检查器。七阶段见 P3.0 设计稿 §P3.0c;**第一落点 = Phase 0+1:binding 子问题 PB 独立重建 + VeriPB sidecar 复验(2-5 周 PoC)**。三条已拍定的设计约束:①**独立重建**编码(不从生产代码导出,保持异构交叉验证价值——与 PR2 #5-B2、I1 是同一笔投资的三个面);②纯旁路,不写生产路径、不碰锁面,与 PR2 主线零文件交集;③开发照 formal/ 模式(仓库外做,绿了经 worktree 落 main)。**Day 1 落地(2026-07-05)**:WSL Ubuntu-24.04 工具链(RoundingSat master 本地编译+veripb 3.0.2——**主线已是 Rust 实现**,深研报告"Python 参考版"口径过时);玩具鸽笼链路正反验证(VERIFIED + 两类假证书被拒);**binding PB 编码设计稿 v2 已落 main 0333fd7**(v1 双会话对抗审均判 REJECT 后重写,21 项修订全吸收——外审最重四刀:①dump 是生产加工后的世界不得当权威输入→canonical sample record;②scope 非机器闭合→五分类 binding_scope_class 字段化 gate,Phase 1 只收 PURE_BINDING_INITIAL;③「域空」在纯模型下是死分支(枚举器要么 raise 要么非空),真实 UNSAT 只来自 generic 精确计数;④验收必须双向:over-constraint 的 emitter 在一切 INFEASIBLE 样本上都漂亮 CONFIRMED,必须加 known-FEASIBLE canaries。归档 docs/research/p3_0c_sidecar_reviews_20260705/)。**实现第一批已落 main f533c96+227e942(`certside/` 顶层目录,与 formal/ 同锁面地位)**:零 import src/ 的 emitter+WSL runner+OPB witness checker+验收 harness **21/21 全绿**(UNSAT 4 CONFIRMED 真证明/FEASIBLE canaries 5/非法输入 8 全 fail-closed/双向突变 4 全被抓);语义规范 binding_canonical_semantics_v1.md(operation_profiles/strict_json 已逐行规格化,三层来源声明);**发现并本地修复 RoundingSat 上游缺陷**(parse 期平凡 UNSAT 的 proof 只写 dummy rup>=0,conclusion 指向它,veripb 正确拒——patch_rs_logger.py 补 rup>=1,全路径 sound;未打 patch 该类样本全 PROOF_REJECTED)。**第二批(99b591e)**:frontend.py 冻结工件解析前端(零 import src/,exact-decimal 解析+profile 独立重推 Fraction 精确 ceil)——与生产 OPERATION_PORT_PROFILES 对拍 **21/21 精确一致**;真实工件端到端 2/2(266 实例全放,17k 变量,R1 无储存箱 CONFIRMED/R2 补箱 SAT+witness,全链<10s 进 nightly 预算)。**owner 拍板(2026-07-05)**:Phase 0 采集侧(canonical sample record,动生产文件)= **P1.2 收口后再落**(选项 b——收口冻结期不给生产面添 diff;sidecar 独立验收已自洽不等这个);先做补强件。**补强件已落(c25d4c3)**:canonical-level witness checker(从原始输入语义独立验证 witness,应有对象集合第二实现,SAT 升级链 OPB→canonical→DIVERGED_CANDIDATE),验收 **25/25**(含 W 组 checker 自身红测 4/4),真实样本 R2 升 DIVERGED_CANDIDATE;**CakePB 第四层已接通(dd1a717)**——初判"版本错配"撤回,真凶=本地 patch v1 的 rup 写在 output 段后(kernel parser 严格段序,veripb 宽容;破案靠 SAT Competition 2026 官方配套文档);patch v2 修段序后**形式化验证 checker 确认全部 UNSAT 证明**(含 17k 变量真实模型),runner 四层默认开 fail-closed(cake_pb 失败 exit 也 0,只认结论行)。**轴 B 停在干净里程碑,剩余外部等待源时点更新**:①等待条件已于 2026-07-07 满足(P1.2 已收口);采集 schema 可排期/仍待 owner 排→真实对账;②~~RoundingSat proof bug 上游报告~~ **已提交**(2026-07-05,gitlab MIAOresearch/software/roundingsat issue #13,账号 ran24;报告经 GPT Pro 四轮对抗审后 owner 批准,含 AI 透明声明;终稿+四轮审查原件在 C:\Users\22957\pr2_pkg\rs_issue_report\;四轮外审顺带把修复方向从我们的 rup>=1 补丁升级为「conclusion hint 直指矛盾输入约束」——sanity check 实测 conclusion UNSAT : 1 即 VERIFIED,本地 sidecar 仍用自家 patch v2 不受影响)。开发目录 `C:\Users\22957\zmd_cert_dev\`(NOTES.md 有实测坑清单:**veripb 失败时 exit code 仍 0,判定必须解析 `s VERIFIED UNSATISFIABLE` 结论行 fail-closed**;OPB 扩展头 #equal 必须精确=等式行数,intsize 被忽略)。执行位=数学面线程。

== 工具链与工作方式(实操必读)==
- elan 经 scoop 装(`scoop install elan`),工具链钉 v4.31.0(formal/lean-toolchain);`cd formal && lake build` 即验证。
- **开发在仓库外做**:`C:\Users\22957\zmd_formal_dev\`(含 build 产物与 axiom_audit)——原因见 [[concurrent-session-untracked-file-wipe]],共享工作区的 untracked 文件会消失;改动经临时 worktree 以 tracked 提交落 main。
- 扩展纪律:任何定理**陈述**的修改必须对照设计稿定理原文,且过独立复审(设计稿修订版复审纪律的延伸;对应表在 formal/README.md)。
- formal/ 永不进 CI 硬门(设计稿 §6 开放问题 2 的预判)。

== 下一批砖(2026-07-05 当日 Lean 侧排队项①-⑤全部清空,main 517dbda→37965f6→ba17355)==
已完成:~~①装 mathlib~~ ✓(v4.31.0,manifest 锁 rev;zmd_formal_dev 有 ~4.5GB 缓存)→ ~~②anon_lift_sound~~ ✓(DesignStatements.lean 全链)→ ~~③第一梯队 6 family 核心~~ ✓(CutFamilies 15 条)→ ~~④F3~~ ✓(all-ports-active 显式量化+frontCell 抽象参数)→ ~~⑤F5 复合安全(零公理)+frontier lex 剪枝+TP7-S 等式键边界~~ ✓(FrameworkLemmas 9 条,各带正反两面:无 P-HOM 删光反例/选中集式 nogood 过切反例)。
剩余(按序):❶前三包**已回收**(2026-07-05,main 995373e):双路对抗审各双会话+盲对拼三方收敛,7 条陈述修订+8 条新增(F3→Multiset/F2 分离性移前提/F6 跨侧 fire/F5 忠实版+needs_cut_invariance 真红测/frontier certified-argmax/EqKey 硬化/F1 group-demand),原件归档 `p3_0b_formal_reviews_round2_20260705/`,**盲方 T1-T6 必要性 lifting = 未来砖素材**;**包4 已回收**(双会话:「架构级重写」vs「修后可作 Q1a 基准」实质收敛)→ **设计稿 v2 落 main 2f6df03**:定名 Q1a_complete_candidate_W(量词层错位修正,Q1p partial 层显式 open)/D_cut 语义 vs 观测分层(¬TrueFeasible≠VerifiedReject)/(Σ,M_base,K,scope) 签名/C6 降格 operational residual/C5 拆 a·b(容量不足层无 owner)/owner lemma 五段合同(emitted-cut refinement+两状态 scope=Q3 真接入)/W 七前提清单/S 撤回不可证改三层(S_i-progress 是逐类定理义务)/telemetry 四分/红测 R1-R10;❷~~完备性分类学设计稿~~ ✓ **v1 已落 main 954dafa**(`docs/research/q1_infeasibility_class_taxonomy_design_v1.md`):D_cut 定义/六类+F5 兜底/owner lemma 模板/**核心裁定 = Q1 拆 W-完备(近乎结构性成立,Lean 可及)与 S-完备(改判实验命题,telemetry 承载)**,待外审(包4);❸~~W-完备 Lean 骨架~~ ✓(WCompleteness.lean 3 条,main a611937;**自查发现:设计稿 v1 §5「扩展=自身」隐含两前提 Feasible⊆Complete + Complete 无真包含,已在 Lean 显式化,v2 修订时补 §5**——包4 CONTEXT 已把此发现交给 reviewer 复核);❹~~组合定理~~ ✓(oracle_nogood_compound_search_safety,main f3efa5c,formal/ 到 **60 条**整);❺F8 等 P1.3 stencil reconcile;❻TP7-D 周期日历证书验收语义。**Lean 侧不依赖外审回传的活已全部做完**——回传前无排队项。
Lean 施工经验(30 条趟出来的,后续照用):▸ 的 motive 搜索会丢类型 ascription→包 private def(castSnd 模式)走 unifier defeq;`{ι : Type*}` 在 def 里=下游定理的刚性 universe 参数→下游特化 .{u,v,max v w};依赖 cast 用「先 subst 后显式化」引理组(groupSlot_cast/atom_cast_eq);fiber 拼装用 Equiv.sigmaFiberEquiv+Embedding.sigmaMap(双参,第一个传 refl)全程 defeq,别用 generalize+subst 碰依赖上下文;native_decide 引 ofReduceBool 公理,小反例一律纯 decide(先 show 展开 def 才能合成 Decidable 实例)。

== 首轮审查回收要点(纪律沿用)==
盲形式化与本方全部抽象选择收敛零矛盾;对抗审 1 BLOCK=覆盖面夸大(教训:README 对应表别把核心引理写成完整定理);证书侧深研修正六处混桶。补丁不盲 apply——lean 补丁经本地重编译+公理审计采纳(实修一处:Lean core 无 Function.Bijective,改双侧逆)。陈述改动必须重过「编译+公理审计+对照设计稿原文」三件套。
