---
id: p1-3-batch1-m5-current-20260712
kind: status
title: Batch1/M5/M6 当前态(2026-07-12):1A-1F 全落地;C1=certified 默认编码;供电可行布局存在性已关闭(完整产品默认 OPTIMAL@649.1s);M5 A/B 已解锁并完成首轮归因——剩性能调优与 prod-scale campaign,不是可行性/授权问题
summary: 取代 M5/Batch0/M6 三张旧卡的当前态。Batch 1 六子批 1A-1F 全部落地;C1 power-pole pose-bool/cov 编码已是 certified 默认(master_model c1_power_pole_representation 默认 True,S4 blocker 保证非 C1 即拒)。完整 266 实例+6×6 ghost 已有 OPTIMAL 解——M6 的「供电可行布局存在性 OPEN」已关闭。M5:「默认参数病态」已证伪(smoke#4 实死于当时 42G 硬帽+禁 swap 条款,双变量混杂误读;C1 出解时刻有 ~60G 级固有内存尖峰),修订内存条款下四组参数全部 OPTIMAL、完整产品默认 fixed+p3+s3 OPTIMAL@649.1s;A/B 已解锁并完成首轮归因,不再存在「待 owner 拍板」。剩余=性能调优优先级+production-scale campaign 实测(PIC-4/5),别再重复申请 owner 拍板、恢复已删 witness 路径、或把性能当可行性 blocker。铁律保留:prod-scale master solve 一次只跑一个(47.7GB 机双并发必 OOM);内存采样 ≤1s+VmHWM+VmSwap。**08-03 订正+08-05 复验终局(正文尾两段):「已有 OPTIMAL 解」跑于 front 错位语义+旧候选池,引用必须带「front 修正前口径」条件;08-05 现行池复验=62G 条款失效(9min OOM)+master 可行但认证枚举 censored@33h(owner 判有限时间跑不通)——存在性在现行口径下回到 OPEN,认证枚举墙深化四个数量级(649s→≥33h)。**
scope:
  domains:
    - p1-3-batch1
    - m5-convergence
    - power-encoding
  paths:
    - src/models/master_model.py
    - scripts/run_campaign_linux.sh
    - docs/research/p1_3_m5_convergence_20260708
  symbols:
    - c1_power_pole_representation
status: superseded
priority: P0
validity:
  until: "下一轮改变 Batch1/M5 结论的实测(prod-scale campaign 实测、性能调优批、内存条款修订)落地之前本卡为当前态"
  invalidated_by: "PIC-4/PIC-5 生产层实测得出新结论、C1 编码被替代、或内存条款再修订——届时按生命周期规程 supersede 本卡"
triggers:
  intents:
    - tune-solve-parameters
    - run-production-campaign
    - diagnose-first-solution
    - power-encoding-work
  keywords:
    - M5
    - M6
    - 首解
    - 供电
    - power pole
    - C1
    - cov 通道
    - 默认参数
    - OPTIMAL
    - campaign
    - Batch 1
    - 1D
    - A/B
  negative_keywords: []
  paths:
    - src/models/master_model.py
  symbols:
    - c1_power_pole_representation
  error_regex: []
  examples:
    - M5 的 A/B 实验还在等 owner 拍板吗,下一步跑什么?
    - 供电可行布局到底存不存在,首解出了没有?
    - 生产 campaign 用什么参数,默认参数是不是病态?
activation:
  layer_hint: L0
  must_know: true
  reason: 旧 M5/Batch0/M6 卡仍宣称「A/B 待 owner/1D 待开工/供电可行性 OPEN」,触发词(M5/首解/供电/Batch1)高频;按旧态会重复申请 owner 拍板、恢复已删 witness 路径、错误调参或把性能优化误当可行性 blocker(07-12 文档实态外审 F11)。
provenance:
  op: supersede
  supersedes: [p1-3-m5-phase1-verdict, p1-3-batch0-c1-first-solution, p1-3-m6-power-encoding-diagnosis]
  reason: 2026-07-12 文档实态外审(zmd_doc_audit_20260712)F11:三张 P0/L0 旧卡把已关闭问题写成当前开放项(A/B 待 owner、1D 待开工、供电可行性 OPEN),与 roadmap 当前段和源码相反;修复批 β 按生命周期规程 supersede 并立此 current 卡。旧卡的实验史实与死因分析仍真,保留为历史证据;单跑纪律与内存条款已并入本卡。
  evidence:
    - "src/models/master_model.py:2298,2315,2630(c1_power_pole_representation 默认 True)"
    - "docs/research/p1_3_m5_convergence_20260708/m5_ab_param_bisect_20260711.md:15-33(四组均 OPTIMAL;产品默认 fixed+p3+s3 OPTIMAL@649.1s;smoke#4 死因=42G+禁 swap)"
    - "docs/项目说明/00_master_roadmap.md §0(1A-1F 全落地;PIC-7 归因关闭)"
updated_at: "2026-08-05"
---
> **Superseded 2026-08-07(剪枝 P4 首批定点大修:三层订正地层压实为单层现态)**:当前态见 `p1-3-batch1-m5-current-20260805`。本卡仅作历史地层保留(07-12 正文 + 08-03 现势订正 + 08-05 复验终局三层原样保存),不再参与 active recall;**本卡 summary 头条与正文首段是压实前的旧口径,与文末两段订正相反,单读任何一层都会得出错误现态**——需要现态一律读新卡。

**Batch 1 / M5 / M6 当前态(2026-07-12;本卡取代三张旧诊断/判决卡的「当前开放项」口径)**:

- **Batch 1(1A-1F)全部落地**:C1 pose-bool cov-channel 编码转正为 certified 默认(`c1_power_pole_representation` 默认 `True`,S4 blocker 保证 certified 路径非 C1 即拒)、cov 通道+witness cell(1B)、解级 power-pole dominance 剪杆进 sealed(1C)、第 15 条 proof obligation 入册(1E)、生产内存条款(1F)。**没有「1D 待开工」**。
- **供电可行布局存在性已关闭**(原 M6 OPEN 问题):完整 266 实例 + 6×6 ghost 已有 OPTIMAL 解;M6 的「供电一开就溺死」诊断是 C1 之前的旧编码世界,其史实仍真但结论已被 C1 突破取代。
- **M5「默认参数病态」已证伪**:smoke#4 之死实因当时 42G 硬帽+禁 swap 条款(C1 出解时刻有 **~60G 级固有内存尖峰**,RSS>42G+swap 18G),不是参数病态;修订条款(62G 帽+swap 允许)下四组参数全部 OPTIMAL,参数只造成 wall 差异(+3.6%~+27.8%),完整产品默认 fixed+p3+s3 **OPTIMAL@649.1s**。**A/B 已解锁并完成首轮归因,不存在「待 owner 拍板」**;PIC-7 已关闭。
- **剩余工作的正确定性**:性能调优优先级 + production-scale campaign 实测(PIC-4/PIC-5 生产层)。**不要**:重复申请 owner 拍板、恢复已删除的 witness 路径、把 +26% wall 之类性能注记当可行性 blocker。
- **铁律保留**(从旧卡并入,继续有效):**prod-scale master solve 一次只跑一个**——47.7GB 机上双并发必 OOM(Windows 侧实测双杀);42G 帽+禁 swap 必死;内存采样纪律 ≤1s 间隔 + 读 VmHWM/VmSwap(30s 采样会把 60G 尖峰看成「温和」)。

**2026-08-03 现势订正(就地订正;查漏镜头首跑抓出头条结论缺前提条件)**:「完整 266 实例+6×6 ghost 已有 OPTIMAL 解」的判定跑于 **2026-07-11,即 front 错位语义+旧候选池之下**。07-18 front P0 事故(机械查体外第 2 格 vs 游戏真语义第 1 格,见文件记忆卡 front-offset-incident-20260718)双向污染当时全部 front 相关结论,批1-批5+域修正 82,829 落地后候选池已重冻结(现行 `f05b1291`)。**该存在性结论未在现行池下重跑——引用本卡头条时必须带「front 修正前口径」条件**。方向性预期不变(front 事故定谳原则=最优解从未变、旧数字是模型误差品;且修正放宽了第 1 格语义,可行域只增不减,存在性预期更稳),但「已关闭」的严格口径=待现行池复验。M5 参数/内存条款结论不受影响(与 front 语义无关)。

**2026-08-05 复验终局(就地订正;08-03 订正预告的「待现行池复验」已执行,结果推翻乐观预期)**:现行池 `f05b1291`+front 修正语义下按 7 月刀4 公式重跑存在性 cell(`.artifacts/m5_revalidation_20260803/`,NOTES.md 全程记录),两次尝试:①原公式 w6 在 42G/20G cgroup 下 **9min OOM——62G 修订条款对现行池不再成立**(swap 恰顶 20G 帽,RSS 35G 仍在爬;池大 ~18% 后内存包络越界);②降 w4+软 cap 22G 重跑:**master 预算内找到可行候选布局**,但 binding↔routing 无帽枚举(内层试错循环,7 月同 cell 总墙钟 649s)**磨 ≥33h 无终态,owner 拍板判「有限时间内跑不通」停机,枚举 censored@33h**。净结论:**存在性问题在现行口径下回到 OPEN**——master 可行 ≠ 认证级存在(binding/routing 门未过);「可行域只增不减所以更稳」的方向性预期对 master 层成立、对认证门**不成立**(front 修正让同一 cell 的认证枚举难度深化四个数量级)。这与文件记忆卡 first-certified-reduces-to-4-small-instances 的「真墙=binding↔routing 枚举循环」互为印证,是该墙在 front 修正后语义下的首个深度测量。62G 条款失效意味着 1F 生产内存条款也需随池版本重标定。
