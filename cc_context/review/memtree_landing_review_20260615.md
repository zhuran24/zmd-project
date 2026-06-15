# 记忆树重构 — 讨论过程 + 落地 + 修复过程(2026-06-15/16)

> 这份 md 记录这套记忆树工具的完整轨迹:发现问题 → 团队+外审讨论 → 落地 P0–P3(repo 侧)→ 一轮外审挑出 3 处偏离 → 核实+修复(第 8 节)。
> **供随包(文件区)代码审查时作背景**:1–7 节是讨论与落地(每阶段分「讨论决定了什么」「实际落地了什么」两栏,便于逐条核),第 8 节是后续修复过程。

---

## 0. 背景:记忆树现状与痛点

一棵"逻辑知识树"有多个物理投影:
- `cc_context/memory/`(repo, ~104 节点, snake/kebab 混名, 含手工 `MEMORY.md` 索引)= owner 手维护的协作记忆。
- `_cc_live_memory/` = cc_context/memory 的逐字节镜像(远程可见)。
- **harness 召回树** `~/.claude/projects/<slug>/memory/`(~153 节点, kebab)= **Claude Code auto-memory 运行时真正召回读的树**;按节点 frontmatter `description` 语义匹配注入, **不读 wikilink**, `MEMORY.md` 有 ~24,576 B 注入上限。
- `cc_context/harness_memory_snapshot/`(~49)= harness-only 节点的手动 git 备份。

实测痛点:读写分家(召回读 harness / owner 维护 repo, 单向手动 sync 漏跑就读不到)、MEMORY.md 顶 24KB 红线、41% 节点不在平铺索引、同步工具碎片化无总闸、harness-only 备份靠手动、失效链全 fail-soft、现状值无强制函数。

---

## 1. 重构方向团队讨论(2 Claude + 2 codex 4 轮)

**讨论决定了什么(收敛 = harvest-only):**
- 真相源之争(arch 主张 harness=源 / gpt-eng 主张 repo=源)被 gpt-red 一句话重塑:**harness 有原生写入(AI 会话直接写它),所以它是并列写入源**,任何单向同步都静默丢一边。
- 收敛:**repo 是可审计源, live harness 是运行时工作副本 + 写入入口, repo 永不自动反写 active harness**(harvest-only)。
- migrate 物理裁决:harness 不入 git、CI 看不见 → "harness 当唯一源"不可达;**保留 `_cc_live_memory`**(远程可见, CI block 项)。
- 红队铁律:绝不静默丢节点;同名节点 drift 是最骗人的失败。

---

## 2. GPT Pro 外审("你怎么看", 已收回)

**GPT 当时给的(应被落地遵守):**
- 认同 harvest-only 是"唯一真正稳的拓扑";命名改 **L2 = harvest 账本(不是 deploy 目标)**,免得有人拿它反写 live。
- 四层:① live harness=运行时工作副本 ② repo harvest ledger=可审计账本(CI 可见) ③ curated memory(cc_context/memory + _cc_live)④ generated index(MEMORY.md 从 description/单源生成)。
- 钦点回归样本:`zmd-round2-dispatch-fix-state` 在 repo/harness 间漂移 + repo MEMORY.md 索引摘要 stale,现有 gate 没抓到 → 证明"MEMORY.md 自动生成是止血钳"。
- 落地顺序 **P0 冻结观测 → P1 无副作用总闸 → P2 harvest → P3 generated MEMORY → P4 schema/命名**。
- 四条硬规则:single command 但绝不自动写 live harness;slug resolver 降级(只决定读哪棵);**pending 要收同名 drift 不只新增**;description 质量 gate 分级。

---

## 3. 落地 P0/P1/P2

| | 讨论决定 | 实际落地(待 GPT 对照代码核) |
|---|---|---|
| **P0 冻结观测** | repo↔harness 对账, 抓同名 drift, 不写 | `cc_context/tools/memory_harvest.py --check` + `cc_context/knowledge/memory_harvest_manifest.json`;按 frontmatter name 对账,**语义**(body+desc hash)抓同名 drift,区分"有意 stub"(handoff 现状源)与真 drift;**只读 harness** |
| **P1 无副作用总闸** | single command 串现有检查, 不写 harness | `cc_context/tools/sync_knowledge.py --check`,串 9 项子检查(check_memory_tree / sync_doc_subjects / authoritative_numbers / sync_memory_to_harness --check / stamp_living_status / check_harness_links / memory_harvest / description_freshness / lockfile),两级 BLOCK/warn,**不写任何文件** |
| **P2 harvest** | 只读收割 live→repo, 新增/同名变更分开落盘, secret 扫, pending 存在不报红 | `memory_harvest.py --harvest` → `cc_context/harness_memory_harvest/`:`new/`(49 harness-only)+`updates/`(同名 drift 存证)+ secret `quarantine/` + manifest;**实测写前后 harness .md 数与 mtime 不变 = 不写 harness** |

---

## 4. P3 设计岔口 + 第二轮团队讨论

**实测撞墙:** 朴素"把 MEMORY.md 摘要换成节点完整 `description`" → 35,224 B,**超 24,576 cap 43%**(description 为通道② 召回写、长且带分类前缀)。

**第二轮讨论收敛:**
- **arch 双通道重塑**:MEMORY.md = "无条件注入的小段"(通道①, 24KB 稀缺);每节点 description = 按 query 召回(通道②, 不受 24KB 约束)。**那 64 个"挂父索引"的节点召回侧没丢**(各自 description 仍在通道② 匹配)→ "153 塞不进 24KB"是伪问题。
- **migrate 实测**:harness 153 节点 frontmatter 全有 description;**现有 MEMORY.md 摘要本就是从 description 抄来的、且已在漂**(owner-chat-shorthand 索引行比节点旧)→ 新增 index_summary 字段 = 第三份会漂副本(反向操作)。
- **gpt-red**:漂移不靠"摘要放哪"解决, 靠 **body-sha gate**(正文变了摘要没变就红);绝不静默丢;优先级分级若用要硬分类。
- **gpt-eng**:给完整 5 字段系统(index_summary/recall_priority P0-P4/index_group/surface_policy/recall_queries)+ 贪心分配器 + surface_report + BM25。

**scope 裁决(owner 选极简):** lead 推荐极简(effort-matches-stakes:个人 KB 不上搜索引擎级机器),吸收 gpt-eng/gpt-red 的安全内核(staleness gate + 绝不静默丢)但不上 5 字段系统;若将来树涨大/预算长期溢出/recall-miss 反复才升完整。**owner 确认极简。**

**关键转折(diff 实测推翻了一步收敛):** 极简最初按 arch/migrate 的"直接用 description 截断"做生成器,但**完整 104 行 old→new diff 显示截断 REGRESSED 质量**(丢 actionable 尾巴如"提交前想清楚"、加冗余前缀"zmd "/"抽象事实:"、半句被"…"砍)。→ 证伪"直接用 description";**改走方案 A**。

---

## 5. 方案 A = 实际落地的做法(请重点核这一节是否符合讨论)

**讨论决定(方案 A):** 把现有**好的手写摘要**回种进各节点 frontmatter 的 `index_summary` 字段(单一来源、与节点同住,不是 AI 重生成、不是截断 description),生成器从 index_summary 出索引;body-sha gate 抓"正文变了 index_summary 没跟上";保 lockfile(MEMORY.md == 重生成)。

**实际落地:**
1. `cc_context/tools/seed_index_summary.py`:解析 repo MEMORY.md 每条 `- [title](file.md) — summary`,把 summary **原样**回种进 file.md frontmatter 的 `index_summary`(双引号 YAML 转义),**同时写 cc_context/memory + _cc_live 两镜像**保字节一致;写后自校验 round-trip。已 `--apply` 104 节点 × 2 镜像,**0 不一致**。
2. `cc_context/tools/gen_memory_index.py`:从节点 `index_summary` 生成 MEMORY.md(缺失才回退截断 description),硬 24KB cap 超了报红不静默裁,输出旁路 `cc_context/knowledge/MEMORY.generated.md`(**不动正本**)。实测生成版 **逐字节 == 现 MEMORY.md(0 行差异), 21,543 B** = 零质量损失。
3. `cc_context/tools/check_description_freshness.py`:记录每节点 (body_sha, desc_sha, idx_sha) 基线;正文变了但 index_summary/description 没跟上 → 报 stale。已 seed 104。
4. **lockfile gate** = `gen_memory_index.py --check`:MEMORY.md ≠ 从 index_summary 重生成就 exit 1。已接进 P1 总闸。
5. 总闸 `sync_knowledge --check` 全绿 exit 0;`check_memory_tree` exit 0;_cc_live 字节一致。

---

## 6. 已知边界(诚实声明,请 GPT 一并核是否是合理的阶段切分)

- **只完成 repo 侧。** 修的是 repo `cc_context/memory/MEMORY.md`(owner 策展源 + GPT 钦点 stale 行所在)。
- **AI 召回真正注入的 harness MEMORY.md 尚未单一来源化** —— 这是 A 的"recall 侧"另一半(传播 index_summary 到 harness 节点 + harness MEMORY.md 也从 index_summary 生成, 要处理 harness 153 节点的 24KB 预算 + arch 双通道), 列为下一阶段。
- 因此当前 repo 节点有 index_summary、harness 节点没有 → check_memory_tree 报 71 投影 + 32 共维护 drift **warn(非阻断)**,是这个半迁移态的预期产物,将在 recall 侧完成时清除。
- P4(frontmatter 格式统一 / snake-kebab 命名统一)按讨论放最后,未动。

---

## 7. 请 GPT 审的问题

对照随包(文件区)的实际代码与上述讨论:**落地的这个记忆树改动是否符合我们的讨论?有哪些地方偏离了讨论?** 重点:
- 方案 A 的实现是否忠实于"单一来源 + 保质量 + body-sha gate + lockfile + 绝不静默"?
- harvest-only 铁律(不写 active harness)在 P0/P1/P2 代码里是否真守住?
- "repo 侧先做、harness 侧后做"的阶段切分是否合理,还是漏了 recall 侧导致 GPT 钦点的 stale 问题其实没在召回侧解决?
- 有没有引入新的漂移面 / 静默失败 / 偏离四层模型的地方?

---

## 8. 后续修复过程(P3 落地后又过一轮外审 → 核实 → 修)

P3 落地后,对照代码又挑出 **3 处偏离** + 几条风险。处置纪律:**先逐条独立核实问题确实存在,再动手修**(不裸信外审结论)。3 处全部核实为真(非误报),已修:

| # | 指出的偏离 | 独立核实 | 修复 |
|---|---|---|---|
| 1 | 钦点回归样本 `zmd-round2-dispatch-fix-state` 并没真正修好 —— 方案 A 的 seed 把**旧的 stale 摘要原样**种进了 `index_summary`,`--seed` 又把它接受成基线 → 那个"被点名的 bug"反而被固化 | seed 确实逐字回种了 MEMORY.md 里的旧摘要;freshness 基线把 stale 态当成了"已审"。属实 | 把该节点 `index_summary` 对齐到当前正文态;重跑 `gen --apply` 同步 MEMORY.md 正本;重新接受 freshness 基线(并发的另一会话也同步更新了该节点正文) |
| 2 | `check_description_freshness` 与 `MEMORY.md == index_summary`(lockfile)两个 gate 接进了总闸却挂在 **warn 档** —— 子工具 exit 1 被总闸降级成不阻断的 WARN,复刻了"失效链 fail-soft"原始病 | `sync_knowledge.CHECKS` 里这两项 blocking 字段确为 False。属实 | 两项 blocking 改 True(BLOCK):任一失败总闸 exit 1 |
| 3 | `gen_memory_index` 不是真 lockfile,且节点缺 `index_summary` 时**静默回退**到"截断 description" —— 既掩盖缺失,又可能悄悄换进低质摘要 | `regenerate()` 里 `summary is None` 分支确会回退截断,无任何校验/报错。属实 | 加 `validate_index_nodes`:索引引用的节点文件缺失、或节点缺 `index_summary` → 直接报错并拒绝写正本(`--check` 退 1、`--apply` 拒写);docstring 写清边界 —— 它只刷新摘要文本、不重建标题/结构,是"摘要刷新器"非完整 lockfile |

修复后验证:`sync_knowledge --check` exit 0(105 节点;freshness stale 0;lockfile 0 行差异)、`check_memory_tree` exit 0、`cc_context/memory` 与 `_cc_live_memory` 逐字节一致。

**仍未做(诚实声明):** harness 召回侧单一来源化(方案 A 的另一半,recall 真受益处);P1/P2 风险项 —— freshness 对全新节点应 fail 而非放过、harvest 同名静默覆盖、slug resolver 4 处硬编码不统一、gen 完整 skeleton-hash lockfile(能抓标题/结构改动)。
