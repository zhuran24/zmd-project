# 记忆系统「召回触发」讨论纪要 + 瓶颈

> 日期:2026-06-28(团队会议在本会话进行)。
> 范围:记忆系统 v-next 的第三个问题——「卡片召回的触发条件」——的完整讨论记录,
> 含五席团队辩论、撞到的命门、收敛出的分层方案,以及 owner 随后戳穿的**更深一层瓶颈**
> (它把整件事逼回到 v-next 的存在理由本身)。
> 这份是讨论档案,不是最终拍板;最后是一个**待决的价位选择**。

---

## 0. 一句话总览

「在我需要的那一刻、对的卡及时出现」这个理想,被证明**分三档**:有事件可钩的时刻能自动、确定、即时地解;我**外露成文字的思考**只能靠一个**每回合看守**(花钱、慢一步)够到;而**纯粹没露出水面、又涉及稀有卡的念头**——只有「我自己想起来去查」能救,而那正是 v-next 当初要消灭的死穴,**真盖不住**。所以最终问题缩成一句:**愿不愿意为「够到我写出来的思考」那一档,付每回合一次小模型调用的钱。**

---

## 1. 背景:三个问题怎么来的

owner 注意到:v-next 在会话开始注入 T0 卡片,而旧 cc_memory 也在会话开始注入一坨(元手册 + 覆盖域图)。由此引出三个问题,owner 决定**分开、一个一个讨论**:

1. **① 老系统初始注入内容是否整合**(readfirst 的元手册指针 + 覆盖域图 + 维护提醒,跟 vnext T0 是否冗余、删/迁/留)。
2. **② hook 的迁移**(发现 `cc_memory_readfirst.py` 错挂在**全局** `~/.claude/settings.json`、写死本项目路径、不判当前项目 → 在任何别的项目开 CC 都会注入本项目记忆 = 泄漏)。owner 裁:**不用讨论,直接做。**
3. **③ 卡片召回触发条件**(召回只挂 UserPromptSubmit、拿用户提示词当 haystack;Claude 中途自发的动作/思考不在提示词里 → 该触发的卡不触发)。

顺序:②(直接做)→ ③ 先讨论(杠杆大)→ ① 后讨论(部分卡在整库迁移/冻结未决裁决)。本文件覆盖 ② 的落地结论 + ③ 的完整讨论。

---

## 2. 问题 ②(hook 迁移)— 已做掉

- **病**:`cc_memory_readfirst.py` 挂在全局 settings、写死 `C:\claude pj\zmd_pj\cc_memory`、只判固定路径存在(永远存在)、不判当前项目 → 全局每个会话都注入本项目 cc_memory 元层 = 项目记忆泄漏到无关会话。它是**唯一一个被放全局的项目级记忆 hook**(其它 cc_memory hook 和 vnext hook 都在项目 settings.local.json)。
- **修**:脚本搬进 `cc_memory/hooks/cc_memory_readfirst.py`(自定位路径 `__file__→cc_memory/`,归项目、随仓库版本化)+ 注册移到项目 `.claude/settings.local.json` + 删全局注册与孤儿脚本。实测脚本输出 JSON OK、两 settings 合法。提交 `17540c7`(push 撞 topology-opt 分线合并的 PR #1,精确确认无冲突后 `--autostash` 安全 rebase,没碰那条线 WIP)。
- **效果**:下次会话起 readfirst 只在 zmd_pj 触发,不再泄漏。

---

## 3. 问题 ③(召回触发):团队讨论全程

### 3.1 问题陈述

v-next 卡片召回靠 **UserPromptSubmit hook**,拿【用户提示词文本】当 haystack 匹配卡的 trigger/scope/claim_guards。但 Claude 实际工作**远超提示词**——中途 spawn 子代理、跑 git、改 frozen 文件、走提示词没点名的路径。那些时刻该触发的卡**不会被召回**。

**真实例子(本会话亲历)**:owner 说「开始做 b」→ 系统拿「做 b」匹配 → 我中途自己决定 spawn codex 子代理,该弹 `codex-agent-subagent-is-async` 卡的那一刻,「开始做 b」里没有 codex/异步 任何触发词 → 卡没出现 → 我真踩了坑(后来 codex 自己审出来)。**该提醒的那一刻是我动手那一刻,但系统只看 owner 开头那句话。**

### 3.2 五席团队 + 各自立场

(注:形式 = Agents Team 互辩;以下是各席核心立场,已收敛。)

**skeptic(怀疑/最小主义)**:问题真,但「全量 PreToolUse 用工具裸参数当 haystack 召回」是最差解。5 条硬伤——① 每动作 subprocess 冷启延迟(现 hook 每回合一次、PreToolUse 每动作一次);② flood 复活 + 无跨注入去重(改 frozen 5 次→同卡注 5 次);③ 工具裸参数 haystack 质量差(`git add -A` 才几 token、bm25 假阳性爆,唯一可靠=path 匹配);④ blast radius 抬高(召回 hook 坐工具前,fail-closed/出错卡死 agent);⑤ 治错层(永远相关 must-know 该 L0 常驻、不该每动作召回)。主张:不建全量;建 **(b) L0 常驻** + **(a) 只钩高危少数**(path-glob/命令前缀,只用可靠信号);否决 (c) PostToolUse(它当时认为太晚)。

**hook-mechanics(可行性 grounding)→ 命门、整场转折点**:头一遍查项目自己的文件,误得「PreToolUse 不能注入 additionalContext、只能 deny」;被要求查**官方文档**后**结论反转**:
- PreToolUse **能**发 `additionalContext`,**但官方明写它注入在【工具执行之后】(next to the tool result)、不是之前**,用途是「annotate/comment on results」。
- 执行**前**唯一能动的只有 `permissionDecision`:`deny`(挡+reason)/ `ask`(强制弹框+reason、要用户点)/ allow / defer。
- 真·执行前注入只有 **subagent-splice**(spawn 前把卡片 append 进子代理 prompt)。
- 失败语义 fail-open;能拿到 tool_name + tool_input。

**pro-action(动作召回设计派)**:给了两个让窄闸能打的机制,但被命门修正:
- **关键技术点(贯穿所有通道、不绑死掉的投递方式)**:`compile_context` 把结构化信号(paths/symbols 走确定性集合匹配)和 bm25(prompt/keywords)**物理分开**。PreToolUse frame 只要 `prompt=""`、只填 paths/intents/symbols → **bm25 恒为 0 → skeptic 硬伤③(裸参数假阳性)由构造消失**。这是**选卡机制**,与投递通道正交。
- **会话级注入账本**去重:改 frozen 5 次同卡只注 1 次;注入量上界 = 本会话不同 armed 卡数,与动作次数无关。
- **被命门修正后的最终归类**(三通道):codex spawn→【执行后 additionalContext 正好】(坑在 spawn 返回后的误排序);git commit/add→【执行前必须 deny/ask 拦】(扫进别人 staged、不可逆);frozen edit→【执行前 ask】(有时是合法 ritual)。**advise-only「执行前温和注入」这个形态死了**——它坍缩并入 README 的 MVP-1a 高危阻断。
- **账本只活在【建议/执行后】通道,绝不碰 deny**(否则压住第二次 deny=放危险动作过去=安全系统漏 must-know,正是它自标的最坏失败模式)。

**measurement(测量与覆盖纪律)**:
- 约 **40% must-know 卡是「动作时刻」卡**,且偏偏是不可逆/对外那几张最贵的;真正漏的是「**自主多步漂移**」(动作离授权它的 prompt 隔了好几步)。这一片占比是**未测黑数**。
- **eval 数据层已能表达**动作 frame(frame 本就是 dict、force_reason/scope_match 已吃 paths/symbols);缺 ① `source:prompt|action` 判别字段 ② 真正该测的是「**工具调用→frame 的投影函数**」,eval 存原始工具调用、走 hook 同款投影,测整条链。
- **red-line A** 在动作召回下会被**字面**绕过(frozen 卡 scope.paths 就是那文件、paths 一填就==scope);救法=判据从「字面要不同」改成「**出处必须是真实记录的工具调用**」(从 transcript 取、非卡作者采、带时间戳),反而比 prompt 那套更可审。
- **「先测后建」5 步**:① 先装**影子 hook**(算投影+跑编译,但**只 shadow 记录「本会注啥」、一张不真注**)② 拿真实 transcript 挖「卡相关+prompt 没注+动作会注」的真事件计数=功能真实载荷,≈0 就停 ③ 用真事件造 action 金标准 ④ eval 按 source 拆红绿、纯脚本打 100% ⑤ 建多少由实测数封顶。**关键洞见:影子阶段不需要 additionalContext(只 log 不注),所以对命门免疫。**

**resident-design(常驻替代派)→ 关键代码事实**:
- `force_reason()` 里真正驱动 L0 的只有:`session_start_l0`+intents含session-start(对**任何 kind** 生效,**是 pitfall 唯一能进 L0 的途径**)、constraint 走 scope.paths-glob/symbol/claim_guards、status 走 phase/claims、open_obligation 走 always_on/arming。**pitfall/decision/file_local/reference 在 force_reason 里没有 kind 分支 → route-time 永远进不了 L0,最多 L1 抢 quota。`must_know`/`layer_hint` 不被代码读、纯文档。**
- 推论:`codex-async`、`concurrent-git` 都是 pitfall → route-time 只能到 L1、自发动作时连 L1 都进不去 = **它们漏的根因**。
- **三卡裁决(经命门修正)**:`concurrent-git`→升 session_start_l0 常驻(最该)+ 危险 shape(`git add -A`/无 pathspec commit)窄 deny 当保证层;`frozen-ritual`→不常驻,执行前 **deny**(冻结契约 fail-closed 是认证线精神,deny 正是正确语义)+ 罕见合法 ritual 用 env 解闸/ask;`codex-async`→弱基线常驻 + **执行后 additionalContext / 完成通知回合 splice**(坑在 spawn 下游、绝不该 deny)。
- **L0 预算**:session_start_l0 ≤ 5-7 张;always_on ≤ 2-3。判据 = P(本会话发生该动作)×漏一次损失 ≥ 一个永久槽的注意力稀释。
- **(b) 常驻盖不住的(=留给 (a)/别的)**:按动作/文件的精确命中 + 执行前拦截、长流程正文、稀有具体坑的长尾、位置衰减 + /compact 后丢失(**常驻是基线、不是保证;保证需 always_on 或 (a)**)。

**codex-voice(跨模型独立)→ 补了所有人都漏的第三条路**:
- **代码事实**:UPS hook 只把 payload 里**显式 paths 字段**搬进 frame,**不从 prompt 文字提取路径**;`frame_haystack` 也不含 paths/symbols。所以「改下 frozen 规则」没带结构化 path → 约束卡进不了 L0;且 constraint **没有 L1 quota 位** → 非强制命中直接掉 L2 指针(基本没人读)。**信号通道结构性断裂。**
- **第三条路 = 增强 UserPromptSubmit 的 frame 提取**:确定性抽 repo/Windows 路径、符号、风险动词(git add/commit/freeze/publish/seal)→ 喂现有管道。**这入口在 Claude 形成方案【之前】,比 PreToolUse 早、比常驻便宜、能影响 reasoning、不需新 hook。**
- **优先级**:frame 富化(早+便宜+影响思考)> L0 常驻(全局托底)> 窄闸 PreToolUse(执行前最后门)。
- **Catch-22(独立印证 hook-mechanics)**:PreToolUse 是「执行前刹车」不是「思考前召回」——选工具/成方案的认知在 reasoning 阶段就结束了,PreToolUse 触发时决策已在飞。它只能拦动作、改不了已成形的烂方案。

### 3.3 命门(决定方案形状的两个硬约束)

1. **时机**:PreToolUse 的 `additionalContext` 落在**执行之后**;执行前只能 `deny`/`ask`(阻断)。→ **「动作前温和提醒」这个形态根本不存在。**
2. **Catch-22**:烂方案在 reasoning 阶段成形,PreToolUse 触发时已晚;它能拦动作、改不了思路。

### 3.4 收敛出的分层方案(按「影响认知:早→晚」)

| 层 | 机制 | 管什么 | 通道 |
|---|---|---|---|
| **0. UPS frame 富化** | 给读消息那步加确定性提取器,从 prompt 文字抠路径/风险动词/符号喂管道 | 信号在 prompt 里但没被抽出来 | 最早、最便宜、影响 reasoning、不需新 hook **(最高优先)** |
| **1. L0 常驻** | 把少数「整会话恒真、自发动作、漏了高代价、≤2行」的卡升 `session_start_l0`(pitfall 唯一进 L0 途径) | concurrent-git(最该)、precompact 纪律、codegraph;codex-async 弱基线 | 预算 ≤5-7;**基线非保证**(衰减/压缩后丢) |
| **2. PreToolUse 窄门** | 只认可靠结构信号(path-glob+命令首动词),绝不碰 bm25 | 不可逆危险动作 | **执行前 deny/ask**(frozen edit、`git add -A`、`rm -rf`)= MVP-1a;**执行后 additionalContext**(codex-async);**spawn-splice** |
| **纪律. 影子先行** | 先只 shadow log「本会注啥」、一张不真注,挖真实漏掉计数,≈0 就停 | 防止盲注不存在的问题 | eval 加 source、测投影函数、red-line A 改判「出处=真实工具调用」 |

**死的**:「PreToolUse 能在动作前温和召回卡片」——它只能 block。
**活的**:底层需求被**重新路由**到四层。

---

## 4. 更深的瓶颈(owner 戳穿的)

团队收敛后,owner 觉得**偏了**——大家被「hook 机制能干什么」牵着走,绕着限制做文章,把真正要的东西放掉了:「**在我需要的那一刻,对的东西及时出现**」。owner 进一步精确化:不是「做什么之前」,而是「**当我想到什么、或遇到什么的时候**」。

### 4.1 拆成两件很不一样的事

- **「遇到什么」**(撞错/拿到结果/读到文件)= 真实发生、系统看得见的那一下(PostToolUse)。**能解,而且上一场会小看了它。** 卡片本就有 `error_regex` 字段,专为「撞到这个错→弹这张卡」设计。例:`git push` 撞 `non-fast-forward` → 推送冲突卡当场弹。上一场把 PostToolUse 当「太晚」否了——**那是对「拦动作」太晚,对「撞上后指路下一步」时机正好。**
- **「想到什么」**(念头在脑子里,还没动手)= **真·硬骨头**:**系统里没有任何钩子钩在「我正在想」那一刻。** 我的思考只有变成 ① 工具调用 ② 写出来的字(且要等整回合说完)才露出水面。纯念头系统看不见,没法在那刻注入。

### 4.2 owner 的悖论(整场最深的一刀)

owner:「那唯一的办法就是你主动去找了,但这样不就又回到旧系统上了吗?如果你能主动找,那旧系统也没这个问题了。」

逻辑链:think 钩不住 → 只能我主动找 → 那就是旧系统 → 旧系统正因「指望我主动找」才废 → 绕回原点。

### 4.3 解套(这一刀里有一节对、有一节藏了岔路)

- **对的那节(认)**:一个**纯在脑子里、既没写出也没动手**的念头,确实只有「我自己想起来去查」能救,而那正是旧系统死穴。**这块真解不了。**
- **藏岔路的那节**:「只能**我**主动去找」——悄悄塞进了「我」。旧系统病根不是「要去找」,是「要**我**去找」(指望消费者起念头)。还有第三个选项:**一个旁边的看守,替我去找、然后推给我。**
  - 旧系统 = **拉**:库等我来拽,我不拽=没有。
  - 看守 = **推**:独立进程读我刚写的字,发现我漏了张卡,主动怼到我脸上。**我不用想起来去看,是它替我看。**
  - 所以**看守不是回到旧系统,恰恰是它的反面**——把「注意到该 retrieve 了」从**我**(不靠谱)挪到**自动旁观者**。

### 4.4 点破 v-next 的真正本质

v-next 从来不是「卡片 vs 数据库」——存哪儿不重要。真本事是:**把「注意到该 retrieve 了」这个动作,从我身上拿走、交给一个自动触发器。** 旧系统存得好好的,死在「retrieve 要靠我起念头」。

### 4.5 三档谱 + 真正盖不住的残余

顺着本质,整件事是一个**谱,越往后覆盖越多、越贵**:

1. **有事件可钩的时刻**(发消息/调工具/撞结果)→ 自动触发器,**免费、确定、即时**(现 v-next + 该补的 PostToolUse)。
2. **「想到」但我写出来了**(reasoning 里嘴上说「我去 spawn 个 codex」)→ 没事件钩它,但**看守读我写的字能逮到**。不是我查、是看守查。代价:**每回合一次小模型调用 + 慢一步**(救不了这回合第一下、能救下一步)。= precompact「判官」从「压缩时一次」挪到「每回合」。
3. **纯念头从没露水面**:
   - 涉及那几张「永远相关」的卡 → **常驻能救**(本就在眼前、不用 retrieve)。
   - 涉及某张**稀有又具体**的卡 → **真没救**(没法全常驻,又没事件、没外露文字给看守抓)。**这一格 owner 赢,盖不住。**

**所以不是绕回原点,是分了三档**:前两档把「注意」从我身上挪走(没回旧系统);常驻救下纯念头里高频那几张;只有「连影子都没留下、又涉及稀有卡的纯念头」才真回到「只能靠我」,**而那一格又小又罕见。**

---

## 5. 收敛到的真问题 = 一个价位选择

> **愿不愿意为「够到我写出来的那部分思考」,付「每回合一次小模型调用」的钱?**

- **愿意** → 「每回合判官/看守」就是答案(v2 早埋伏笔:necessity-LLM / 行为日志)。覆盖从「事件时刻」推进到「我外露的思考」,代价是钱 + 慢一步。
- **不愿意** → 停在「**事件时刻全盖(补 PostToolUse + UPS 富化)+ 几张常驻**」,接受「自发漂移」那条缝靠压缩时判官兜底。

两种都**严格优于旧系统**(旧系统可靠覆盖 = 零)。差别只是「事件时刻」之外那条缝盖到多深。

---

## 6. 待决 / 下一步

- **待 owner 拍**:上面那个价位选择(每回合看守 要不要)。
- **无论选哪个,都先能做的(不依赖该决定)**:
  - **Layer 0 UPS frame 富化**(最高杠杆、最低风险、不需新 hook)。
  - **Layer 1**:把 `concurrent-git` 等极少数卡升 `session_start_l0`(几乎零成本;先确认 force_reason 的 session_start_l0 通道 + L0 预算 ≤5-7)。
  - **PostToolUse 的「遇到」召回**(error_regex 驱动)——这是上一场漏挖、且最贴 owner「遇到就弹」诉求的一块,值得单独细化。
  - **影子测量**(Layer 2 任何真注入之前):量「自发漂移」那条缝到底多大,用真实数据决定建多少。
- **本议题(③)未拍板前,不动手真注入**;且这套是**设计共识、不是已落地**。
- 关联未决:① 老系统注入整合(还没讨论)、整库迁移/冻结三处文档矛盾(见 `memory-layer-authority-transition` 卡 + HISTORY §4)。

---

*纪要由本会话 team(skeptic / hook-mechanics / pro-action / measurement / resident-design / codex-voice 六席)辩论 + owner 戳穿瓶颈收敛而成。命门(PreToolUse additionalContext 落执行后)经官方文档 code.claude.com/docs/en/hooks 复核。*
