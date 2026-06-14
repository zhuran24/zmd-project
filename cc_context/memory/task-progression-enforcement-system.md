---
name: task-progression-enforcement-system
description: 「任务推进方式」根治系统(2026-06-15 落地, commit 35548cc): 注入式 hook + 授权台账 + fact 层 + forcing gate 取代靠自觉的文字规则; 要维护这套看这里。
metadata:
  node_type: memory
  type: reference
---

> 事实依据: [[fact-decision-boundary-is-ability]] [[fact-forcing-function-required]]

「任务推进方式」(能做却请示 / 「我现在去做 X」然后停)反复违反的**根治系统**, 2026-06-15 全量落地 (8 人 team + GPT 跨模型设计, commit 35548cc)。它把「再写一条更强的文字规则」换成**机制**, 维护时认这张图:

- **执行侧主力 = 注入式 hook** `~/.claude/hooks/turn_exit_self_check_inject.py` (挂全局 settings.json 的 SessionStart=完整版 / UserPromptSubmit=精简版): 回合**开始**注入「收尾自检动作 + 四合法终态 DONE/WAITING_EXTERNAL/BLOCKED_USER_ONLY/TECHNICAL_HANDOFF」, 改 generation。**回合末正则 Stop hook 被否决** —— 实测正则分不了同一字面的两种相反语义、会误拦合法句 = 负资产 (对抗样本 stop_gate_adversarial.py 留档)。
- **授权台账** `cc_context/knowledge/standing-authorizations.json` (17 条机器可读 requires_user): 「要不要问 owner」**查表**、不靠临场感觉。新增可授权/需确认动作往这加条目, 别散进散文。
- **fact 层** (记忆树 normalize): 7 个 `fact_*.md` 抽象事实 + 投影节点加一行「事实依据」wikilink 回指 (见 MEMORY.md「抽象事实层」块)。
- **forcing gate**: `scripts/check_memory_tree.py` 的 `_check_fact_projection_contract` (死事实/孤立投影/新投影没接 fact → 自动报红; opt-in + fail-soft); harness 投影同步是 **warning 不阻断** pre-push (Finding 2)。
- **行为契约本身** = 全局 CLAUDE.md「任务推进方式（回合出口门）」段 (核心不变量 + 四终态 + 查台账指针)。
- **设计全程留档** (各侧定稿 + 对抗样本 + GPT patch + 复验): `cc_context/review/tp_overhaul_design/`。

第二轮 (技术债, 非阻断, 未做): exemption baseline 按簇消灭 + 投影正文删重复抽象 + harness `abstract-facts-index` 误标 type:fact 的潜在隐患。
