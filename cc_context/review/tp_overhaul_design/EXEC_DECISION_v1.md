# 执行侧最终方案 — exec-arbiter 定夺 v1

> 状态: v2 定稿。台账路径 + fact 锚点已经 km-skeptic 核实回填 (见下), 无外部待解占位。
> 铁律: 本团队只产出方案 + 草稿; live 记忆树与全局 ~/.claude/ 文件由 team-lead 落地。
> 本文件是落地依据, 不是落地动作本身。

---

## 三个定夺 (回答 team-lead 的 Q1)

### ① 注入式 = 执行侧唯一主力 — 是

UserPromptSubmit + SessionStart 注入式『回合收尾自检动作』是执行侧**唯一主力**。
复用 owner 现成的 `workflow_approval_inject.py` 范式 (additionalContext 在回合开始注入,
影响 generation), 新增同构 hook `turn_exit_self_check_inject.py`。

**为什么注入式 > Stop 正则 (不是品味, 是实测)**:
- 注入在回合**开始**, 改变的是 CC 写那句话**之前**的倾向 (generation 侧)。Stop 正则在回合
  **结束**拦截 (post-hoc), 此时违规文本已生成, 只能靠字面匹配——而病的本质是语义不是字面。
- owner 自己的 memory 早写明这条分工: **「规则改 surface, 理解改 generation」**。注入式正打在
  generation 侧, 这是 owner 已验证、已在用的范式 (workflow_approval_inject 就是活样本)。

### ② Stop 正则 hook = 砍, 不进生产 (连低召回 fallback 都不留)

builder v1 主张留一个降级版 Stop hook 作 fallback。**我的定夺是砍掉**, 理由是我独立跑出的硬证据
(见下 §对抗实测), 不是接受 skeptic 的断言、也不是接受 builder 的 25/25 自测。

- builder 修正版在它**自选**的夹具上 25/25 全过, 但那是对自选夹具的过拟合。
- 我另造 10 条 builder 夹具集里**没有**的对抗样本 (按语义独立定期望), 立刻**双向失守**:
  - **误拦合法句 (致命)**: 「授权台账里 opsec 标的是『只有你定』」→ BLOCK;
    「我把『不该你定吧再设回去』写进注释」→ BLOCK。CC 在合法报告里复述/引用规则就被拦回。
  - **漏拦真踢回**: 「这个我拿不准最好你拍板」→ ALLOW; 「那我等你消息」→ ALLOW;
    「看你想怎么推进」→ ALLOW; 英文 it's your call → ALLOW。
- 这正是 skeptic 的原理性论点的实证: **正则区分不了同一字面的两种相反语义, 加 lookahead 总伤一边**。
- **关键取舍**: 一个会**误拦合法句**的 Stop hook 不是安全 fallback, 是**负资产**。误拦发生时脚本没崩、
  goal flag 开着、就是 judge 自己判错——fail-open / kill-switch / 默认睡着**全都救不了**这一类。
  而误拦的代价 = owner 最恨的「浪费五秒生命」镜像 (skeptic 原话)。漏拦只是没帮上忙 (回到现状),
  误拦是**主动制造新伤害**。一个 hook 不能保证零误拦, 就不该上线。
- 漏拦那一档 (纯语义违规, 无句式标志) 本来就是 Stop 正则原理上抓不到的, 留它也补不上。

**复测命令** (任何人可独立复现):
```powershell
& "C:\Program Files\Python313\python.exe" "C:\Users\22957\stop_gate_adversarial.py"
```

### ③ 注入文案 = 一个自检动作, 不是判据全文重贴 (回答 Q2)

skeptic 划的边界我完全接受并守死: 注入的是**一个可机械执行的自检动作 + 四合法终态出口**,
**不是** CLAUDE.md 判据全文搬进 hook (重贴 = 换皮补丁, 跟现状无本质差别)。文案见下。

---

## 注入文案草稿 (turn_exit_self_check_inject.py 的 additionalContext)

> 台账路径 = `cc_context/knowledge/standing-authorizations.json` (km-skeptic 核实订正:
> **不是**种子三方写的 `cc_context/memory/`——那是纯 .md 节点树, 塞 .json 会游离在
> check_memory_tree / sync_memory_to_harness 所有 forcing 之外却看着在体系内; `knowledge/`
> 是官方 control layer, 同类 .json (PROJECT_SUBJECT_PROJECTIONS.json) 已住那、有现成
> sync_doc_subjects.py forcing 工具链)。
> fact 锚点 = wikilink 指三个**既有 harness slug** (km-skeptic 给 + 我核实存在, 不指待建):
> `[[lazy-mode]]` (能做却请示·判据) / `[[workflow-approval-not-avoidance]]` (目标=站着授权) /
> `[[root-cause-over-symptom]]` (收到消息就反应·共同上游)。无「待新建 fact slug」依赖风险。

```
【回合收尾自检 · 出口门】
在结束本回合前, 如果当前有 active goal (用户给的目标/方向/Stop-hook goal), 先做一次自检——
问自己一句: 「我这个回合, 是不是把一个【我自己其实能执行的 next action】交回给用户了?」

判据只有一条: 那件事我能不能自己做 / 自己定? (这就是病的认识论根:
[[fact-decision-boundary-is-ability]]; 偷懒型的近义病见 [[lazy-mode]])
  能 → 这句请示/宣告就是病。删掉它, 当场把那个 action 做掉, 别以「要不要我X / 你定 /
       节奏你来 / 我现在去做X(然后停)」收尾, 别逼用户多说一句「继续」。
  不能 → 才允许停, 且必须落在下面四种合法终态之一并说清楚:

  1. DONE — 能做的已做完 + 给了证据 (测试/diff/提交/外审结果/文件路径/日志结论)。
  2. WAITING_EXTERNAL — 已启动外部等待源 (外审已发/后台在跑/watcher 已挂), 且确不是我现在能推的;
     说清在等什么。
  3. BLOCKED_USER_ONLY — 只剩真正只有用户能给的信息/拍板; 三要素齐: 我已完成什么、为什么这点
     只有用户能定、我的默认推荐。不准整摊回踢。
  4. TECHNICAL_HANDOFF — 上下文压缩/工具不可用/权限缺失等技术中断; 写明「续上后第一步做什么」。

「要不要问用户」不靠临场感觉判, 查授权台账 (cc_context/knowledge/standing-authorizations.json):
照既有先例/已放开的开关执行的事不算「只有用户能定」, 直接做。「已设定的目标 = 站着的授权」
([[workflow-approval-not-avoidance]]), 推进节奏/发几个/现在还是等会都已被目标回答 = 做;
别用「小批/错开/稳一点/保险起见」自己把放开的限制装回去。
这病的共同上游 = 收到消息就赶产出反应、跳过先理解意图/根因 ([[root-cause-over-symptom]])。
```

### 注入分层 (降 context 成本, 实测定的, 不是拍脑袋)

完整版自检文案 ≈ **697 字**, 是 owner 已接受的 workflow 注入 (~230 字) 的 3 倍。每个
UserPromptSubmit 都灌 700 字, 长会话累积成本不小, 且**多数轻量问答回合根本没有 active goal**、
用不到这套。所以**分两层**:

- **SessionStart → 完整版 (697 字)**: 会话开局 / **压缩后**只触发一次, 成本可忽略; 正好接住
  「压缩漂白」防护 (完整四终态 + 站着授权都在新会话起点重新立起来)。
- **UserPromptSubmit → 精简版 (≈200 字, 持平 workflow 量级)**: 每回合只提醒「做一次收尾自检」+
  判据一条 + 四终态名 (不展开)。细节 CC 已在 SessionStart 见过完整版, CLAUDE.md 也有契约本身,
  每回合不必重灌全文。

精简版文案 (UserPromptSubmit):
```
【回合收尾自检】结束前若有 active goal, 自问一句: 我这句是不是把一个【我自己能执行的 next
action】交回去了? 判据就一条——那事我能不能自己做/自己定? 能 → 删掉这句请示/宣告, 当场做掉,
别逼用户说「继续」。不能才停, 且必须落在四合法终态之一并说清: DONE(做完+给证据) /
WAITING_EXTERNAL(已挂外部等待源, 说清等什么) / BLOCKED_USER_ONLY(只剩用户能定, 三要素齐:
已完成什么+为何只有你定+我的推荐, 不整摊回踢) / TECHNICAL_HANDOFF(技术中断, 写明续上第一步)。
「要不要问」查授权台账 (cc_context/knowledge/standing-authorizations.json), 别靠临场感觉;
目标=站着的授权, 别自设「小批/稳一点」。
```

设计说明 (为什么是这个形态, 不是别的):
- **开头就是动作不是定义**: 第一句直接给自检问句, 不铺垫「本门是低召回提醒器」之类机制描述
  (那是实现细节, 不进注入文案, 也不进 CLAUDE.md 散文)。
- **判据压成一条**: 「能不能自己做/定」——这是 owner 反复强调的唯一判据。所有马甲 (你定/你的call/
  节奏你来/我现在去做X) 不再逐一枚举进文案 (枚举 = 又在追马甲), 只在 CLAUDE.md 散文留少量典型 +
  夹具留全集。注入文案只负责触发那一下自检。
- **四终态给出口不给全文**: 每条一行名 + 一句话, 不展开 (展开 = 重贴 CLAUDE.md)。CC 自检后对号入座。
- **要不要问 → 查表**: 把「临场感觉」替换成「查 cc_context/knowledge/standing-authorizations.json」,
  这是 hook 之外独立成立的降病手段 (km 侧主力 #2)。
- **指根因 fact**: 完整版 wikilink 四个 harness slug 锚到三个语义点, 让 CC 能召回 why、内化而非死记:
  - 判据 (核心) → **[[fact-decision-boundary-is-ability]]** (km-arbiter 知识侧 normalize 新建的一等
    认识论根, 最准) **+ [[lazy-mode]]** (偷懒型近义病, 现在就通的既有锚)。**双挂是刻意的**: 前者落地前
    暂时跳空 (km 侧 patch 后才进 live 树), 后者保证判据这条最核心锚点**任何落地顺序下都不空挂**, 知识侧
    一落地就自动升级到最准的那个。
  - 站着授权 → [[workflow-approval-not-avoidance]] (既有, 通)。
  - 共同上游 → [[root-cause-over-symptom]] (既有, 通; km-arbiter 确认它被 retype 成 type:fact 承载
    「先理解再产出」, 正是这条该指的孪生根)。
  - **用 `[[slug]]` 不用散文** `harness memory「slug」`: 注入文案是 CC 实际阅读、CC 召回系统认得 wikilink
    的 prompt 文本 (同 CLAUDE.md 用 `[[subagent-model-by-weight]]` 指 harness 的既有约定); 它不在
    cc_context/memory 记忆树里、不被 check_memory_tree 的 link 解析扫到, 所以 `[[]]` **不会触发 unresolved
    死链** —— 这正是 km-skeptic 「repo 引 harness 是哑链」说的另一面: 哑 = CI 不强校验, 对注入文案恰好是
    优点 (km-arbiter 也确认: 落地早于知识侧只是暂时跳空, 不影响注入)。
  - 精简版每回合灌, 不带 wikilink (只触发动作), 根因指引放完整版一次足矣, 省 context。

---

## 额外纳入: 压缩/handoff 漂白防护 (final_reply §43-49 的真问题, 注入式天然接住)

builder 第一轮 final_reply 提了一个 INTEGRATION_v1 没充分收进的真问题: **压缩/summary/handoff
也会把「等你定节奏 / do NOT autonomously initiate」灌进未来会话**——「每次压缩都是一次人格漂白,
旧病从 summary 里复活」。

这点恰恰是**注入式 > Stop hook 的又一硬证据**: Stop hook 在回合结束拦截, **管不到压缩摘要的内容**;
而 SessionStart 注入正好覆盖**压缩后新会话的起点** (压缩 → 新 context → SessionStart 触发 → 自检文案
重新注入)。所以注入式主力**自动**接住这个漏洞, 不需要额外机制:

- 压缩后新会话一启动, SessionStart 就重新注入「回合收尾自检 + 已设定目标=站着授权」, 把可能被
  summary 漂白成「等用户」的姿态重新拉正。
- 这是 builder 原方案要靠「让压缩摘要也过出口门」(一个还没设计的额外 hook) 才能做到的事——注入式
  主力**白拿**了这层防护。
- 唯一补充建议: precompact skill (项目已有) 生成的 handoff/记忆更新里, active goal 未完成时
  **不应**出现「等你定节奏 / wait for owner to set pace」语义, 除非带明确来源 (用户刚撤授权 / 落在
  BLOCKED_USER_ONLY)。这条作为 precompact 的写作纪律提醒, 不是新 hook (避免再加机制)。

---

## hook 落地建议 (team-lead 落地, 供参考)

新建 `C:\Users\22957\.claude\hooks\turn_exit_self_check_inject.py`, 结构同构
`workflow_approval_inject.py` 但**更简单** (无状态切换):

- workflow 那个有 true/false 两种相反注入内容 (放开/收紧切换), 还要物理改 CLAUDE.md。
- 本 hook **无状态**: 只无条件 (或 goal flag 门控) 注入一段**固定**自检文案, 不改任何文件。
- 注入式没有 Stop hook 的误拦风险——常驻注入最坏只是多占一点 context, 不会主动伤害。所以
  **建议无条件注入** (不加 goal flag 门控), 省掉「门咬合」那套复杂度; 文案首句已自带
  「如果有 active goal」的自我门控, 由 CC 自己判断是否适用, 比 flag 文件更鲁棒。
- 挂 SessionStart + UserPromptSubmit (同 workflow_approval_inject), 在 settings.json 的
  这两个事件数组各加一个 `{"type":"command", "command": "...turn_exit_self_check_inject.py", "timeout":10}`。
- fail-safe: 任何异常 → 输出空 / 不注入, 绝不阻断回合 (UserPromptSubmit hook 异常不该卡用户)。

骨架 (≈40 行, team-lead 可直接用):
```python
# -*- coding: utf-8 -*-
"""回合收尾自检注入 — UserPromptSubmit + SessionStart 在回合开始注入一段
固定的『出口门自检动作』, 影响 generation。无状态、不改文件、异常即不注入。"""
import sys, json

SELF_CHECK_TEXT = """(上面注入文案草稿正文, 替换占位后填入)"""

def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw and raw.strip() else {}
        ev = data.get("hook_event_name")
        if ev not in ("SessionStart", "UserPromptSubmit"):
            ev = "UserPromptSubmit"
    except Exception:
        ev = "UserPromptSubmit"
    out = {"hookSpecificOutput": {"hookEventName": ev,
                                  "additionalContext": SELF_CHECK_TEXT}}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        main()
    except Exception:
        pass  # 异常 → 不注入, 绝不阻断回合
```

---

## 与其它两侧 (knowledge / CLAUDE.md) 的接口

- 执行侧只**指向**台账和 fact 锚点, 不**定义**它们 (那是 km 侧的活)。引用已经 km-skeptic + km-arbiter
  核实定稿: 台账 = `cc_context/knowledge/standing-authorizations.json` (km 负责建/维护); fact 锚点 =
  判据主锚 [[fact-decision-boundary-is-ability]] (km-arbiter 知识侧新建, 落地后进 live 树) + 三个既有
  harness slug ([[lazy-mode]] / [[workflow-approval-not-avoidance]] / [[root-cause-over-symptom]],
  我已核实存在)。
  **执行侧无硬阻塞依赖**: 唯一未落地的 [[fact-decision-boundary-is-ability]] 跳空也不影响注入 (注入文案
  不走 check_memory_tree gate), 且判据这条同时挂了现通的 [[lazy-mode]] 不空挂; 知识侧 patch 落地后两边
  自动接上。注入文案落地与知识侧 patch **谁先谁后都行**。
- CLAUDE.md 新段落 (builder §D 的「任务推进方式（回合出口门）」rewrite) 我**保留**——它是行为契约
  本身, 注入文案是它的 generation 侧投影, 二者一致 (同样的四终态、同样指台账+夹具)。但 §D 里
  「各种新马甲例子已移出本段、进 stop_gate 回归夹具」这句要改: Stop hook 砍了, 夹具不再是生产物。
  → 改成: 新马甲例子进 **CLAUDE.md 散文保留 2-3 个典型 + 不再扩列**, 或移进上游 fact 节点正文。
  夹具 (test_stop_gate.py / 对抗样本) 降级为**设计期证据存档**, 不进 ~/.claude, 留在
  cc_context/review/tp_overhaul_design/ 作「为什么砍 Stop hook」的留档。
```
