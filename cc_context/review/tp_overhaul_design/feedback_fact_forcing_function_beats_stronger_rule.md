<!-- 落地文件名 = feedback_fact_forcing_function_beats_stronger_rule.md (前缀 feedback_ 必需:
sync_memory_to_harness.py 的 COPY_PREFIXES 白名单只认 feedback_/project_/reference_/user_,
fact_ 前缀不会投影到 harness 召回树; 用 feedback_ 还会被 sync 自动归入 harness 的
collaboration-rules-index 父节点正文 —— km-arbiter 查实)。frontmatter name 仍 kebab。 -->
---
name: fact-forcing-function-beats-stronger-rule
description: 抽象事实 — 用「记一条更强的规则」治反复复发的行为/状态漏更治不住;被动文本管不住没有强制函数、不挂产物完成定义的动作。根治=给它 forcing function(钩子/测试 gate/自动 stamp),漏做就自动报红;规则只是 fallback 文档。
metadata:
  node_type: memory
  type: feedback
  node_role: fact
---

<!-- fact 节点只声明 node_role: fact, 不维护 projections 清单 —— fact↔投影关系的
唯一真值源在投影侧的 derives_from (forcing function v2, km-skeptic 反讽门槛收敛)。
本 fact 的投影 = 在自己 frontmatter 写 derives_from: fact-forcing-function-beats-stronger-rule
的那些节点 (落地时: memory-currency-protocol + lazy-mode), 由 gate 机器反向派生, 不在此手列。 -->

**抽象事实(本次 normalize 从 [[memory-currency-protocol]] rule#7 提炼出的独立事实层)**: 用「记一条更强的规则」去治一个**反复复发**的行为 / 状态漏更, **治不住**。被动文本管不住一个**没有强制函数、不挂任何产物完成定义**的动作 —— 对比 commit / push / memory-sync / 链接 / 测试都有钩子或会大声报错, 唯独那个反复犯的动作没有。所以「记完又犯」不是知识缺口(我知道、甚至当场明说"回来再更"), 是这个动作根本**没上锁**。根治 = 给它 **forcing function**(钩子 / 测试 gate / 自动 stamp / CI 阻断), 漏做就**自动报红**; 规则只是 fallback 文档, 不是主防线。

**为什么是独立 fact, 不是 memory-currency-protocol 的一部分**: 这条原本埋在 [[memory-currency-protocol]] rule#7 末段(2026-06-02 owner 三连追问后定), 那里它的语境是"handoff 现状漏更"这一个具体投影。但同一个抽象事实的**适用范围远不止 handoff** —— 凡是"反复复发、记规则压不住"的行为 / 状态漏更都适用。把它提到独立事实层, 是为了让其它投影(不只 currency 那条)能共指同一个上游, 不必各自重述。

**适用范围(从 handoff 漏更扩展到所有反复漏更)**:
- **现状漏更**(原始投影): handoff / 记忆树现状值漂移 → 治本 = pre-commit `stamp_living_status.py` 自动 stamp 可推导字段。见 [[memory-currency-protocol]]。
- **权威数字漂移**: cuts 计数 / sizing 等散在多处手抄 → 治本 = core-node + projection + pytest forcing test(`test_authoritative_numbers_currency.py`: 断言 core == live recompute)。
- **知识层 fact↔投影漂移**(本次 tp-overhaul 新增, 即本 fact 自身的元应用): fact 没被回指(死事实) / 投影没接事实 / 引用关系断 → 治本 = 扩展 `check_memory_tree.py` 的 forcing function(已挂 preflight_gate + CI + pre-push)。
- **lazy / 卸责反复犯**: 句式黑名单(更强的禁词规则)压不住, 因为措辞会换马甲 → 治本两条腿 = ① **理解 why 内化**(规则改 surface, 理解改 generation, 见 [[lazy-mode]]); ② 出口门 hook 当低召回 fallback 提醒器。注意: 行为类比状态类难"上锁", forcing function 对它是**辅助**不是充分解, 真根治仍是内化。

**How to apply**: 发现自己/系统某件事**反复犯、记了规则还犯**时, 先别再写一条更强的规则。问: 这个动作有没有强制函数(漏做会不会自动报红)? 没有 → 那才是根因, 去给它上锁(钩子 / 测试 gate / 自动化), 而不是加第 N 条文本规则。能机械检测的就机械化; 纯行为类(措辞会变的)优先靠内化 why, forcing function 只作 fallback。

**边界(诚实)**: forcing function 治"状态/可机械检测"类漏更近乎根治; 治"行为/语义"类(如 lazy 措辞、投影正文是否忠于事实)只能做**结构性代理**(出口门低召回提醒、引用图闭合), 抓不到语义层, 那部分仍靠理解内化 + 人工/审查。别把"加了个 forcing function"当行为类问题的完结。

relate [[memory-currency-protocol]] [[lazy-mode]]。
