---
id: p1-2-closeout-then-tcb-backlog-order
kind: decision
title: PR2 TCB backlog 四阶段执行序(07-06 晚起转为发布时点安排)+ 测试提速线溶进主线 + P1.2 收口前提演变史(07-04 先深化→07-06 早扩全 backlog→07-06 晚收窄:防蓄意内鬼类延期、编码前提实质清空;"三连 clean"非硬判据)
summary: owner 2026-07-04 定的主线推进计划(本 summary 已按 07-04 晚、07-06 早、07-06 晚三次修正同步)。**前置板(现行版=07-06 晚)**:收口前提演变三步——07-04 晚"先深化(至少 #1)再收口";07-06 早扩"收口前提=全 backlog 编码项";**07-06 晚收窄(现行):厘清"内鬼=故意而非手滑"后,所有"仅防蓄意内鬼"硬化(#8 深化/#2/#3/#5-F/#9b/#9c/Option B)延期到发布时点、非 P1.2 前提→编码前提实质清空(#1 核心已做、剩余全在桶内),四阶段序转为发布时点执行序**,冻结仪式已走(冻结树 c9b41b3)、收口外审包已备(见修正历史③+[[deliberate-insider-hardening-deferred-to-release]])。#9a 维持部署时点。**"三连 clean review"语义澄清(owner 07-06):那是图方便的说法、非硬判据——实际=外审到 owner 判定合适为止(轮数可多可少),唯一权威动作是 owner 手动关门;gate JSON 的 3 与关门确认字段字样保留为机器兼容值(checker pin 死,同 p1_3b_* 模式)。****backlog 四阶段(轻→重,child 内容→child 闭包→OS 边界,每步给下步铺面不返工):①#8 argv0/contract digest + #9a 仓库侧收尾 + #6 维持不建;②#2+#3(loader 最小快照+fd-held read-once,同一接缝一起做)→ #5 的 B2 候选域独立枚举(长在 fd-held 语义上);③#5-F part3 设计 spike 三选一(追全/重构最小化 import-time 执行/接受残余)必须在 #1 动工前拍 → #1 最小 TCB 闭包(快照不扫全 src、child 不 import 项目域、吸收 #5-F part1+2);④#9b OS 级写隔离 + #9c 原生 TOCTOU。** **测试提速线全部溶进主线、不独立成批**:硬依据=提速任务动的文件(outer_search/exact_campaign/certified_frontier/benders_loop/candidate_proof_replay/terminal_fixed_witness_*/pr2_l0_*)全在 60 条 close-kernel sink 名单里,改它必走 reseal,reseal 是最贵固定成本,独立小批=每批白付一次;故收编进同文件面主线批合批。绑定:resume 清洗+frontier/replay 纯核心抽取→批2a(#2/#3);outer_search 非授权编排接缝→批2b(B2);306s aspect_ratio 巨无霸→批2b 尾巴(测试文件、不触 reseal);l0-snapshot 拆分+lazy import→并入 #1(#1 自动覆盖/消解);fused child→收益实验进 #5-F spike、成立(≥10s 固定税)则与 #1 同批、不成立(<3s)降为 #1 结构选项;搁置类(mini pack/cache-reset/sharded sidecar)维持搁置。总图与拍板台账见 docs/项目说明/00_master_roadmap.md(2026-07-05 立)。**backlog 四阶段(轻→重,child 内容→child 闭包→OS 边界,每步给下步铺面不返工):①#8 argv0/contract digest + #9a 仓库侧收尾 + #6 维持不建;②#2+#3(loader 最小快照+fd-held read-once,同一接缝一起做)→ #5 的 B2 候选域独立枚举(长在 fd-held 语义上);③#5-F part3 设计 spike 三选一(追全/重构最小化 import-time 执行/接受残余)必须在 #1 动工前拍 → #1 最小 TCB 闭包(快照不扫全 src、child 不 import 项目域、吸收 #5-F part1+2);④#9b OS 级写隔离 + #9c 原生 TOCTOU。** **测试提速线全部溶进主线、不独立成批**:硬依据=提速任务动的文件(outer_search/exact_campaign/certified_frontier/benders_loop/candidate_proof_replay/terminal_fixed_witness_*/pr2_l0_*)全在 60 条 close-kernel sink 名单里,改它必走 reseal,reseal 是最贵固定成本,独立小批=每批白付一次;故收编进同文件面主线批合批。绑定:resume 清洗+frontier/replay 纯核心抽取→批2a(#2/#3);outer_search 非授权编排接缝→批2b(B2);306s aspect_ratio 巨无霸→批2b 尾巴(测试文件、不触 reseal);l0-snapshot 拆分+lazy import→并入 #1(#1 自动覆盖/消解);fused child→收益实验进 #5-F spike、成立(≥10s 固定税)则与 #1 同批、不成立(<3s)降为 #1 结构选项;搁置类(mini pack/cache-reset/sharded sidecar)维持搁置。**收口动作(07-06 晚起即发、不再等 backlog)**:冻结仪式已执行(冻结树 c9b41b3、门禁全绿、送审包+7 切面提示词已备)→ 收口外审(GPT Pro relay,owner 手动上传)→ 审到 owner 判定合适 → owner 手动关门。
scope:
  domains:
    - release-engineering
    - certified-exact
    - pr2
    - test-performance
  paths:
    - PROJECT_LOCK.md
    - src/search/exact_campaign.py
    - src/search/outer_search.py
    - src/search/certified_frontier.py
    - src/search/candidate_proof_replay.py
    - scripts/check_p1_2_proof_obligations.py
  symbols:
    - supervisor_seal
    - resolve_p1_2_publish_open_gate
status: active
priority: P1
triggers:
  intents:
    - plan-p1-2-closeout
    - sequence-tcb-backlog
    - pick-next-hardening-item
    - bind-test-perf-tasks-to-mainline
    - design-fused-child-experiment
  keywords:
    - P1.2 收口
    - 先收口后深化
    - 三连 clean review
    - backlog 顺序
    - 四阶段
    - 执行序
    - 提速绑定
    - reseal 合批
    - close-kernel sink 名单
    - 纯核心抽取
    - fused child
    - 固定税
    - "#5-F spike"
    - "#1 最小 TCB"
    - 批2a
    - 批2b
    - lazy import
    - l0-snapshot
    - 306s 巨无霸
  negative_keywords: []
  paths:
    - PROJECT_LOCK.md
    - src/search/exact_campaign.py
  symbols:
    - supervisor_seal
  error_regex: []
  examples:
    - 下一个该做 backlog 里哪一项 / 排到主线哪个阶段
    - 测试提速的剩余任务怎么和主线绑
    - fused child 到底值不值得做 / 收益怎么测
    - P1.2 收口和 TCB 深化谁先谁后
activation:
  layer_hint: L1
  must_know: false
  reason: 规划 P1.2 收口 / 挑下一个 TCB 深化项 / 决定测试提速任务排到哪、fused child 做不做时该想起——这是 owner 2026-07-04 拍定的主线执行序与提速绑定,顺序和绑定理由都不显然(靠 sealed 名单+reseal 固定成本推出来),照它走才不会白付 reseal 或做返工的闭包。
provenance:
  op: record
  reason: 2026-07-04 owner 拍定主线序(原始拍板为"先收口 P1.2 → 四阶段 backlog",当晚修正为先深化后收口,07-06 再扩收口前提=全 backlog,见正文),并把 pytest 提速线程的剩余任务全部绑定进主线(依据 close-kernel sink 名单),含 fused child 收益实验设计与判据。
  evidence:
    - "2026-07-04 owner(问过 Fable + pytest 提速线程)给出完整绑定方案:提速任务动的文件全在 60 sink 名单→必走 reseal→全溶进主线合批;fused child 唯一收益未定,用现状代码量第二个 child 固定税(<3s 不成立/≥10s 成立,审查曾疑全仓 hash 18.8s 被第二 child 重复付),实验并进 #5-F spike;l0-snapshot(实测省 0.1-0.35s/seal)、lazy import(slow lane<1%)并入 #1。提速侧任务权威记录在 cc_memory(pytest 线程 2026-07-04 更新)。"
    - "2026-07-06 owner 两拍板(P1.2 方案完整性评估后):①对'#2/#3/#8/#9b 是否也算收口前提'答'算'→收口前提=全 backlog 编码项、收口外审移到阶段4 之后;②'三连 clean'是图方便的说法非硬判据,实际=外审到 owner 判定合适为止,gate JSON 的 3 与关门确认字段字样保留为机器兼容(checker pin 死)。落盘批 main 03ea2be(gate JSON 叙述字段/总图 1a+1b/本卡/收敛卡/stage3 卡/CLOSE_GATE/12 号/08 号/README);本分支卡片同步于同日。"
  updated_at: "2026-07-06"
---
owner 2026-07-04 拍定的主线推进计划(问过 Fable + pytest 提速线程)。这是"下一步做什么"的排期权威。

== 前置板(owner 07-04 晚修正 + 07-06 扩认:先做完整条 backlog 深化,再收口)==
**先做完整条 TCB backlog 深化,再走 P1.2 收口外审。**
- **修正历史**:本卡原记"先收口后深化",依据是"#1~#9 都在 TCB 线下、收口不等它们"。2026-07-04 晚 owner 质疑并澄清:那条 TCB 线是 2026-07-03 关于 **close-kernel 外审停** 画的、只管 close-kernel 外审循环,**不**授权"P1.2 整体收口不等所有 TCB 深化";**P1.2 收口的前提至少包含 #1(最小 TCB 闭包、child 不再 import 项目域)**——TCB 没真正做到最小时不能算收口。详见 [[review-convergence-tcb-line-not-zero-findings]] "再澄清"段。
- **修正历史②(07-06,回答"P1.2 方案完整性评估"里的悬空点)**:owner 明确 **#2/#3/#8/#9b 也算收口前提**——即收口前提=整条四阶段 backlog 编码项(#8、#2/#3、#5-B2、#5-F spike、#1、#9b/#9c)全部完成,收口外审排在阶段4 之后;#9a 生产字节重钉维持部署时点定位、不阻塞收口判定(既有绑定:#9c 随 #9b 同批、#6 为零工程决策确认)。原括号句"(#2/#3/#8/#9b 等是否也是收口前提 owner 未逐一明确;至少 #1 是)"就此作废。
- **修正历史③(07-06 晚,厘清"内鬼=故意还是手滑"后)**:owner 把②**再收窄**——所有「仅防能执行 reseal 仪式的**蓄意内鬼**」的硬化(#8 深化、#3、#9b、#9c、#5-F、#5 Option B、#2)**暂缓到发布时点、明确不作为 P1.2 收口前提**。判据:手滑/外部已被字节 sha floor 常开拦死,这些锚只对忠实 reseal 后的蓄意内鬼有意义(威胁模型 [[close-kernel-threat-model-reseal-adversary]])。连带:#1 剩余工程=阶段3(=#5-F)+阶段④(=#3)+out-of-scope 硬地板,全在桶内或范围外→**#1 无独立于桶外的前提工作**。**净效果:P1.2 编码前提实质清空,剩 owner 手动门 + close-scope 拍板**(≠可关)。故②"收口前提=全 backlog 编码项"现行版=剔除全部蓄意内鬼类;下面阶段序改为**发布时点**的执行序、不再是 P1.2 前提。全集+判据+可做项见 [[deliberate-insider-hardening-deferred-to-release]]。
- **"三连 clean"语义澄清(owner 07-06)**:「三连 clean 计数」是 owner 当时图方便的说法,**不是硬判据**——实际判据=收口外审进行到 **owner 判定合适为止**(轮数可多可少);gate JSON `required_consecutive_clean_full_reviews=3` 及关门确认字段的 "three clean reviews" 字样保留为**机器兼容值**(checker `check_phase_review_gate.py` pin 死该数字,改值=checker+tests 连锁手术,同 `p1_3b_*` 兼容模式),唯一权威关门动作=gate JSON `owner_manual_decision`。
- **正确顺序**:阶段1→批2a→批2b(已 DONE)→#5-F spike→#1(阶段3 枢纽,带 #5-F-B + fused 一批)→阶段4(#9b/#9c)→ 代码重新冻结+fresh reseal → 收口外审(本地 codex 多镜头 + GPT Pro relay 按需 + owner 判定合适 + owner 手动门)。**不起外审 round-21**(close-kernel 画线仍站着)。
- 收口外审的本地素材(12 镜头审报告 + 中立提示词)已备,留到深化做完、代码重新冻结后再用(那时审的才是含全 backlog 的最终 TCB)。

== backlog 四阶段执行序(轻→重;child 内容→child 闭包→OS 边界,每步给下步铺面不返工)==
**阶段1(轻,一次 reseal 批打包)**
- #8 argv0/contract 内容 digest:收掉"全信 `sys.argv[0]` 认 checker 身份",小而独立。
- #9a 仓库侧收尾:硬化批已合 main,补完 partial。**生产字节重钉是部署门任务**(必须 CachyOS+Py3.13 重生成重钉),单列、不占编码序。
- #6 维持"不另建":写一行决策确认,零工程。

**阶段2(中,两个 reseal 批)**
- **批2a = #2+#3 一起**:受控 loader 最小快照 + fd-held read-once 是同一条接缝(child 怎么读字节),拆开做互相返工;顺手收押后的 resume-envelope finding(README 归到 #2/#3 envelope 硬化)。
- **批2b = #5 的 B2 候选域独立枚举** —— **DONE(Option A)2026-07-06 `16495f4`**:B2 真实内容是 child 独立重推 **candidate_placements 几何**、断言 sha == 被钉字节(**不是** candidate_generation 尺寸域——那早已从冻结 canonical_rules 独立锚定;本行原文"不信 candidate_generation ~403-417"是**误框**,曾坑本会话两次,见 [[pr2-5-b2-candidate-geometry-rederivation-landed]])。#3 defer 后"长在 fd-held 语义上"的前置不再成立,B2 直接长在当前 path-read 语义落地,无返工。残余 = Option B(把 candidate_placements 移出证明权威=契约迁移)owner-only、未做。

**阶段3(硬骨头,child 内容定型后)**
- 先 **#5-F part3 设计 spike**:给 owner 三选一(A 追全 import-time 副作用 / B 重构最小化 close-kernel TCB 的 import-time 执行 / C 接受残余+V99 whole-file floor+人工 reseal 兜底)。**必须在 #1 动工前拍**——选 B 会直接改 #1 的做法,且 README 提过 #1 重构路线可能顺手溶解大半 F/A4 残余,比逐形态巡逻划算。
- 然后 **#1 最小 TCB 闭包**:快照不再扫全 `src/`、child 不再 import 项目域、吸收 #5-F part1+2。排阶段2之后的理由:最小闭包是对 child **最终形态**做的,child 内容还在变就闭包=白做一次。
- **spike 前期调查已做(2026-07-04 owner 离线期)**:见 [[stage3-spike-fused-5f-part3-findings]] —— fused=speedup-holds(本质省第二次 close-kernel 17s)、#5-F part3 已被 V99 floor 兜(TCB 线下)、阶段3 枢纽=#1(#5-F-B + fused 挂 #1 上一批做);三选一 owner 2026-07-04 已拍板采纳。

**阶段4(大,最后)**
- #9b OS 级写隔离:需目标 OS 资源(Linux uid-ns/seccomp 在 CachyOS 验、Windows 写隔离另一套);#1 做完 child 已最小化 → 要沙箱的越小、隔离设计越省。#9c 原生 `.pyd/.so` TOCTOU 随 #9b 一起收。

== 测试提速线全部溶进主线(不独立成批)==
**硬依据**:提速任务要动的文件——`outer_search.py`、`exact_campaign.py`、`certified_frontier.py`、`benders_loop.py`、`candidate_proof_replay.py`、`terminal_fixed_witness_*.py`、`pr2_l0_*.py`——**全在 60 条 close-kernel sink 名单里**。改任一必走完整 reseal 连锁,而 reseal 是最贵的固定成本。所以提速线**独立小批 = 每批白付一次 reseal**;正确排法只有一种:**收编进主线四阶段,跟同文件面的主线批合批走同一次 reseal**。(修正上一轮把提速分"独立长线 vs 搭顺风车"两类的错误——那三条"长线"动的也全是 sealed 文件,没有独立可言。)

**绑定表**
| 提速任务 | 绑到 | 理由 |
|---|---|---|
| resume 清洗 / frontier 投影纯核心抽取 | 批2a(#2/#3) | 同片代码(#2/#3 重构的就是 exact_campaign 读取面);且**纯核心抽取先行**——先抽核心配细粒度测试、再动 read-once 语义 = 给主线大改装安全网 |
| replay 纯 projection 核心 + checker 义务同步 | 批2a | certified_frontier 同文件面,与上条同手法(非授权纯核心抽取),一批做手法一致、审一次 |
| outer_search 三个非授权编排接缝 | 批2b(B2 独立枚举) | B2 改 producer/child 候选域契约必碰 outer_search,同批同 reseal |
| 306s 巨无霸(aspect_ratio 测试)改造 | 批2b 落地后的尾巴 | 依赖上面接缝才能改;本身是测试文件改动、**不触 reseal**,批后做不占批面 |
| fused child | 收益实验进 #5-F spike;成立则与 #1 同批 | child 形态大手术只开一次刀;不成立就只作 #1 的结构选项 |
| l0-snapshot 拆分、lazy import | 并入 #1,不单列 | #1 自动覆盖/消解(见下) |
| 搁置类(mini pack / cache-reset / sharded sidecar) | 维持搁置 | 收益小或未证实,不占任何批 |

**已实测、不再单列的两项**
- **l0-snapshot 拆分**:实测每次 L0 seal 只省 0.1-0.35s,提速可忽略;真实价值是 importable 攻击面收窄 = 主线 #1"child 不再 import 项目域"的浅层版,#1 做完自动覆盖。
- **lazy import**:实测对 slow lane 贡献 <1%;#1 会重塑整个 import 拓扑,先做会被推翻、后做大半自动消解。并入 #1 后看残余,不实验。

**fused child(两个隔离子进程融合成一个)——唯一收益真未定**
- 收益本质 = "第二个 child 重复支付的固定税"(进程启动 + heavy import + snapshot/hash)。
- **实验(不用先实现就能测)**:写取证脚本(exploratory 侧、放 `temp_scripts`、不碰 `src/`),对一个 toy sealed project 分别驱动 candidate replay child 和 fixed-witness capsule child 各若干次,每次拆两段计时——spawn→开始验证(固定税)、验证本体。fused 的节省 ≈ 第二个 child 的固定税段。
- **判据**:固定税 <3s/次 → 提速价值不成立,fused 降级为 #1 的一个设计选项(只剩 TCB 结构简化价值);≥10s(如审查曾怀疑的"全仓 hash 18.8s 被第二个 child 重复付"属实)→ 提速价值成立,正式纳入阶段3手术范围。
- **放哪**:时间线并入 #5-F part3 设计 spike(该 spike 本就是给阶段3做三选一调查,fused child 数据正是"重构最小化"选项的直接输入,不单开调查批)。环境:本机 Windows 够用(固定税=启动/import/hash,量级可信),CachyOS 就绪后复测校准一次。

== 分工归属(owner 2026-07-04 拍板:两不沾 / 偏数学面的交 Fable)==
- **Fable 负责**:搁置类三项(mini pack / cache-reset / sharded sidecar,纯 pytest 运行器基建、两不沾)+ aspect_ratio 306s 巨无霸测试改造(纯测试文件、偏数学面,改它要懂数学语义)。
- **发布面(Opus)负责**:其余全部——整条 TCB backlog 本体,以及提速里碰 sealed 认证文件的(resume/frontier/replay 纯核心抽取、outer_search 接缝、l0-snapshot、lazy import、fused child);动机虽是提速,但手术面在认证核心 + 善后是 reseal 连锁,属发布面。
- **铁律**:凡碰 sealed 文件的,不管谁写代码,**reseal 善后统一由发布面走**,避免多头 reseal 各自钉错。
- caveat:这些本是 pytest 提速线程的活,若该线程即 Fable 则本就归他;否则交接时别重复指派(owner 协调)。

== 贯穿纪律 ==
- 每批 = 完整 preflight + `--slow-tests` + close-kernel reseal 连锁(见 [[close-kernel-reseal-execution-sop]]);批内打包、批间不拆——全碰 sealed 文件,reseal 是最贵固定成本,排批 = 省它。
- **不自动起外审 round**(画线拍板还站着):每批对抗验证走本地 codex 多镜头 + 需要时手动 GPT Pro,不进 round-21/22 循环。
- 批2a/2b 审查面变大 → **审查分镜头**(主线语义改动一个镜头、非授权纯核心/接缝一个镜头),因为绑进去的这几条**刻意设计成不改证明语义**。
- 主线每批本来就跑完整 `--slow-tests` → 提速改动的效果回归被免费覆盖。
- 每批落地按 [[ship-then-sweep-docs-for-stale-narrative]] 扫文档;动 `src/search` 注意并发纪律。

== 游离序列外的两个部署时点任务(卡在 Linux 生产环境,就绪随时插入、不依赖 backlog 进度)==
- #9a 生产字节重钉(dependency-floor manifest 在 CachyOS+Py3.13 重生成重钉)。
- 真实 campaign→seal 实跑(`scripts/run_supervisor_seal.py` 从真 marker 驱动)。

== 一句话版(07-06 版)==
阶段1(#8+#9a尾+#6确认)→ 批2a(#2/#3 带两条纯核心抽取,先抽核心后改语义)→ 批2b(B2 带 outer_search 接缝,批后收 306s 巨无霸;已 DONE)→ #5-F spike(带 fused child 固定税实验并拍板)→ #1 最小闭包(吞 l0-snapshot/lazy import/若成立的 fused child)→ 阶段4(#9b/#9c)→ **收口 P1.2**(冻结+fresh reseal→外审到 owner 判定合适→owner 关手动门)。提速线整体溶解进主线,一次 reseal 都不多付。

关联:画线≠取消 backlog、外审收敛判据见 [[review-convergence-tcb-line-not-zero-findings]];#7 已通电见 [[pr2-7-supervisor-seal-entrypoint-design]];每批 reseal 实操见 [[close-kernel-reseal-execution-sop]];批后扫文档见 [[ship-then-sweep-docs-for-stale-narrative]]。提速侧任务的实测数字/细节权威记录在 cc_memory(pytest 线程 2026-07-04 更新)。
