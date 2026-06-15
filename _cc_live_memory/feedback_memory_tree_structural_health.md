---
name: memory-tree-structural-health
index_summary: "wikilink 命名统一才解析 + MEMORY.md ~24576B 超了尾部静默截断 + harness 重写 frontmatter 保 name."
description: "记忆树**结构**健康轴(区别于 [[memory-currency-protocol]] 内容现状轴),六条:① wikilink 命名口径统一否则断链;② MEMORY.md ~24576B 自动加载上限、超了尾部静默截断;③ harness 重写 frontmatter 但保 name 字段→rename 耐久;④ 第三轴 同话题散多条没跨链=改不全+召不全(治法 grep 全树一起改 + 互相 wikilink + 共同话题词);⑤ 第四轴 泛化不足(规则锁死首次语境)→记前问'只适用眼前还是更通用';⑥ 实例/transclusion 模型(可推导值升 INSTANCE 槽、stamp 引擎自动 transclude)单一真相源根治 drift。细节见正文。"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

> 事实依据: [[fact-forcing-function-required]]

记忆树会"结构性"坏掉 —— 这是跟 [[memory-currency-protocol]] (内容过时轴) **不同的失效轴**, 内容再新, link 断了 / 尾部被截一样废。2026-06-01 梳理时治的就是这层。

## 两个硬机制

1. **wikilink (双方括号包 `name` slug) 命名必须统一一套口径才能解析**。曾三套并存 (剥前缀 / 留 `feedback-` 前缀 / 中文名) → 断链 192、孤点 63。归一为**剥前缀**后 434/434 resolved、孤点 0。维护时新加 link 一律用剥前缀的 `name:` slug。

2. **MEMORY.md 在 ~24KB 附近尾部条目开始不进上下文** (经验阈值 ≈ 24576B=24×1024, **未见 harness 文档, 来自实测推断, 别当文档化硬上限**)。观察: 33396B 时尾部约 33 条 (#85–#117, 含打包规范) 不在 context。**"打包规范召不回"的最佳推断主因是尾部截断** —— 但当时**同期**还有断链 192/孤点 63, 而修复是 slim+重排+重连**一起做的**, 没做对照隔离, 所以"截断是主因"是强推断**不是证实结论** (同 [[no-causal-claim-from-n1]] 那类 N=1 因果, 别说死)。无论真因是哪种, 下面的操作规则都成立。
   - **瘦身**: 超长索引条砍到 <120 字符; 分 6 段重排, **当前状态/打包规范放最前 (永不截), paradigm 死路史放最后 (要截只截低价值历史)**。
   - **headroom 红线**: slim 到 ~23366B 后, 每加一条索引就涨回上限 (24070B 时只剩 ~506B)。**加索引前必先 slim 一条旧的**, 否则尾部重新被截。

## harness 交互 + 维护工具

- **CC harness 写 memory 时会重写 frontmatter** (加 `originSessionId`, 偶尔搞坏某文件需手修), 但**归一后的 `name:` 字段被保留 → rename 耐久**, 不会被 harness 冲掉。
- 维护脚本在 `cc_context/tools/` (相对路径, 别用绝对): `normalize_memory_links.py` (命名归一)、`report_link_graph.py` (健康报告: 文件数/link 数/resolved/孤点)、`deorphan_links.py` (**批量补链**: 喂 `(from,to,reason)` 边表, fail-closed=校验目标 slug 存在 + 去重已连的 + 只读校验后才写; 连通审计出缺链清单后用它批量补 [比手工逐处 edit 稳], 但**逐条先 vet why 非盲信** per [[verification-independent-backstop]] 规则#3)、`extract_session_turns.py` (抽对话当 backstop 主体)、`stamp_living_status.py` (实例/分身 transclude 引擎, pre-commit 调)。
- **2026-06-14 机器检查加固**: `scripts/check_memory_tree.py` (preflight 已调, push 门禁) 现额外跑两条 **warn-only** 检查 —— ① **harness↔cc_context 共维护文件 drift** (规范化跨树 wikilink 后比内容; 补 2026-06-14 禁用 pre-commit 自动镜像后的缺口, 防两树再分叉); ② **活树裸引用已归档节点未标 (已归档)** (link checker 只抓 `[[]]`, 抓不到 prose `见 X` 形式; 扫全部 archive slug, 根治归档时手列不全 —— 首跑即抓出 20 处遗漏)。两条都 warn 不 block, 不适用环境 (CI/换机) 自动 skip; 测试 `src/tests/test_memory_tree_guards.py`。归档节点时仍要 grep 全树清裸引用, 这条 lint 兜底响亮提示。

## 第三个失效轴: 同话题散在多条 memory 没跨链 (2026-06-02 用户 catch)

同一情况/规则常散在**多条** memory。它们若没好好互相 wikilink, 两个失效, 都已实证复发:
- **改不全 (write 时)**: 改正一条、漏掉同话题其它条 = 假修。实例: "≤29MB 是下载安全线"这个未验证幻觉散在 SendUserFile 段 + pitfalls description + handoff 三处, 我第一次"修"只改了一处 (用户 catch)。
- **召不全 (read 时)**: 召回一条、没拉进同簇其它条 → 该用的规则没 surface。实例: "修完再审直到 clean" 记在 gemini-review-algorithm-math(已归档) §循环规则 (Gemini 语境), 但没连 [[verification-independent-backstop]]/audit-verify-before-archive(已归档); 我跑 GPT-review workflow loop 时没想起它 → 同问题复发 (用户 2026-06-02 第二次 catch)。

**协议 (两手都要 —— 别只靠被动 recall: recall 按 description 匹配注入、不自动顺着 wikilink 走)**:
1. **改/记一条 memory 前, 先 grep 该话题关键词跨全树**找所有实例 (不只手头那条), 全部一起改/对齐 —— 这是 [[verification-independent-backstop]] 的"完整性"用到 memory 编辑本身 ("修就修全, 别只改手头一处")。
2. **同话题簇必互相 wikilink** (双方括号包对方 slug) 双向互指, 让改一条能顺链到同簇、召一条能拉同簇。
3. **clustered memory 的 description 带共同话题词**, 让同簇在 recall 时倾向 co-surface (description 是 recall 匹配面)。
4. 周期性 (大 review / phase boundary) 跑**簇连通审计** (可派 workflow, 主体=记忆树): 找"同话题但互不 link"的 memory 对, 补链。这跟 `report_link_graph.py` 查的"断链/孤点"是不同轴 —— 那查 link 解不解析, 这查**该有的 link 缺没缺**。

## 第四个失效轴: 记忆时泛化不足, 把通用规则锁死在首次触发的具体语境 (2026-06-02 用户 catch, 第三轴的上游)

记一条 lesson 时, 它若**本质通用** (适用多个触发语境), 却被记成 / 框成只属于**首次触发的那个具体语境/标题**, 它就在别的语境**不 surface** = silo。**这是第三轴 (连接性) 的上游**: 一开始就记对抽象层 → 根本不形成 silo, 不用事后补链。

实例 (用户原话点名): **"review 修完要再审直到 clean" 本是通用 review/verify 规则**, 但 2026-05-24 被我记成了 gemini-review-algorithm-math(已归档) 的「循环规则」—— **锁在 "Gemini 审查" 这个语境框里**。跑 GPT-pro-review workflow loop 时它没 surface → 同问题复发 (用户两次 catch)。根因不只"没跨链", 更上游是**记的当下没想到它通用, 按触发语境 (Gemini) 归了档**, 即"泛化不够 / 没对当时具体情况想透它的适用边界"。

**协议**: 记 lesson 前停一秒问 —— **"这条只适用眼前这个具体场景, 还是其实更通用?"** 判别法: 把规则里的具体名词 (Gemini / GPT / 这个文件 / 这个 family) 换成占位符, 规则还成立吗? 成立 = 该泛化。通用的就**记成通用规则 (放通用 memory / 起通用标题), 把当前事件当 example 挂规则下**, 别让标题/归档语境把规则窄化。触发实例要留 (它是证据), 但不能当成规则的边界。(这跟 [[no-causal-claim-from-n1]] 是镜像的两种 over/under-fit: 那条是从 N=1 过度泛化出因果, 这条是该泛化时泛化不足。)

## 实例/分身模型 (单一真相源 + transclusion — 2026-06-02 用户提出, 三个失效轴的结构性根治)

前四轴是**逐个症状**, 这是**统一架构**: 三个失效轴 (现状值漂移 / 同话题 silo / 泛化不足) 本质是**同一个病** —— 树里存的是 **copy** 而非 single-sourced 引用。根治 = 把树做成「**实例 + 分身**」:
- **实例 (instance)** = 某事实/概念的唯一权威值, context-independent (一处真值)。
- **分身 (projection)** = 任意节点对实例的**引用**, 不 copy 值。
- 更新走实例 → 所有分身自动同步; 树里**放不下重复值** → 不漂移、不 silo。

**两类, 机制不同 (别搞混)**:
1. **可推导值** (sha / git HEAD / phase / repo url / 计数...): 用 **transclusion 引擎** —— `cc_context/tools/stamp_living_status.py` 的 `INSTANCES` 注册表 (id→resolver) + 节点里 `<!-- INSTANCE:<id> -->…<!-- /INSTANCE:<id> -->` 槽 (示例用 `<id>` 占位免被引擎当真槽匹配; 真槽 id 用注册表里的真名如 latest_review_package); pre-commit 每 commit 扫全树填槽, 结构上不可能 drift。**加实例**=往 INSTANCES 加 resolver; **加分身**=节点插槽。见 [[github-backup]]。这是把"现状漂移"那类**上锁**的强制函数 (规则治不住没上锁的动作)。
2. **规则/判断** (如"修完再审 clean"、"下一步 P1.3A"): **不 transclude 逐字副本** (满树重复=clutter)。靠 **wikilink 链接** (双方括号包对方 slug 本就是"概念"的分身指针, 指权威节点不重述) + 第三轴连通纪律 + 第四轴泛化纪律。漂移恰发生在**抄了值/重述了规则**而非"指"的地方。

**判别**: 一个事实**既出现在 ≥2 节点、又随时间变** (drift-prone) → 升成实例。只一处的、永不变的 → 留着别过度范式化。**诚实边界**: transclusion 只填**标记过的槽**, 改不了自由散文里隐式提到实例的地方 (那残留靠 currency-protocol rule#7 的 warn 兜)。

**How to apply**: 周期性 (phase boundary / 大 review 前) 跑 `report_link_graph.py` 查连通 + 看 MEMORY.md 字节数 + 按第三轴协议查同话题簇缺链。加索引条前先 slim。改/记 memory 前 grep 全树找同话题所有实例一起改。**记新 lesson 时先判它通不通用 (占位符测试), 通用就记到通用层别锁触发语境**。**重复的可推导值 → 升实例 + 分身槽 (别手抄); 重复的规则 → wikilink 别重述**。关联 [[memory-currency-protocol]] (内容轴, 互补) [[verification-independent-backstop]] (完整性 → 改全 + 记对抽象层) [[no-causal-claim-from-n1]] (over-fit 镜像) gemini-review-algorithm-math(已归档) (under-fit 实例) [[github-backup]] [[memory-edit-confirmation]]。
