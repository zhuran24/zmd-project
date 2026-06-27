# 老 cc_memory 会话开始注入「整合」讨论纪要

> 日期:2026-06-28(团队会议在本会话进行)。
> 范围:记忆系统问题 ① —— 老 cc_memory 的 SessionStart 注入(`cc_memory/hooks/cc_memory_readfirst.py`,即 readfirst)
> 是否跟 vnext T0 冗余、该 删 / 迁 / 留。6 席(3 codex + 3 claude)辩论收敛。
> 这份是讨论档案;末尾的「落地结论」分免费可做 / 需迁移工程 / 需 owner 裁决三档。

---

## 0. 一句话

**不是「删 vs 留」——是给一座早就在跑的过渡桥装一个退场条件,顺手清掉废料。** 那张覆盖域图本质不是「重复内容」,是一块**迁移债务仪表**:它诚实暴露「vnext 还没盖到这些地方」。所以它该**留着、但随迁移自动缩小、清零即自退**,同时立刻砍掉它身上的噪声和重复。

---

## 1. 背景 + 事实底座(coverage-mapper 实测)

**readfirst 三部分(全部每会话从 DB 现算、mode=ro 只读)**:
1. **「Read first」指针**:`pinned=1 AND status=active` 的条目摘要,当前 3 条(`cc-memory-meta-index` / `memory-runtime-protocol` / `offline-mode-autonomy-criterion`)。是**摘要指针不是正文**。
2. **覆盖域图**:全部 active(facts 18 + entries 102 = **120 节点**)按 id 前缀塞进 8 个硬编码命名域计数,不匹配的落 `其他:<prefix>`。真实输出 = `P1.2证明(30)·cc-memory系统(30)·codex协作(13)·rerank(6)·owner(4)·下载(3)` + **~27 个 `其他:X(1)` 单条散尾**。注释自称目的=「告诉 cc 有哪些话题存在→触发 search」=**未被注入正文内容的唯一 route-time 发现入口**。
3. **维护提醒**:DIRTY / 待审关系建议 / 上次 finalize 异常(条件触发,干净时无输出)。

**vnext T0 / SessionStart L0**:`session_start.py`→`zmem context --layers L0`,intents=["session-start"]。L0 = `activation.session_start_l0:true` 的卡,当前**恰 2 张、注的是卡【正文】**:`cc-memory-meta-index` [reference/P0]、`vnext-maintenance-discipline` [constraint/P0]。其余 19 张卡是 route-time(L1/L2)。

**计数**:cc_memory = 111 entries(102 active)+ 22 facts(18 active)= **120 active**,3 pinned;vnext = **21 卡**;同 id 交集 = 4(cc-memory-crud-gotchas / cc-memory-meta-index / codex-executes-claude-orchestrates / offline-mode-autonomy-criterion)。

**未迁 N ≈ 115**:120 个 active 里只有 3 个 pinned 拿到指针注入;其余 117 个非 pinned 零正文注入、只在域图露个域计数;其中仅 2 个有同 id vnext 卡 → **≈115 条既不被注、又无对应卡,唯一 route-time 发现入口就是这张图**。

**唯一真·会话开始双注入** = `cc-memory-meta-index`(readfirst 当 pinned 指针注一次 + vnext 当 L0 正文又注一次,同 id 同时刻两边开火)。

**顶部负载实测(owner-exp)**:readfirst 1239 字(覆盖域图独占 ~600)+ vnext L0 533 字 = **~1772 字 ≈ 半屏多**,上面还叠 MEMORY.md + CLAUDE.md。**5 个互相竞争的 P0/必读 = 等于没有必读**。

---

## 2. 六席立场(摘)

- **coverage-mapper(claude,事实底座)**:见 §1。纯事实、不下删留结论。
- **bridge-keeper(claude,留)**:覆盖域图是那 ~115 条未迁的**唯一**发现入口,删=把它们从「弱可见」打成「不可见」(比旧基线还差);"推"只对 21 张已迁卡存在、那 115 条一个钩子没钩——对【根本没有推】的人口,"带索引的拉" >> "什么都没有"。维护提醒 vnext 零对应(旧库还在被写,删了静默损坏没人盯)。元手册指针是改系统级行为前的必读闸。过渡现实:整库冻是未做 V2、冻结口径三处文档冲突,迁完前删发现桥=自断后路。**举证责任翻给删派:点名 vnext 用哪个机制让那 115 条 route-time 浮出水面?**
- **delete-advocate(codex,删)**:图是最该砍的摆设——pull 靠我 search、③ 已证我不可靠,占顶部槽却驱动不了可靠召回 = "假装覆盖"。元手册砍成 1 行+迁;维护砍成极小独立状态行。**诚实承认删了会塌两件**:(1)迁完前无提示会忘旧库仍历史权威;(2)维护异常会积压。**解法不是留整坨,是迁成卡 + 一行状态;迁不动的就承认没可靠召回、别拿图冒充能力。**
- **owner-exp(claude,体验)**:1772 字真配顶部的不到 ⅓;覆盖域图最大单块浪费(~600 字、我会扫一眼就划过、读"P1.2(30)"零可操作)。主张把图的 pull 降级成 push(route-time L1)。理想会话开头草图:1 行 meta-index 指针 + ≤3 张真 always-on 反射 + 条件 dirty 行,压到 ⅓。**原则:顶部槽只放「推」(恒真反射+条件状态),任何「拉」route 到 L1。**
- **migration-designer(codex,路径)**:把 readfirst 拆成「vnext 卡真相 + legacy 缺口提示 + runtime 状态行」。覆盖域图**不删、改造成"未迁 legacy 域图"**:建 `legacy_manifest.json`(`old_id→disposition/domain/card`),图只统计 `unmigrated` → 迁完一域自动消失、`其他:*` 压成 `long-tail(n)`。分阶段 P1(系统域:cc-memory/codex/precompact/离线/owner)→P2(证明主线+regression frame)→P3(工具长尾合并)→P4 退役硬条件。冻结:owner 拍;默认推荐=按条冻立即、整库冻等 manifest 清零。**旁证:`mem.py search --semantic` 当前报无效参数=旧库语义查部分坏了,"旧库可手动查"没那么硬。**
- **codex-indep(codex,reframe)**:**覆盖域图不是内容,是迁移债务仪表**(暴露"vnext 尚未覆盖这里")。三派各漏一点:删派漏掉删了 115 条失明;留派漏掉"靠我 search=旧系统死穴";迁移派漏掉**必须先定义退场条件**否则迁移只是口号、系统变成"俩都半权威、俩都会漂"。终态:vnext 卡=主动召回权威,旧 cc_memory=只读 archive/provenance/fallback,不再 SessionStart 注入、不再维护。实测:`settings.local.json` 现在**两个 SessionStart hook 并排在跑**=过渡桥早就在跑、只是没退场条件。

---

## 3. 收敛:crux 与化解

**crux**:覆盖域图的大域部分(P1.2 30/cc-memory 30/codex 13)——摆设(删派)vs 拐杖(留派)?

**化解(migration-designer + codex-indep 合力)**:既不删也不供着,是**「自萎缩的迁移债务仪表 + 硬退场条件」**——
- 它是**拐杖不是新架构**(承认 pull 不理想);
- 但删了那 115 条失明,所以**留**;
- 改造成**只统计未迁节点**(manifest 驱动)→ 迁完一域就消失 → 清零自退;
- 它的**真职责不是"解决召回",是"暴露 vnext 还没盖到哪"**(债务仪表)。

这把删派(诚实/砍浪费)、留派(115 条不能失明)、迁移派(路径)、体验派(压顶部)同时满足。

---

## 4. 落地结论(三档)

### A. 免费清理(不依赖迁移、现在就做、零风险)
1. **`cc-memory-meta-index` 双注入 → 去重**(readfirst 别再注它的 pinned 指针,vnext L0 已注全文)。
2. **~27 个 `其他:X(1)` 单条散尾 → 压成 `长尾(n)`**(就一条的破域、我不会为它 search、纯噪声)。
3. **整段元手册 header → 瘦成精简指针**。
4. **5 个互相竞争的 P0/必读 → 减载**(全标必读=没有必读)。
→ 会话开头压向 ⅓,顶部只留「推」型。

### B. 结构整合(真正的迁移工程)
1. 覆盖域图 → 改造成 manifest 驱动的「未迁 legacy 桥/债务仪表」,自萎缩、清零自退,最好由 vnext 一个 hook 顺手生成(不要两 hook 永久并排)。
2. 维护提醒 → 独立极小 runtime 状态行。
3. 分阶段迁库(每条给处置 card/merge/archive/drop/legacy-ref):P1 系统域 → P2 证明主线(补 regression frame)→ P3 工具长尾 → P4 收口。
4. **老 readfirst 退役硬条件**:manifest 无未迁 active + 全卡过 verify/eval + 高危域有金标准 + `mem.py check` 干净 + 四处文档口径统一 + fresh 进程验证。

### C. 只有 owner 能拍的
**冻结裁决**(MASTER_PLAN"上线即冻" vs council_B"迁移延后" vs CLAUDE.md"cc_memory 仍 authoritative" 三处冲突)。
**团队默认推荐**:按条冻立即生效(做成卡→旧库副本只当 evidence、不再更新);整库冻 + readfirst 退役等 manifest 清零再批;未迁条目旧库仍可写,新 route-time 知识优先写 vnext 卡。

---

## 5. 终态 + 关联

- **终态**:vnext 卡 = 主动召回 + 当前操作知识权威;旧 cc_memory = 只读归档/出处/兜底查,不再 SessionStart 注入、不再维护。每条旧知识三去向:迁成卡 / 标历史归档 / 明确不迁。
- **③ 连接**:覆盖域图是"拉"正是它不能当永久答案的原因(③ 证 pull 不可靠);但那 115 条没卡可推,迁完前 pull-图-当债务仪表是诚实的桥。修法=迁移(把 pull 变 push),仪表盯债务、自退役。
- **关联未决**:整库迁移/冻结(本议题 C)、③ 的"每回合看守"价位选择(见 `recall-trigger-discussion-20260628.md`)。

---

*纪要由本会话 team(coverage-mapper / bridge-keeper / owner-exp / delete-advocate / migration-designer / codex-indep 六席,3 codex + 3 claude)辩论收敛而成。事实底座经命令实测,顶部负载经字数实测。*
