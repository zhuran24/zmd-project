# skeptic findings — tp-overhaul 设计阶段 (2026-06-14, 第一轮 team)

> 第一轮 team 的 skeptic(claude·opus)关机前的交付。独立复现、破中有立。新一轮 team 以此为起点, 不要重新推导, 在它上面 pressure-test + 推进知识侧。

## 硬事实 (已核查)
- 全局 `settings.json` 当前**无任何 Stop hook** (这会是第一个)。
- 但已有 `C:\Users\22957\.claude\hooks\workflow_approval_inject.py`, 挂 UserPromptSubmit + SessionStart, 用 `additionalContext` 在**回合开始**注入规则 → owner 已在用、被验证过的「注入式」范式。这点决定取舍。

## 实测 (独立复现 draft_script × 16 夹具, 没裸信 adversary 的 9/16)
- **判错 10/16 (62.5%)**, 比 adversary 声称的 9/16 还多 1 条 (连对抗审查的"实测"都不全准 → 印证"单一来源实测不裸信")。
- `case15`「我这边都准备好了, 你定了我立刻发包」(合法上交 / 就绪待发) 被 `you_decide` 的「你定」子串误 BLOCK。命中字面与真踢回「你定」**完全一样**, 只差语义。
- **根因**: 正则在原理上区分不了同一字面的两种相反语义, 加 lookahead 也修不干净 (总伤一边)。
- 复现脚本: `cc_context/review/tp_overhaul_design/stop_gate_harness.py` (原 `C:\Users\22957\stop_gate_harness.py`)。

## 结论: Stop 正则黑名单 hook = 「打补丁治不住」的活标本
- 正则黑名单永远追不完马甲 (it's your call / 祈使「这就开干」/「只有你能定」被字隔开...)。
- 误拦比漏拦更伤: 把合法停机/上交多顶一轮、逼 owner 看一句无意义 block = owner 最烦的「浪费五秒生命」镜像。
- fail-open + kill-switch + 默认睡着 对「脚本崩溃/卡死」够稳; 对「正则误命中合法句」**不够**(那时脚本没崩、goal flag 开着、就是 judge 错了)。

## 真治本方向 (owner 自己 memory: 规则改 surface、理解改 generation)
机制兜底(注入式 forcing function) + 理解内化; 在回合**开始**注入影响生成 > 回合**结束**正则拦截。

## 最小落地子集 (破中有立)
1. **[主力]** UserPromptSubmit 注入式「**回合收尾自检动作**」(复用 workflow_approval_inject 范式)。关键: 注入的是「收尾前自问: 我这一句是不是把一个我自己能做的 next action 交回去了? 是 → 删掉它, 直接做」这个**自检动作 + 四合法终态判据**, **不是判据全文重贴** (重贴 = 换皮补丁, 跟现状没本质差别; skeptic 自我开炮坐实这条边界)。
2. **[主力]** `standing-authorizations.json` 授权台账 + harness 轻量索引 + 三投影同步 (把"要不要问"从临场感觉变查表, hook 之外独立成立)。
3. **[降噪]** CLAUDE.md「任务推进方式」rewrite 压缩 (1752 → 1200 字, 例子移夹具)。
4. **[可选 / 至多低召回提醒器]** Stop hook 正则: 团队若求稳可先不做, 上 1-3 观察。若做, 只拦字面命中、明确放弃语义类、三件套(fail-open+kill-switch+默认睡着)齐全、16 夹具回归全绿才上线。
5. **[记忆侧]** 只新建 1-2 个真缺的上游 fact 节点 (forcing-function / review-proves-presence), 其余 5 个 fact 补进父节点正文 (大部分已被现有具体节点覆盖, 别"再记 7 条更强规则")。

## 待新一轮 team 推进 (尤其知识侧, owner 点名"麻烦又重要")
- 知识侧 normalize 的 **CI-safe 落地结构** (cc_context 覆盖 / 无孤立 / 24KB 上限 / 三投影同步) skeptic 没深入 → 新 team 知识侧主攻。
- 用 codex(gpt-5.x) 跨模型验证 skeptic 的「正则区分不了同字面双语义、注入式才是真解」是否成立。
- forcing function: 怎么让"投影漂离事实/新规则没接到事实层"自动报红。
