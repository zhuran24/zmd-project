---
id: p1-3-batch1-m5-current-20260805
kind: status
title: Batch1/M5/M6 现态:1A-1F 全落地;C1 pose-bool cov = certified 默认编码;M5 参数已归因无待拍板;现行池 f05b1291+front 修正语义下供电可行布局存在性 OPEN(master 可行≠认证级存在);62G 生产内存条款失效待重标定
summary: Batch 1 六子批 1A-1F 全部落地,没有「1D 待开工」;C1 power-pole pose-bool/cov 编码是 certified 默认(master_model c1_power_pole_representation 默认 True,S4 blocker 保证非 C1 即拒)。M5「默认参数病态」已证伪(smoke#4 死于当时的 42G 硬帽+禁 swap 条款,不是参数病态;C1 出解时刻有 ~60G 级固有内存尖峰),A/B 已解锁并完成归因,**不存在「待 owner 拍板」**——别再申请拍板、别恢复已删 witness 路径、别把性能注记当可行性 blocker。**现行池 f05b1291+front 修正语义下:供电可行布局存在性 = OPEN**(master 在预算内找到可行候选布局,但 binding↔routing 无帽枚举磨 ≥33h 无终态、owner 判「有限时间跑不通」停机,censored@33h;master 可行≠认证级存在)。**62G 生产内存条款(1F)对现行池失效**(原公式在 42G/20G cgroup 下 9min OOM,池扩约 18% 后内存包络越界),需随池版本重标定。铁律不变:prod-scale master solve 一次只跑一个(47.7GB 机双并发必 OOM);内存采样 ≤1s+VmHWM+VmSwap。凡引用「完整产品默认 fixed+p3+s3 OPTIMAL@649.1s」必须带前提「front 错位语义+旧候选池口径」——该结论未在现行池下复现,且现行口径的认证枚举难度比它深化约两个数量级(≥183×;censored 只给下界)。
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
status: active
priority: P0
validity:
  until: "下一轮改变 Batch1/M5 结论的实测落地之前本卡为现态(prod-scale campaign 实测、性能调优批、生产内存条款随池重标定、或存在性在现行池下被重新关闭)"
  invalidated_by: "PIC-4/PIC-5 生产层实测得出新结论、C1 编码被替代、内存条款完成重标定、或供电可行布局存在性拿到认证级(binding+routing 门全过)的正/负结论——届时按生命周期规程 supersede 本卡"
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
    - 内存条款
    - 62G
    - 存在性
    - censored
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
    - prod-scale 跑要给多少内存,62G 条款还能用吗?
activation:
  layer_hint: L0
  must_know: true
  reason: 触发词(M5/首解/供电/Batch1/内存条款)高频,而被本卡取代的地层卡各自宣称过相反口径(「A/B 待 owner」「1D 待开工」「供电可行性已关闭」「62G 条款可用」);按任一旧口径行动会重复申请 owner 拍板、恢复已删 witness 路径、错误调参、把性能优化误当可行性 blocker,或按失效的内存条款发射长跑而 OOM。
provenance:
  op: supersede
  supersedes: [p1-3-batch1-m5-current-20260712]
  reason: 剪枝 P4 首批「压实 + 无时态层」定点大修。被取代卡是三层地层(07-12 正文 + 08-03 现势订正 + 08-05 复验终局),summary 头条与正文尾段口径相反,读者必须跨层整合才能得出现态——正是设计稿 .artifacts/prune_v2_20260803/design_p4_compaction_timeless_layer.md §3b 定义的开刀对象(订正地层 ≥2 层)。本卡把三层压实为单层现态,历史地层留在被取代卡与台账里。知识零丢失:参数/内存/铁律/存在性四组承重结论逐条搬入。
  evidence:
    - "src/models/master_model.py 的 c1_power_pole_representation(certified 默认 True;S4 blocker 保证 certified 路径非 C1 即拒)"
    - "docs/research/p1_3_m5_convergence_20260708/m5_ab_param_bisect_20260711.md(四组参数均 OPTIMAL;产品默认 fixed+p3+s3 OPTIMAL@649.1s;smoke#4 死因=42G 帽+禁 swap)"
    - ".artifacts/m5_revalidation_20260803/NOTES.md(现行池复验全程:尝试1 原公式 9min OOM;尝试2 降 w4+软 cap 22G,master 可行、binding↔routing 枚举 censored@33h)"
    - "docs/项目说明/00_master_roadmap.md §0a 的 M5 存在性复验终局行(owner 停机拍板与三条净结论)"
    - "「PIC-7 已归因关闭」的具名出处:docs/research/p1_3a_attach_power_on_spike_20260710/03_production_integration_checklist.md:29(PIC-7 条目原文)与 docs/项目说明/06_current_status.md:176(增量段复述)"
    - "「批1 1A-1F 全落地」的具名出处:docs/项目说明/00_master_roadmap.md §0a 里程碑指针表 07-10 行(第 62 行)"
updated_at: "2026-08-07"
---
**Batch 1 / M5 / M6 现态**（单层现态卡；历史地层见文末指针）：

- **Batch 1（1A-1F）全部落地**：C1 pose-bool cov-channel 编码是 certified 默认（`c1_power_pole_representation` 默认 `True`，S4 blocker 保证 certified 路径非 C1 即拒）、cov 通道 + witness cell（1B）、解级 power-pole dominance 剪杆进 sealed（1C）、第 15 条 proof obligation 入册（1E）、生产内存条款（1F）。**没有「1D 待开工」。** 具名出处：台账 `docs/项目说明/00_master_roadmap.md` §0a 里程碑指针表 07-10 行。

- **M5 参数结论（窄口径 = 「smoke#4 死于资源条款、不是参数病态」；仅这一句与 front 语义无关）**：「默认参数病态」是**误读，已证伪**。smoke#4 之死实因当时的 **42G 硬帽 + 禁 swap** 资源条款——C1 出解时刻有 **~60G 级固有内存尖峰**（RSS > 42G + swap 18G），不是参数病态。放开内存后四组参数全部 OPTIMAL，参数只造成 wall 差异。**A/B 已解锁并完成首轮归因，不存在「待 owner 拍板」；PIC-7 已归因关闭**（出处见 frontmatter evidence）。
  **⚠ 别把这条窄口径读宽**：四臂 A/B 的实测条款 = **42G 帽 + 20G swap（＝ 62G 预算）**，**该条款对现行池已失效**（见下方内存条款行）；随之而来的 wall 数字（**+3.6% ~ +27.8%**、`OPTIMAL@649.1s`）全属**旧池口径**，不是现行池下的可复现量。同款条款同 w6 在现行池上就是下方尝试① 的 9 min OOM。

- **⚠ 带前提引用**：「完整 266 实例 + 6×6 ghost 产品默认 fixed+p3+s3 **OPTIMAL@649.1s**」这一条**只在「front 错位语义 + 旧候选池」口径下成立**，未在现行池 `f05b1291` 下复现。引用它必须写明该前提，否则就是把一个旧口径的数字当现态用。

- **供电可行布局存在性 = OPEN**（前提：现行池 `f05b1291` + front 修正后语义）。现行口径复验两次尝试：①按旧公式（w6）在 42G/20G cgroup 下 **9 min OOM**；②降 w4 + 软 cap 22G 重跑：**master 在预算内找到可行候选布局**，但 binding↔routing 无帽枚举（内层试错循环）**磨 ≥33h 无终态**，owner 拍板判「有限时间内跑不通」停机，枚举 `censored@33h`。净判据一句话：**master 可行 ≠ 认证级存在**——binding / routing 门未过，存在性就是 OPEN。
  **OPEN 的位置在认证门（binding / routing），不在 master 的供电编码**：M6「供电一开就溺死」的旧编码墙已被 C1 突破（史实见卡 `p1-3-m6-power-encoding-diagnosis`），复验尝试② 里 master 在预算内出可行候选布局正是佐证。别把这条 OPEN 回读成「供电编码又不行了」。

- **认证枚举墙是真墙，且在 front 修正后语义下更深**：同一个 cell 的认证枚举从旧口径的 649 s 量级变成现行口径的 ≥33h，**深化约两个数量级（≥183×）**；`censored@33h` 是**下界**，真实倍数只会更大、拿不到确值。「front 修正放宽第 1 格语义 ⇒ 可行域只增不减 ⇒ 存在性更稳」这条方向性预期**对 master 层成立、对认证门不成立**。这与「真墙 = binding↔routing 枚举循环」互为印证，是该墙在现行语义下的首个深度测量。

- **生产内存条款（1F）待重标定**：**62G 修订条款对现行池不再成立**（swap 恰顶 20G 帽、RSS 35G 仍在爬；池扩约 18% 后内存包络越界）。发射 prod-scale 长跑前必须按当前池版本重算包络，别照抄 62G。

- **铁律（不随池版本变）**：**prod-scale master solve 一次只跑一个**——47.7GB 机上双并发必 OOM（Windows 侧实测双杀）；**42G 帽 + 禁 swap 必死**；内存采样纪律 = **≤1s 间隔 + 读 `VmHWM`/`VmSwap`**（30s 采样会把 60G 尖峰看成「温和」）。

- **剩余工作的正确定性**：性能调优优先级 + production-scale campaign 实测（PIC-4/PIC-5 生产层）+ 内存条款随池重标定。**不要**：重复申请 owner 拍板、恢复已删除的 witness 路径、把 +26% wall 之类性能注记当可行性 blocker、或把「master 找到可行布局」写成「存在性已关闭」。

**历史指针**（本卡不复述旧论证）：被取代的三层地层卡 `p1-3-batch1-m5-current-20260712`（其 provenance 再往上指 `p1-3-m5-phase1-verdict` / `p1-3-batch0-c1-first-solution` / `p1-3-m6-power-encoding-diagnosis` 三张原始诊断卡）；实验史实与死因分析全档 `docs/research/p1_3_m5_convergence_20260708/`；现行池复验全程 `.artifacts/m5_revalidation_20260803/NOTES.md`；owner 停机拍板与三条净结论见台账 `docs/项目说明/00_master_roadmap.md` §0a 对应行；坐标速查见 `docs/项目说明/27_status_dashboard.md` §4。
