---
id: memory-three-layer-coexistence-decided
kind: decision
title: 记忆三层互补共存已定调:cc_memory/vnext/harness 分工 + 冻结=按条 archive-on-promotion(非整库冻/迁)
summary: 2026-06-30 统一三处文档并定调:cc_memory(全量可查 pull,仍现役可写,带图+语义)+ vnext cards(主动推送精选)+ harness(索引/反射/resume)三层【互补共存】,不是新旧替代、整库迁移非目标。"冻结"=按条 archive-on-promotion(某条做成卡→archive cc_memory 源条目防漂移;图枢纽条目留薄"图锚/指针节点"保边)。新记忆先进 cc_memory 收件箱,达"必须每回合推送"门槛才晋升成卡;不给 vnext 补通用低摩擦写入(摩擦=质量闸)。问"旧库冻没冻/还能不能写/这条写哪/为什么还往 cc_memory 写/要不要迁进 vnext"按此答。
scope:
  domains: [memory-layer-authority, cc-memory-freeze]
  paths: []
  symbols: []
status: active
priority: P1
triggers:
  intents: [memory-layer-authority, cc-memory-write-allowed, freeze-status, memory-write-location]
  keywords: [冻只读, 整库只读, 旧 cc_memory 能不能写, 旧库还能写吗, 旧的不是只读, authoritative, 双活, 迁移真相源, 三层并存, 三层共存, cc_memory 冻, 这条写哪, 为什么还往 cc_memory 写, 往 cc_memory 写, 迁进 vnext, cc_memory 迁, archive-on-promotion, 按条 archive, 图锚]
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 旧 cc_memory 不是冻只读了吗,为什么还往里写
    - v-next 上线后旧库是整库只读、还是还能写
    - 这条要写旧 cc_memory 还是 v-next 卡
    - cc_memory 和 vnext 到底怎么分工,要不要把 cc_memory 迁进 vnext
    - 为什么新记忆还是优先往 cc_memory 写
activation:
  layer_hint: L1
  must_know: false
  reason: 误以为旧库已整库冻/要迁进 vnext 会写错地方、答错分工;实际是互补共存+按条 archive-on-promotion。
provenance:
  op: supersede
  supersedes: [memory-layer-authority-transition]
  reason: 2026-06-30 owner 与会话把三处文档口径统一(MASTER_PLAN/COUNCIL_FINAL_PLAN[=council_B]/CLAUDE.md 全对齐)并定调"互补共存+按条 archive-on-promotion、整库迁移非目标",原 open_obligation 的 until/invalidated_by 条件已满足。
  evidence:
    - "CLAUDE.md 'Collaboration memory (cc_memory)' 与 'Active card memory (cc_memory_vnext)' 两节(2026-06-30 已对齐:互补共存、非冻只读)"
    - "记忆系统-3/记忆系统-架构总览与三层分工-20260630.md(三层分工+archive-on-promotion+图锚)"
    - "记忆系统-3/记忆系统-vnext方案-统一版-20260630.md(三份方案稿合并,冻结口径修正)"
updated_at: "2026-06-30"
---
记忆是**三层互补共存**(不是新旧替代,整库迁移非目标):
① 旧 `cc_memory`(SQLite)= 全量、低摩擦的可查历史库 + 写入收件箱,**仍现役、可写**,带图(边)+ 语义检索(pull,需主动 search);
② v-next `cards/` = 主动推送精选层,每轮按相关性注入完整内容,只放"必须每回合提醒的稳定知识"(push);
③ harness `*.md` = SessionStart 加载的轻层(跨库索引 / always-visible 行为反射 / volatile resume 锚)。

**为什么不整库迁进 vnext**:vnext 结构上吞不下 cc_memory 的核心能力——边的自动发现 + impact 图、低摩擦随手记、大规模语义检索、跨会话变更感知。两层是互补的不同形状,迁移**只搬内容、不搬边**,边和图永久留 cc_memory。

**"冻结"= 按条 archive-on-promotion**(替代模糊的"冻"):某条知识做成 v-next 卡后 → `archive` 它的 cc_memory 源条目(status→archived,从 boot/export/召回消失但仍可 read/search,防同一记忆两边漂移)+ 留指针。**图枢纽条目**(被别的活条目依赖)别直接 archive——留一个薄"图锚/指针节点"在 cc_memory(只含边 + 指向卡片),内容进卡片、边留 cc_memory(就地转换最省事、免重指边)。

**写入分工**:新记忆默认进 cc_memory(低摩擦收件箱)→ 达"必须每回合主动推送"门槛才晋升成 v-next 卡;**不给 vnext 补通用低摩擦写入**(没好触发的卡要么不被推、要么逼出垃圾触发=噪声;authoring triggers 的摩擦=质量闸)。可选只加"晋升脚手架"`zmem new-card --from-cc <id>`,不是"丢文本→卡"。

问"旧库冻没冻 / 还能不能写 / 这条写哪 / 为什么还往 cc_memory 写 / cc_memory 要不要迁进 vnext / 三层怎么分工",按上面答。详见 `CLAUDE.md` 两节 + `记忆系统-3/记忆系统-架构总览与三层分工-20260630.md`。
