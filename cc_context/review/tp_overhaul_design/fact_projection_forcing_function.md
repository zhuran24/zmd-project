# 知识侧 forcing function 设计 — fact↔projection 防再漂 gate (km-forcing / Q3)

> 状态: v1 设计 + 可工作实现草稿 + 实证 (零误报 no-op + 6 fixture 全过)。
> 待 km-arbiter 确认 fact 清单定稿口径、km-skeptic 确认语义漂移降级。
> 铁律: 本团队只产出方案+草稿; live 文件 (check_memory_tree.py / 记忆树) 由 team-lead 落地。
> 实现草稿: 同目录 `fact_projection_gate_design.py` (可独立 `python` 跑自检)。

---

## 0. 它治什么 (team-lead 三需求)

知识侧 normalize 出「抽象事实层 (fact 节点) + 投影回指」结构 (= workflow_design.json
的 factmap: 7 个 `fact-*` 节点 + 每个的 `links_from_projections`)。但**这套治理本身
不能再变成靠人记得维护、会再漂的负担** (否则就是同一个病换层)。需要 forcing function
让下列三种情况**自动报红** (类比 authoritative_numbers 的 pytest gate):

| # | 需求 (team-lead 原文) | 本设计如何抓 |
|---|---|---|
| 1 | 新增投影/规则节点, 却没接到任何抽象事实 (孤立于事实层) | **检查 2** 孤立投影: 节点声明 `derives_from` 却没在正文 `[[link]]` 回去 |
| 2 | 某 fact 节点没被任何投影回指 (死事实) | **检查 1** 死事实: 没有任何投影 `derives_from` 它 (反向索引派生, 非正文 link 计数) |
| 3 | 投影声称依据的事实与事实节点实际内容漂移 | (a) **检查 2 内含**: derives_from 引用完整性 (目标真存在/真是 fact/正文落地 wikilink); (b) **检查 3** (warn 级): 节点正文引用的仓库文件路径在文件系统真存在 (km-skeptic 认可的「真值源=文件系统」那类)。语义层漂移无机器真值源, 不测 — 见 §2 |

注: 需求 1 的字面是「投影没接事实」, 我**不**强制「每个规则节点都必须接事实」(team-lead
明确要求别强制), 而是**只查已经显式声明要接事实的投影有没有接成** —— 即把「该不该接」
的判断交给节点作者的显式声明, 脚本只验证「声明了就得接成」。详见 §1 铁律 A。

---

## 1. 三条设计铁律 (从 authoritative_numbers 先例 + 本项目实测约束推出)

### 铁律 A — opt-in, 绝不猜
节点只有 frontmatter **显式声明角色**才进入检查范围:
- fact 节点声明 `metadata: node_role: fact`;
- 投影节点声明 `metadata: derives_from: <fact-slug>` (可多个: flow list `[a, b]` 或 block list)。

脚本**绝不**去猜「这条规则像不像某 fact 的投影」。理由 = authoritative_numbers 的核心
教训: 扫散文猜语义必然到处误报、淹没真信号 (它的 docstring 明写「deliberately does NOT
scan prose docs」)。这同时直接满足 team-lead「别强制每个节点都必须挂事实 (有些天然纯事实/
纯参考)」: **没声明角色的普通节点, gate 完全不管它**。

### 铁律 B — 关系单一真值源, 其余机器派生 (km-skeptic 反讽门槛 v2 收敛)
**v1 → v2 的关键修正**(km-skeptic catch, 我接受): v1 让 fact 维护 `projections:` 清单 +
投影维护 `derives_from:` 清单 + 查两者对称。但那两份是**同一关系的冗余拷贝**, `projections:`
这张表本身会漂 —— 等于「拿一个会漂的检查去守另一个会漂的东西」, 正是本治理要避免的「同一个
病换层」, 也违反 memory-currency-protocol「能指针就别 copy 值、嵌值=drift 负债」(我自己写的
fact body 都引这条, v1 却破了它)。

**v2 正解**: fact↔投影关系**只存一处** = 投影节点的 `derives_from`(投影作者写投影时就知道
的局部知识, 且本来就要和正文 `[[fact]]` wikilink 耦合)。fact 侧**不**维护清单; fact 的「我有
哪些投影」由全树 `derives_from` **反向派生**(机器算, 零维护)。于是**没有第二份表可漂, 双向
闭合检查随之消失** —— 这才是「不引入新补丁」。需求 3 的语义漂移无机器真值源, 诚实交回人工/
审查, 不进 gate (跟 authoritative_numbers 把「README 散文是否还对」留给人、只机器化
「core==recompute」完全同构)。

### 铁律 C — fail-soft 分层, 对现状零影响
- **block** (errors, returncode 1, 同现有 isolated/unresolved): 关系硬不变量 —— 死事实 /
  孤立投影 / derives_from 指向不存在或非-fact 的 slug。这些有确定真值源、误报风险极低。
- **warn** (非阻断打印): 检查 3 引用完整性 —— 节点正文引用的仓库路径在文件系统不存在。
  之所以 warn 不 block: 节点正文路径可能有历史/示意成分, 误报不该阻断 push; 但漂了 (脚本
  被删/改名→节点烂尾) 要响亮提醒。真值源仍是硬的 (文件在不在), 只是后果分级更轻。
- **静默 no-op**: 「fact 层整个还没落地」(无任何 `node_role:fact` / `derives_from` 节点),
  或检查 3 没传 repo_root。gate 在 fact 层为空时必须是**纯加法**, 对当前 95 节点树零影响
  (已实证, 见 §4)。
- 注: v1 的「双向闭合 / 半闭合 warn」已随 `projections` 清单一起砍掉 (单一真值源下不存在
  「半」闭合); 现在唯一的 warn 来源是检查 3。

---

## 2. 为什么这些具体取舍 (回应两个 teammate)

### 回 km-arbiter Q1 — 脚本不写死任何 slug
factmap 的「7 fact + 各自投影」还可能调整。所以脚本**不写死**任何 slug, 也不内嵌「应有
几个 fact」。真值源 = 投影节点的 `derives_from`(关系唯一记录处)+ fact 的 `node_role: fact`
(只声明身份)。fact↔投影清单怎么改 → 改投影的 derives_from **一处**, gate 自动跟着走,
**永不用动脚本、也没有第二份表要同步**。这是 authoritative_numbers「真值进 core node、test
只查 core==live」的同构搬运。

### 回 km-arbiter Q2 + 检查 1 的关键正确性 — fact 的 repo 锚定
**实测**: factmap index_size_note 建议挂载的索引父节点 (`collaboration-rules-index` /
`gpt-delivery-acceptance-discipline` / `verification-hardening-ladder`) **在 repo
cc_context/memory 树里不存在** —— 它们是 harness-only 合成节点 (sync_memory_to_harness.py
动态生成, repo 侧无文件)。而 check_memory_tree.py **只扫 repo 树**。推论:
- fact 节点的「被认领/不死」(检查 1) 必须靠**真实存在的 repo 投影节点**
  (`root-cause-over-symptom` / `lazy-mode` / `no-gpt-concurrency-field` 等, 见 §5 清单)
  用 `derives_from: <fact>` 认领它 + 正文 `[[fact]]` wikilink 落地。harness-only 节点的
  认领**不计入** repo gate —— 这是**特性不是 bug**: 它强制每个 fact 必须有 repo 锚,
  否则 repo gate 永远抓不到它漂没漂。
- fact 节点**不进 MEMORY.md 顶层** (factmap 设计省 24KB 预算)。故本 gate 把
  `node_role:fact` 节点**豁免**现有 coverage 检查 (否则现有 `known - covered` 会把
  fact 当 missing 误报)。落地点见 §3。

### 回 km-skeptic — 反讽门槛 (v2 的来源)
km-skeptic 的门槛: 新加的 forcing 检查若没有机器可判真值源, 就是「拿会漂的检查守会漂的
东西」= 又一层补丁。这把尺子直接削掉了 v1 的双向闭合: 那里 fact 的 `projections:` 清单
没有独立真值源(它就是关系的第二份手抄), 会漂。v2 收敛为**关系单一真值源 = derives_from**,
fact 被投影集机器反向派生 —— 没有第二份表, 就没有「守一个会漂的表」的问题。需求 3 的语义
漂移确实无机器真值源, 所以**不测**(交人工/审查), 而不是硬测一个会漂的代理。这是诚实的能力
边界, 不是偷懒 —— 硬凑会复刻 authoritative_numbers 明确拒绝的「扫散文 → 到处误报」失败。

---

## 3. 落地接入 (team-lead 把草稿合并进 check_memory_tree.py)

**扩展 check_memory_tree.py, 不新建 test。** 因为它已挂 `preflight_gate.py [11/17]`
→ CI (`.github/workflows/project_foundation.yml`) + pre-push hook (`preflight_gate.py
--hook`)。合并即**零额外接线**获得 CI + pre-push 双覆盖。三处改动 (草稿里函数照搬):

1. **block 检查** — `main()` 内 `errors.extend(_check_links(...))` (line 311) 后加:
   ```python
   fp_errors, fp_warnings = check_fact_projection_layer(memory_dir)
   errors.extend(fp_errors)
   warnings.extend(fp_warnings)   # v2 不产 warning, 但保留接口对称便于将来扩展
   ```
2. **coverage 豁免** — `_check_links` 内 `missing = sorted(known - covered)` (line 123) 改:
   ```python
   missing = sorted(known - covered - fact_nodes_to_exempt_from_index(memory_dir))
   ```
   (或把 fact 豁免集作参数传入, 避免重复 load; 草稿给的是独立函数版便于审阅。)
3. 草稿里的 `_scalar` / `_list_field` / `_Node` / `_load_nodes` 并入 check_memory_tree.py
   的 helper 区 (与现有 `_frontmatter_name` 同风格, 都是宽松逐行解析 — 节点 frontmatter
   **不保证合法 YAML**, description 里有裸 `:` 和 Windows `\` 路径, 不能用 yaml.safe_load)。

**检查 3 (引用完整性) 启用**: 合并时把 `check_fact_projection_layer(memory_dir, repo_root=PROJECT_ROOT)`
传上 repo_root 即开 (check_memory_tree.py 里已有 `PROJECT_ROOT`)。不传则只跑检查 1/2 (检查 3
静默跳过) —— 给将来想关掉它的逃生口, 也让单测无 repo 上下文时不误跑。

无需改 preflight_gate.py / CI yaml / pre-push hook — 它们调的是 check_memory_tree.py
的退出码, 退出码语义不变 (errors→1, 否则→0; 检查 3 是 warn 不影响退出码)。

---

## 4. 实证 (非眼判)

`python cc_context/review/tp_overhaul_design/fact_projection_gate_design.py`:
- **当前 repo 树 (fact 层未落地)**: `未启用 ... 跳过` → exit 0。**零误报 no-op 坐实** (铁律 C)。

回归 fixture × 9 (`test_fact_projection_gate.py`, 可 `python` 直跑也可 pytest 收集, 9/9 过):
| test | 构造 | 期望 | 实测 |
|---|---|---|---|
| empty_layer_is_noop | 全是普通节点 | 0 err 0 warn | ✅ |
| healthy_relation_single_source | fact 不列投影, 2 投影 derives_from 认领 | 0 err | ✅ |
| dead_fact_blocks | fact 没投影 derives_from 它 | 死事实 err | ✅ |
| **fact_with_only_prose_link_still_dead** | fact 仅被散文 `[[link]]` 提到、无 derives_from | 死事实 err | ✅ (v1 的 indeg 版会漏判活, v2 抓得到) |
| orphan_projection_declares_but_no_wikilink | 声明 derives_from 正文没链 | 回指没落地 err | ✅ |
| bad_derives_from_targets | derives_from 指向不存在/非 fact | 不存在+非fact err | ✅ |
| **no_second_list_to_drift** | fact 残留旧 projections 字段 | 被无视, 0 err | ✅ (证明无第二份表可漂) |
| **reference_integrity_warns_on_missing_path** | 正文引用不存在路径 + URL + 单层词 | 仅不存在路径 warn | ✅ (URL/单层词不误报) |
| reference_integrity_off_without_repo_root | 不传 repo_root | 检查 3 不跑 | ✅ |

加粗三条是关键证据: 死事实用 derives_from 反向索引(硬关系)而非正文 link 计数; 残留
projections 字段被完全无视; 检查 3 引用完整性只对「明确像路径」的形态报红、误报边界守得住。

**自查附注**: 写检查 3 fixture 时 repo_root 层数一度写错 (`parents[3]` vs `parents[2]`,
两个文件基准不同), 被回归直接抓红 → 修正。即「fixture 本身就是 forcing function 的解药」
的实例: 错误不靠眼判, 靠不能回归的 case 兜住。

---

## 5. fact 落地时配套的 frontmatter 约定 (给 km-arbiter 的 normalize 落地用)

fact 节点 (示例, 真 7 个 fact 的 slug 以 km-arbiter 收敛为准。**注意: fact 侧不写
projections 清单** —— v2 关系单一真值源在投影侧):

> **文件名约定 (km-arbiter 查实, 对 harness 召回至关重要)**: fact 节点文件名必须用
> `feedback_fact_<slug>.md` 前缀, **不是** `fact_`。因为 `sync_memory_to_harness.py`
> 的 `COPY_PREFIXES` 白名单只认 `feedback_/project_/reference_/user_` —— `fact_` 前缀
> 不会被投影到 harness 召回树 (AI 自动召回读不到)。用 `feedback_` 前缀还附带正确副作用:
> sync 重建索引时自动把 fact 归入 harness 的 `collaboration-rules-index` 父节点正文,
> 恰好实现 factmap 想要的「fact 挂进 collaboration-rules-index」(在 harness 侧自动发生,
> repo 侧那个父节点本就不存在)。frontmatter `name` 仍是 kebab。**本 gate 只认 frontmatter
> name, 对文件名前缀零依赖 (已实证), 所以这条约定只影响 harness 投影、不影响 gate。**

```yaml
# 文件: feedback_fact_forcing_function_beats_stronger_rule.md
---
name: fact-forcing-function-beats-stronger-rule
description: <一句>
metadata:
  node_type: memory
  type: feedback
  node_role: fact
---
正文里照 factmap body 写, 含派生投影的 [[wikilink]] (relate 行)。
```
投影节点 (在现有规则节点 frontmatter 加一行 + 正文补一个 wikilink) —— **关系只在这里记一次**:
```yaml
metadata:
  ...
  derives_from: fact-forcing-function-beats-stronger-rule
```
正文任意处出现 `[[fact-forcing-function-beats-stronger-rule]]` 即满足检查 2; gate 全树扫
derives_from 反向派生「这个 fact 有哪些投影」, fact 侧零维护。

**repo 侧真实可锚的投影节点** (factmap 投影中确认存在于 repo 树的, 检查 1 靠它们 derives_from
认领 fact): root-cause-over-symptom · lazy-mode · no-reply-means-agree ·
workflow-approval-not-avoidance · no-giveup-options · no-rest-suggestions ·
directly-state-core-finding · no-gpt-concurrency-field · no-gpt-pro-outsource-core ·
no-causal-claim-from-n1 · verify-solver-param-claims · memory-currency-protocol ·
verification-independent-backstop。
**harness-only (repo 树没有, 不能作 repo 锚)**: verify-before-claiming ·
hallucination-* · 全部 gpt-delivery-* · 全部 verification-*-line-* ·
verification-hardening-ladder · gpt-delivery-acceptance-discipline。
→ 每个 fact 至少要被一个上面"repo 侧真实"的投影回指, 否则在 repo gate 里成死事实。

---

## 6. 边界与已知局限 (诚实声明)

- **不测源内容漂移 (类型 C) — 能抓但不值, 不是抓不到** (km-skeptic 反例精确化): 一种漂移
  本设计放过 = fact body 内容被改、projections/derives_from 引用图纹丝不动 (投影现在挂在一个
  变味的 fact 上)。这正是 team-lead 原文「投影声称依据的事实与事实实际内容漂移」的字面情形。
  **更正我早先的措辞「抓不到」**: 它**能**不靠 NL 抓到 —— 用 content-hash (项目 `sync_doc_subjects.py`
  第 15-16/220-221 行已实现: projection marker 嵌 `sha256:<源 field hash>`, 源变 hash 变即报)。
  但对 fact↔memory 投影**抓它不值**, 三条:
  ① **性质不匹配**: docs 的 marker-sha 是给「投影=从 subject field 渲染生成的副本」(强同步)设计的;
     fact↔memory 投影是**松散语义引用** (lazy-mode 是独立写的规则, 「派生自」ownership fact 不是
     从 fact body 生成), 把强渲染机制硬移植到松散引用上用错了地方。
  ② **必误报到废**: fact body 任何措辞微调 (改错字/补例子) 都翻转 hash → 所有投影标 stale →
     owner 被迫复核一堆没歪的投影。这跟拒 NL 比对要躲的「误报淹没真信号」是同一个病 (只是从
     NL 误报变 hash 误报)。
  ③ **真值源是假的**: hash 能确定性算 (机器真值), 但「hash 变 = 投影需复核」这个**推论**不是
     真值 (hash 变常是无关编辑)。守的是「源动过没」的代理信号, 代理触发的复核负担落回人 = 又一
     层要人维护的补丁 —— 正是反讽门槛要拒的。
  → 经得起 owner 问「那为什么 docs 那边用了 hash」: 答 = docs 是渲染同步、memory 是松散引用,
  两种关系。语义/源忠实度交人工/审查, 不进 gate。
- **harness 树不在 gate 范围**: harness 侧的 fact/投影漂移本 gate 不管 (check_memory_tree
  只扫 repo)。harness 一致性靠 sync_memory_to_harness.py + check_harness_links.py (既有工具)。
- **依赖 frontmatter 显式声明**: 作者忘了写 `node_role:fact` / `derives_from`, gate 当它
  普通节点放过 —— 这是 opt-in 的代价, 也是它零误报的来源 (宁可漏管, 不误拦)。这与 owner
  对 Stop hook 的同款取舍一致 (低召回、绝不误报)。
