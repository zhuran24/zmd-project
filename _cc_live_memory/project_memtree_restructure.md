---
name: memtree-restructure
index_summary: "记忆树重构现状: 2026-06-16 owner 拍板采纳 GPT typed-graph 重写、走『收核心不收覆盖式快照』; 已落地 memory_system+memgraph 核心(impact query 可用)叠加进仓库、零覆盖现有治理层/CI; codex+Claude opus 双模型对抗审查交叉校准, 6 个 verdict 全 rely_with_caveats、无 P0、核心当下可用; 根因=硬边判定靠正文措辞+slug 命名巧合, 待硬化(见正文); v3 只加 bootstrap 入口未修 soundness; 全部未提交。"
description: "记忆树重构。2026-06-16 GPT 外审(会话 6a303556)点破前期『做偏了』(owner 真意图=fact-entry 依赖图: 改 fact 只反查 DEPENDS_ON 它的 entry; 团队却做成 Markdown 治理层), owner 拍板采纳 GPT typed-graph 重写。**已落地(未提交)**: 收核心(cc_context/memory_system + tools/memgraph.py, impact query)叠加进仓库、零覆盖现有治理层/CI(GPT 壳化版会掏空 check_memory_tree CI gate 故拒收), edges 纯正文 infer 不收 GPT 快照。独立验证全绿(真实 106 节点 impact 实证可用、unittest、ruff 0、GPT 谎报过 ruff 干净)。**codex + Claude opus 双模型对抗审查交叉校准**: 6 个 verdict(3 lens×2 模型)全 rely_with_caveats、无 do_not_rely、无当前真漏报 P0, 核心当下可用; codex 第一次用结果可信(核心 finding 被 opus 独立印证、且独有 SUPERSEDES 等发现)→『wf 用 codex』偏好成立。根因=硬边判定全靠正文措辞+slug 含 'fact' 巧合无显式声明, 待硬化(见正文)。caveat: 别给 fact 改名、引用 fact 要显式同行 wikilink。v3 只加 bootstrap 新会话入口、没修 soundness、且高危带 CLAUDE.md 改写(待 diff)。"
metadata:
  node_type: memory
  type: project
---

# 记忆树工作 — typed memory graph 落地 + 双模型审查

## ✅ 2026-06-16 落地闭环 + 双模型审查 (owner 拍板「做」)
owner 拍板采纳 GPT 的 typed-graph 重写, 走我推荐的 **「收核心、不收覆盖式快照」**。已落地(**全部未提交**):

- **收的核心(纯新增, 零覆盖)**: `cc_context/memory_system/` (graph/freshness/indexer/frontmatter/cli) + `tools/memgraph.py` + `tools/resolve_harness.py` + `tests/test_memory_system.py` + `cc_context/memory_graph/` (账本 facts/events/changes + README)。`edges.jsonl` **不收 GPT 快照的 30 条**, 纯靠我当前正文 infer。
- **拒收的(会破坏现状)**: GPT overlay 还带 `MEMORY.md`/`description_review.json` 快照 + 治理工具壳化。**check_memory_tree 壳只调 `memgraph check`, 会掏空现有 487 行 CI gate**(丢掉 fact 投影契约/INSTANCE/stamp/归档悬挂/unresolved 等, `preflight_gate.py:605` 直接调它)= 假绿, 全部拒收。现有治理层 + CI **一字未动**。
- **独立验证(不信 GPT 沙盒; GPT 谎报过 ruff 干净实际 3 error)**: 真实 106 节点 284 边/32 硬边; `impact` 实证捕到本会话新增的 minimal-open-prompts/memtree-restructure; unittest 全过; ruff 0; 现有 check_memory_tree CI gate 仍 exit 0。
- **双模型对抗审查交叉校准 (3 lens × {codex, Claude opus})**:
  - 6 个 verdict **全 rely_with_caveats、无 do_not_rely、无当前真漏报 P0**。当前数据 impact 零漏报。**核心当下可用**。
  - **codex wf 第一次用 = 可信**: 核心 finding(impact slug 依赖、freshness 两假绿)被 Claude opus 独立印证; codex 还独有 SUPERSEDES 环检测双谓词 + 递归 DFS(非 opus 子集)。Claude opus 更深(真造反例复现 impact 空集 + 新旧 rc 对拍 + 实测 106/106 key 一致)。→ **「wf 用 codex」偏好成立**(质量够、关键 finding 不漏、省 Claude 额度), 见 [[subagent-model-by-weight]]。codex 审查 task wlf27p05z, Claude 对照 task wtrdxlf42。
- **待硬化清单 — 2026-06-16 已由 codex 硬化 wf (w33f4ucnp) 修复 A-I 全 9 项**(双 codex 实现+对抗验 + CC 抽查核实全绿: memgraph check OK·286 边/33 硬边 / 14 unittest 过 / ruff 0 / graph.json 已刷新; 根因真修=非 fact- 前缀 fact 现可被 impact 反查、see-also 假阳硬边已降软边; **仅剩 see-also 整行启发式边界 low, 真实数据未触发, 待补测试/文档**)。修了什么(留档):
  - **[贯穿根因] 硬边判定全靠正文措辞 + fact slug 含 'fact' 子串的巧合, 无显式声明**: `"fact" in stripped.lower()`(graph.py:313)对每条带 fact- 前缀的引用行恒真 → 当前零漏报纯属命名约定偶然; fact 改名/别名/跨行/纯 prose 引用即静默漏报; `相关:` see-also 行还被误升硬边(假阳)。**修向 = frontmatter 显式 `depends_on` / 启用 edges.jsonl**(正是 GPT 自己 MVP 设计写了却没实现那层)。
  - freshness 两假绿: 节点删除不 exit1(deleted 不计入返回值); 只改 description/index_summary 而 body 不变不报 dirty。+ 语义砍粗副作用(丢了 summary-lag 检测) + 测试不守这两条路径。
  - graph: SUPERSEDES/CONTRADICTS 环检测双谓词分裂; overlay 无法 downgrade 错误推断边(owner 没纠错出口); INVALID overlay 边处理; frontmatter 解析鲁棒性(inline-map/嵌套 type 误判); 递归 DFS 大图(>1000)崩; line_number 是 body 相对行号。
- **用它的 caveat**: 当前可用, 但**别给 fact 节点改名**(去 fact- 前缀会让引用降软边、impact 漏报), 引用 fact 要写成显式 wikilink(指向 fact 节点、和关键词同行)。
- **待硬化已修(codex 扛, 见上)**; 剩 see-also low 待办。**全部未提交**(含 memory_system 落地 + codex 这批硬化 + dispatch/dump 工具)。

## v3 (2026-06-16 晚, 下载夹四文件)
GPT 又出 v3: 回应 owner 问的『新会话怎么零学习上手』, 加 `memgraph bootstrap` 子命令 + `bootstrap.py` + `MEMORY_AGENT_GUIDE.md` + `agent_protocol.json`(新会话启动卡)。**但 graph.py/freshness.py 与 v2 字节完全相同 → 一个 soundness bug 都没修**(上面待硬化清单对 v3 核心一样有效)。v3 **高危**: overlay 打进了 `CLAUDE.md`(31KB 项目宪法)+ `START_HERE.md` 改写, GPT 称『移除旧 harness runbook 入口』 → **绝不盲目覆盖, 要先 diff 人工拍**。bootstrap 入口能力可增量收; 其余覆盖式快照同 v2 拒收。**v3 未落地**。

## v4 fleshout (2026-06-16, 又一覆盖式快照 + GPT 全认账)
GPT 第三次迭代「fleshout」(下载夹真实路径 `C:\22957\download`, 4 文件: report / validation / gpt回复 / 33.7MB 包)。**它干的**: 加 `memgraph.py bootstrap` 自助入口 + 操作协议节点 + 3 条 fact(self-bootstrapping / memory-change-needs-impact / hard-edge-soft-link-separation)+ 文档(OPERATING_MANUAL/SCHEMA/AGENT_GUIDE)+ 硬化 freshness/index 闸 + **锁死 harness 写入**。
**核实结论(亲眼读码 + codex 对抗审计 wf, 不信 GPT 自述)**:
- **又是覆盖式快照**: sha256 全树差分 → 整包落地会删本会话的 [[assumption-as-fact-then-backfill]] 教训节点、还原我清理过的 [[subagent-model-by-weight]] / 本节、冲掉并发会话的 zmd-round2。**只能 cherry-pick, 不能整包**(同 v2/v3)。
- **change-txn 写入硬门还是空壳**: cli.py/graph.py/memgraph.py/frontmatter.py 与仓库 **SHA256 完全一致**; propose-change 实测无来源 / 传假 event_id 都返回成功 status=proposal。bootstrap/agent_protocol 只是软约束文档。**治 assumption-as-fact 病的强制机制 = 还没建**(早就该做的真 #1)。
- **harness 投影被砍且无替代**: `sync_memory_to_harness.py --apply` 改成 `return 2` 停用; `deploy_harness_cache` 全库零实现; resolver 多候选判 ambiguous → 下游静默 skip 吞掉真实漂移; CLAUDE.md 删了那条「规则不投影进 harness 就召回不到」警示。
- **要点(差点踩坑, 已亲手复核)**: 当前**仓库↔harness = 0 漂移**(`sync --check` 实测 74 synced / 0 drift)。codex 报的「4 缺失/4 漂移」是 **v4 旧快照 vs harness**, 不是 current vs harness — 别误读成「harness 现在漂了」。当前 --apply 是好的、指对路径、无 resolver bug。
**问 GPT「为什么这么改」→ 四点全认账**(原话「安全性过度刹车」「落地顺序错了」「靠不了, v4 没给闭环」「未实现关键件, 不是已完成能力」)。给了修复路线(P0 复原 CLAUDE.md 警示 + resolver ambiguous→rc=2 + 临时 legacy deploy; P1 deploy_harness_cache CAS/managed-block; P1/P2 change-txn 状态机 add-event→propose-change→validate→apply)。
**推荐 + 待 owner 拍**: v4 不落地; harness 维持现状(那几条 P0 是修 v4 自己的回归 = 不落 v4 就 moot); 真正要做 = **建 change-txn 写入硬门**(按「wf 用 codex」: codex 实现 + 我对抗验), 这是全程 #1 也是本会话栽跟头的根治。**owner 尚未拍是否开干**。codex 审计 task woscgtxsp; 追问全文存 `C:\Users\22957\zmd_gpt_followup_v4_why.txt`。
**工具 caveat**: `dispatch_gpt_task.py --resume` 只「等+收」、无「向已有会话发追问」CLI; 要追问走 Claude-in-Chrome 插件(list_connected_browsers→AskUserQuestion→select_browser→在已开 tab 发)或 owner 手发(剪贴板 clip)。owner 本次选了自己手发。

## 背景: 前期「做偏了」(GPT 外审点破)
**fact-entry 依赖图**(改 fact 只反查依赖它的 entry 重写, 不全扫/不靠人 grep)是 **GPT Pro 外审(会话 6a303556)提出的重构方案**。⚠️ 之前(含本节早先表述)把它说成『owner 第 1 轮原始/真意图』是**没有 owner 原话依据的归因**(owner 2026-06-16 点破『这是 gpt pro 提出来的重构方案吗』)——是否真对应 owner 最初意图无原话佐证、不当确证(教训 [[assumption-as-fact-then-backfill]])。前期把任务做成 **「Markdown 记忆树治理系统」**(同步/MEMORY.md 24KB cap/索引/wikilink/repo↔harness 对账)= 错误的层。根因 = 没回到 owner 真意图就开干 ([[root-cause-over-symptom]] / [[fact-understand-before-output]])。GPT 正确架构(全文 `补丁包/gpt_deliveries/inspect_6a303556/conversation_full.md`): 五层 = 事件/实体/**事实(槽位+版本+状态+时效+来源+置信度)**/条目(视图)/**带类型依赖边**(DEPENDS_ON 硬线触发更新 vs RELATED_TO 软线只召回), 写入走 change-txn。本次落地的是它的 MVP。

## 已建的「Markdown 治理层」(前期产物, 仍在仓库, 未被新系统取代)
harvest-only 四层 + repo 侧 5 工具(memory_harvest / sync_knowledge / gen_memory_index / check_description_freshness / seed_index_summary)。新 memgraph 目前是**叠加的辅助层**, 没接管记忆维护流程(更新记忆仍走旧流程 + 手动三写)。完整讨论见 `cc_context/review/memtree_landing_review_20260615.md`。

## 本会话工具变更(未提交)
- `dispatch_gpt_task.py` 加 `--message-attach`(sources 通道额外把文件附到聊天消息)。
- `dump_conversation.py`(新): 后端 JSON 直读导出整条会话; `inspect_conv.py` 已坏。

相关: [[zmd-project-entry]] [[memory-currency-protocol]] [[root-cause-over-symptom]] [[fact-understand-before-output]] [[minimal-open-prompts]] [[subagent-model-by-weight]]
