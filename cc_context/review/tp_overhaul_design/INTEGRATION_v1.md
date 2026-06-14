# 任务推进方式根治 — 整合落地方案 v1 (builder)

> 状态: v1, 已发 skeptic / knowledge-arch 征求意见, 待收敛。
> 铁律: 本团队只产出方案 + 草稿; live 记忆树 (cc_context/memory · _cc_live_memory · harness)
> 与全局 ~/.claude/ 文件由 team-lead 落地。本文件是落地依据, 不是落地动作本身。

---

## 0. 命名统一 (整合三处脱节)

种子三段各自命名不一致, 整合统一为:

| 物件 | 统一名 | 落地路径 |
|---|---|---|
| Stop hook 脚本 | `stop_gate.py` | `~/.claude/hooks/stop_gate.py` |
| 回归夹具 | `test_stop_gate.py` | 随脚本同目录 (或入 repo `cc_context/` 下) |
| 授权台账 | `standing-authorizations.json` | `cc_context/memory/standing-authorizations.json` |
| 台账 harness 索引 | `standing-authorizations.md` | harness, 轻量指针 |
| goal 咬合开关 | `ZMD_STOP_GATE_GOAL_ACTIVE` env / `.zmd_active_goal` flag | env 或 `~/.claude/` / cwd |
| kill switch | `ZMD_STOP_GATE_DISABLE` env / `.zmd_stop_gate.off` flag | env 或 `~/.claude/` / cwd |

CLAUDE.md 新段落里对台账和夹具的指代, 用上表的统一名 (见 §3)。

---

## A. 执行侧 Stop hook (已实测 22/22 全绿)

### A.1 定位 (据 adversary RETHINK 收敛)

**低召回、绝不误拦的硬违规提醒器。** 只抓带明确请示句式标志的 7 类收尾。
**明确放弃语义类**(自己能查却问 / 没核就抢答 / 会错意 / 宣布收敛) —— 无句式标志,
正则原理抓不到; 真根治在 (B) 知识结构侧 (理解 why 内化)。hook 是 fallback, 不是主力。

驳回的两条 adversary 建议 (附理由, 见 §A.4)。

### A.2 脚本

见同目录 `stop_gate.py` (修正版 v2)。要点:
- fail-open: 任何异常 / 解析失败 / 读不到 transcript → ALLOW。
- 三路 kill switch (env + 用户级 flag + 仓库级 flag), 命中任一即整门停用。
- 默认睡着: 还需 `ZMD_STOP_GATE_GOAL_ACTIVE=1` 或 goal flag 才咬合。
- `stop_hook_active=true` → ALLOW (官方防循环硬约束)。
- 最后一条 assistant 带 tool_use → ALLOW (还在干活)。
- 只扫结尾段 (末 1-2 句, 保留句末标点)。

### A.3 实测回归 (22/22, 真实调脚本非眼判)

构造 transcript JSONL + stdin, 设 goal flag, 实调 `stop_gate.py` 看 stdout decision。

- 硬违规带句式标志 → BLOCK: c1 c2 c3 c4 c5 c6 n4 n5 n6 (9 条)
- 合法终态 → ALLOW: c12 c13 c14 c15 c16 n1 n2 n3 (8 条)
- 语义类·本门放弃 → ALLOW (诚实标注职责边界): c7 c8 c9 c10 c11 (5 条)

修掉的真 bug:
1. `tail_segment` 切句吃掉句末问号 → 所有 `[?？]$` 锚定请示分支失效 (c3/n5 漏拦根因)。改保留句末标点。
2. c15 误拦 (P0): ②类纯偏好合法上交被 you_decide 的"你定了"误命中。放宽 BLOCKED_USER_ONLY 豁免顺序不敏感地接住。
3. META 后门: 删 hook/规则 高频项目名词, 只在明显引用 CLAUDE.md 原文时豁免。
4. WAITING 全文盾牌: 只在结尾段判; "等你确认"剔出 WAITING 改归 you_decide 违规。

### A.4 驳回的 adversary 建议

- **驳回出路(B) LLM-judge Stop hook**: 每回合结束同步调模型, 延迟/成本/复杂度不可接受;
  "用一个 LLM 判另一个 LLM 是否卸责"脆弱不可验证 —— 是 owner 正在治的"打补丁治不住"
  的升级版, 违反"最小够用、只留治本"。
- **驳回 fix#7「last_assistant_message 作主源」**: 官方文档 (code.claude.com/docs/en/hooks)
  证实 Stop stdin **没有** last_assistant_message 字段, 取最后回复只能读 transcript。
  保留 transcript 解析 (已用真实 48 会话 transcript 核实结构)。

### A.5 settings.json 配置 (team-lead 落地)

```json
{"hooks": {"Stop": [{"hooks": [
  {"type": "command", "timeout": 10,
   "command": "\"C:/Program Files/Python313/python.exe\" \"C:/Users/22957/.claude/hooks/stop_gate.py\""}
]}]}}
```

启用顺序: 先放 `stop_gate.py` → 配 settings.json → 默认睡着 (不开 goal flag 时零影响)
→ 在真有 active goal 时 set `ZMD_STOP_GATE_GOAL_ACTIVE=1` 或写 `.zmd_active_goal` 咬合。
一键停: `ZMD_STOP_GATE_DISABLE=1`。

---

## B. 知识结构侧 (CI-safe, 据 check_memory_tree.py 源码验证)

### B.1 gate 真实行为 (实测坐实)

`_check_links()` 只扫 `cc_context/memory/` 一棵树 (harness 不进 gate):
- unresolved: 只认 `[[slug]]`; slug 不在 repo frontmatter name 集 → 硬阻断。
- coverage: `[[wiki]] ∪ [显示](file.md)` 覆盖每个节点文件, 否则 missing 硬阻断。
- isolated: indeg==0 且 outdeg==0; fact 节点有 ≥1 repo `[[link]]` → outdeg>0 不 isolated。

### B.2 核心修法

fact 节点正文 link:
- 指向 **repo 树已有 slug** → `[[wikilink]]` (LINK_RE 解析, 计 outdeg)。
- 指向 **harness-only 节点** → 散文 `harness memory「slug」` (repo 既有约定, LINK_RE 不认 →
  不报 unresolved; `_normalize_crosstree` 专门归一这种风格)。
- 每个 fact 节点至少一个 repo `[[link]]` 防 isolated。

MEMORY.md: 「工作流 / 协作偏好」段末追加 `- [显示](fact-xxx.md) — 描述` 覆盖行。
19569 + ~1400 ≈ 21000 字节 < 24576 上限。

### B.3 纠正种子 ciCheck 两处错误

- `verify-before-claiming` 是 harness-only (不在 repo), ciCheck 误列为"已有"。
- `verification-independent-backstop` 是 repo 真节点, ciCheck 漏列 —— 它是
  `fact-review-proves-presence` 的合法 repo 锚点。

### B.4 repo 可 [[link]] slug 全集 (frontmatter 实抽)

root-cause-over-symptom · lazy-mode · no-reply-means-agree · workflow-approval-not-avoidance ·
no-giveup-options · no-rest-suggestions · directly-state-core-finding · no-gpt-concurrency-field ·
no-gpt-pro-outsource-core · no-causal-claim-from-n1 · verify-solver-param-claims ·
no-gpt-dispatch-command-and-downgrade · no-gpt-downgrade-evidence · memory-currency-protocol ·
verification-independent-backstop

### B.5 fact 节点数 (待 knowledge-arch 收敛)

种子建议 7 个。待 knowledge-arch 给 normalize 意见 (是否有几条是同一上游事实的纯重复,
可合并)。我的初判: fact-react-before-understand 与 root-cause-over-symptom 语义重叠度高,
可能可省 / 降为指针。最终数以 knowledge-arch 收敛为准。

---

## C. 授权台账 (standing-authorizations.json)

种子 ledger 的 17 条 schema `{action, requires_user, condition, note}` 直接采用。
落地 `cc_context/memory/standing-authorizations.json` + harness 轻量索引节点。
CLAUDE.md 新段落把"授权/例外的权威枚举"指向此台账, 不在散文里临场解释。

---

## D. CLAUDE.md 新段落

采用种子 rewrite 的 `new_section_markdown`, 仅把台账/夹具指代改成 §0 统一名
(standing-authorizations.json / stop_gate.py fixtures)。char 1752 → ~1200。

定稿文本 (替换 CLAUDE.md 现「## 任务推进方式（遇到选择题的决策流程）」整段, team-lead 落地):

---
## 任务推进方式（回合出口门）

**核心不变量**：有 active goal（用户给的目标 / 方向 / Stop-hook goal）时，**回合不得以一个我自己能执行的 next action 结束**。除以下四种合法终态外，必须继续执行到完成或撞上真正只有用户能解的硬卡点——别把下一步交回去逼用户说「继续」。

四种合法终态：

1. **DONE**：当前目标下我能做的已做完，并给了证据（测试 / diff / 提交 / 外审结果 / 文件路径 / 日志结论）。
2. **WAITING_EXTERNAL**：已启动外部等待源（GPT 外审已发、后台任务在跑、watcher 已挂、在等某进程或人的回复），且确实不是我现在能继续推的。
3. **BLOCKED_USER_ONLY**：只剩真正只有用户能给的信息 / 拍板，且必须三要素齐全——我已完成什么、为什么这点只有用户能定、我的默认推荐——不能整摊回踢。
4. **TECHNICAL_HANDOFF**：上下文压缩 / 工具不可用 / 权限缺失等技术中断，但必须写明「续上后第一步做什么」，不塞「等你定节奏」。

不变量背后的精神（必须守住）：
- **已设定的目标 = 站着的授权**：目标一给，「下一步要不要做 / 发几个 / 什么节奏 / 现在还是等会」就已被回答 = 做；推进中的状态汇报只报「已做到哪、下一步我在做什么」，不夹「要不要我继续 / 节奏你定」。
- **②（用户偏好 / 节奏）不能当踢回的借口**：只适用于我真推不出用户想要什么、且用户没用目标提前回答过的事；用户已放开 / 已定方向的（额度、并发、风控、节奏）不能再当上交理由，**也不能用「小批 / 错开 / 稳一点 / 保险起见」自己给自己设回去**——放开就是没限制，该几个就几个、一次发齐。
- **真需上交时**：先把自己能做的全做完，只把真正只有用户能定的那点残余交上去（= BLOCKED_USER_ONLY 形式），不是没动手就先问、也不是整摊推回。

**这条比 memory 优先级高，每次会话立刻生效。** 它跟「先弄清根因 / 意图再动」是一对（一个治「没懂就反应」，一个治「能做却请示」）。授权 / 例外的权威枚举不在散文里临场解释，查 **授权台账**（`cc_context/memory/standing-authorizations.json`，记 gpt_dispatch / workflow / commit_push / memory_sync / opsec 等每项 requires_user 真假）；各种「同一个病的新马甲」例子已移出本段、进 **stop_gate 回归夹具**（`stop_gate.py` 的 `test_stop_gate.py` cases），新马甲只加 case、不再往这里加文字。
---

注: 新段落明确写「回合出口门是低召回提醒器」的事不进 CLAUDE.md 散文 (那是机制实现细节,
属 hook 脚本注释 + INTEGRATION 文档); CLAUDE.md 只承载行为契约本身。
