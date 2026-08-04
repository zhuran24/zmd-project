---
id: memory-three-layer-coexistence-decided
kind: decision
title: 记忆分层定调(2026-08-03 owner 修订):两层活跃 + cc_memory 整库冻成只读档案
summary: 2026-08-03 owner 修订:cc_memory 整库冻结为只读档案,收件箱地位移交文件记忆层——现在是「两层活跃(文件记忆 + vnext cards)+ 一层档案(cc_memory)」,06-30 那句「仍现役、可写」与「整库冻非目标」就此作废。写入路由只有一条:新记忆写文件记忆层,达"必须每回合推送"门槛才做成 vnext 卡;cc_memory 只读只考古(search / read --body / impact / 跨层 find),写命令仅为档案订正、每次先提醒。06-30 仍然有效的部分:三层是【互补共存】不是新旧替代,整库迁移非目标;边与 impact 图永久留 cc_memory(vnext 结构上吞不下);按条 archive-on-promotion 是档案内部的整理手法(某条做成卡→archive 源条目防漂移;图枢纽条目留薄"图锚/指针节点"保边);不给 vnext 补通用低摩擦写入(摩擦=质量闸)。问"旧库冻没冻/还能不能写/这条写哪/为什么还往 cc_memory 写/要不要迁进 vnext"按此答。
scope:
  domains: [memory-layer-authority, cc-memory-freeze]
  paths: []
  symbols: []
status: active
priority: P1
triggers:
  intents: [memory-layer-authority, cc-memory-write-allowed, freeze-status, memory-write-location]
  keywords: [两层活跃, 一层档案, 文件记忆层, 收件箱, 冻只读, 整库只读, 旧 cc_memory 能不能写, 旧库还能写吗, 旧的不是只读, authoritative, 双活, 迁移真相源, 三层并存, 三层共存, cc_memory 冻, 这条写哪, 为什么还往 cc_memory 写, 往 cc_memory 写, 迁进 vnext, cc_memory 迁, archive-on-promotion, 按条 archive, 图锚]
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 现在新记忆写哪层
    - cc_memory 到底冻没冻、还能不能写
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
    - "owner 2026-08-03 拍板:cc_memory 整库冻结为只读档案,新记忆统一进文件记忆层(推翻 06-30 的『仍现役可写』与『整库冻非目标』)"
    - "2026-08-03 普查报告 §3.4/§3.6:cc_memory 仅 11 条 entries、07-14 起实际停写;三层写入路由税与跨层找卡病是冻结的直接理由"
updated_at: "2026-08-03"
---
> **2026-08-03 owner 修订(以此为准)**:cc_memory **整库冻结为只读档案**。分层现在是「**两层活跃 + 一层档案**」:
> ① **文件记忆层**(`~/.claude/projects/-home-zhuran24-zmd-pj/memory/`)= 新记忆的收件箱,从 cc_memory 手里接过来的;
> ② **vnext `cards/`** = 主动推送精选层(不变);
> ③ **cc_memory** = 只读档案,只供考古(`search` / `read --body` / `impact` / 跨层 `find`)。写命令保留只为档案订正,每次会先提醒一句、不拦。
>
> 直接作废的两条 06-30 口径:「旧 cc_memory 仍现役、可写」和「整库冻结非目标」。理由(普查 §3.4/§3.6):cc_memory 只剩 11 条 entries、07-14 起实际停写,却仍占着收件箱名分,于是每记一条都要先付「写哪层」的路由税,写完下次又跨层找不到。收件箱一交出去,这个问题类别整个消失。
>
> **没被推翻的部分**:边与 impact 图永久留 cc_memory(vnext 结构上吞不下),所以档案不是垃圾堆——`impact` 仍然是查牵连面的地方;按条 archive-on-promotion 作为**档案内部**的整理手法依然成立。

## 现行三层(08-03 口径)

① **文件记忆层** `~/.claude/projects/-home-zhuran24-zmd-pj/memory/` = 新记忆的收件箱,`MEMORY.md` 是索引、每张卡一个 `.md`;
② **v-next `cards/`** = 主动推送精选层,每轮按相关性注入完整内容,只放"必须每回合提醒的稳定知识"(push);
③ **cc_memory**(SQLite)= **只读档案**,考古用 `search` / `read <id> --body` / `impact <id>` / 跨三层 `find <id>`;带图(边)+ 全量历史。写命令保留只为档案订正,每次先提醒一句、不拦。

(还有 harness `*.md` 那一薄层:SessionStart 加载的跨库索引 / always-visible 行为反射 / volatile resume 锚。)

## 写入路由:只有一条

**新记忆写文件记忆层**,达"必须每回合主动推送"门槛才做成 v-next 卡。cc_memory **不再是收件箱**——它 07-14 起就实际停写,只剩 11 条 entries,却仍占着收件箱名分,于是每记一条都要先付"写哪层"的路由税、写完下次又跨层找不到。

**不给 vnext 补通用低摩擦写入**(没好触发的卡要么不被推、要么逼出垃圾触发=噪声;authoring triggers 的摩擦=质量闸)。

## 为什么不整库迁进 vnext

vnext 结构上吞不下 cc_memory 的核心能力——边的自动发现 + impact 图、大规模语义检索、跨会话变更感知。迁移**只搬内容、不搬边**,所以边和图永久留 cc_memory,整库迁移始终不是目标。

**档案内部的 archive-on-promotion**(06-30 原文,仍然有效):某条知识做成 v-next 卡后 → `archive` 它的 cc_memory 源条目(status→archived,从 boot/export/召回消失但仍可 read/search,防同一记忆两边漂移)+ 留指针。**图枢纽条目**(被别的活条目依赖)别直接 archive——留一个薄"图锚/指针节点"在 cc_memory(只含边 + 指向卡片),内容进卡片、边留 cc_memory。

问"旧库冻没冻 / 还能不能写 / 这条写哪 / 为什么还往 cc_memory 写 / cc_memory 要不要迁进 vnext / 三层怎么分工",按上面答。详见 `CLAUDE.md` 的记忆系统一节 + `记忆系统-3/记忆系统-架构总览与三层分工-20260630.md`。
