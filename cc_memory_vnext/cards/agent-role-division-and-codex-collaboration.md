---
id: agent-role-division-and-codex-collaboration
kind: decision
title: 多代理分工——Fable5=数学面负责人(定方向)、Opus leader=发布面负责人+半队长(协调+发布面直做)、实现优先派 codex 省额度;codex 一次性执行任务书 / 矛盾指令按序执行 / 冲突停下澄清 / 改动真实落盘
summary: owner 2026-07-03 定的多代理分工模型 + 同日亲历的 codex 协作特性。**分工**:①**Fable5=数学面负责人**——数学面(routing/CP-SAT/canonical/生成器/loader 这类非对抗)的方向、计划、技术选择由它定,leader 不指挥不干预,最多给"当前情况说明"(leader 去指挥数学面反而拖累负责人);②**Opus leader(我)=发布面负责人+半个队长**——发布面(checker/reseal/close-kernel/外审 triage)直接做,队长那半=协调/派活/跨面编排,但对数学面只协调不指挥;③**具体实现优先派 codex 省额度**,不让负责人亲自写;方向已定的纯实现活直接 codex,只有需要定数学面方向/计划时才请 Fable5 出场、leader 只给情况不插手方向。判据:数学面任务"方向已拍板、纯执行"→ 直接 codex;"要定方向/计划"→ Fable5 定、codex 实现。**codex 协作特性**(2026-07-03 亲历):codex 子代理按**原始任务书一次性执行**,能收中途 SendMessage 但**按到达顺序执行**——发了自相矛盾两条(先"撤 X"后"别撤 X"),它先执行先到的、遇后到冲突时**停下来讲清楚、不默默处理**(很负责);铁律=**派 codex 指令一次写全、别指望中途改**。codex 改动**真实落盘**(别误判成 sandbox 隔离不同步——2026-07-03 我误判过,实为它忠实执行我"撤 T1"指令)。
scope:
  domains:
    - multi-agent
    - orchestration
    - collaboration
  paths: []
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - divide-agent-roles
    - delegate-implementation
    - spawn-codex-subagent
    - assign-math-vs-publish-work
  keywords:
    - 分工
    - 数学面负责人
    - 发布面负责人
    - 半队长
    - Fable5
    - codex
    - 实现优先
    - 省额度
    - 派活
    - 方向
    - 矛盾指令
    - 一次性执行
    - 落盘
    - sandbox
    - 指挥
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 这个数学面小任务派谁做
    - codex 收到我中途改的指令吗
    - 数学面方向该我定还是 Fable5 定
    - 为什么 codex 的改动不见了
activation:
  layer_hint: L1
  must_know: false
  reason: 派数学面/实现活、或派 codex 时该想起——分工搞错(leader 越权指挥数学面方向、或让负责人做纯实现浪费额度)、或对 codex 指令中途改导致矛盾,都是自然会犯的;2026-07-03 当天多次实犯并被 owner 纠正。
provenance:
  op: record
  reason: owner 2026-07-03 明确的多代理分工模型(Fable5=数学面负责人 / 我=发布面负责人+半队长 / 实现优先 codex),及同日 codex 协作特性(矛盾指令按序执行+冲突停下澄清+改动真实落盘)的亲历。
  evidence:
    - "2026-07-03 批次3:owner 纠正'别给 Fable5 当数学面指挥''实现优先 codex 省额度''Fable5 是数学面负责人、你是发布面负责人兼半队长';据此停 Fable5、批次3 纯实现改派 codex。"
    - "2026-07-03 codex-batch3:我先发'撤出 T1'又发'别撤 T1 我要 reseal',codex 按序先撤 T1+提交 T2+T3、遇第二条冲突停下澄清;我一度把 T1 丢失误判为 codex sandbox 不落盘,实为 codex 忠实执行我矛盾指令。"
  updated_at: "2026-07-03"
---
多代理分工模型 + codex 协作特性(owner 2026-07-03 定 + 当天亲历)。

== 分工模型 ==
- **Fable5 = 数学面负责人**:数学面(routing/CP-SAT 建模、canonical 语义、生成器、loader 这类不含对抗性语料的活)的**方向、计划、技术选择**由它定;leader 不指挥、不干预,最多给它"当前情况说明"。理由:leader 去当数学面指挥反而拖累负责人自主发挥。
- **Opus leader(我)= 发布面负责人 + 半个队长**:发布面(checker 硬化、reseal、close-kernel 登记面、外审 triage)直接做(Opus 不被分类器降级);"半队长" = 协调、派活、跨面编排,但**对数学面只协调不指挥**。
- **具体实现优先派 codex 省额度**:不让负责人(Fable5)亲自写实现。方向已定的纯实现活 → 直接 codex;只有需要定数学面方向/计划时才请 Fable5 出场、且 leader 只给情况不插手方向。

== 判据 ==
数学面任务:**方向已拍板、纯执行** → 直接派 codex(省额度);**要定方向/计划** → Fable5 定、codex 实现。凡碰 checker/reseal/对抗性 = 发布面 = leader 自己做(leader=Opus 口径见 [[guardrail-delegate-adversarial-reads]])。

== codex 子代理协作特性(2026-07-03 亲历)==
- **一次性执行任务书**:codex 按你派它时的原始任务书跑;它**能收到**中途 SendMessage,但按**到达顺序执行**。
- **矛盾指令按序执行 + 冲突停下澄清**:我先发"撤出 T1"、后发"别撤 T1 我要基于它 reseal",codex 先执行先到的(撤 T1、提交 T2+T3),遇到后到的冲突时**停下来把冲突讲清楚、不默默处理**(很负责)。→ 铁律:**派 codex 指令一次写全,别指望中途改**;真要改就明确标"以此条为最终"。
- **改动真实落盘**:codex 的文件改动是真的(不是 sandbox 隔离不同步)。2026-07-03 我一度把"T1 改动不见了"误判成 codex sandbox bug,实际是 codex 忠实执行了我"撤 T1"的指令——**别把自己指令的后果甩锅给工具**。

与 [[guardrail-delegate-adversarial-reads]](隔离/降级)、[[agent-longrun-wait-wake-protocol]](teammate 唤醒)同族,一起构成多代理协作基建。

== 更新 2026-07-10（owner 拍板）：审查类活也默认 codex ==
diff 语义审查、修复批独立审查、preflight「改核心文件建议 AI 语义审查」WARN 的响应审查——**以后默认派 codex，不再用 opus**（owner 原话「审查以后也交给codex来」）。战绩背书：2026-07-09 codex 独立审查 C1 patch 在生产 cell 点火前抓出 clone 杆裸奔致命 bug；同日 GPT Pro bug 审的 dedup 段错误雷也是外部模型抓的。opus 审查（如 2026-07-10 硬化批 SEMANTICS_PRESERVED 那次）是该拍板前的最后一次。通道：codex MCP（会话启动时验 `ToolSearch "+codex"`）或 CLI `codex exec --sandbox read-only`（回退，见 cachy 环境卡）。审查提示词纪律照旧走 [[review-prompt-audience-purity]]。

== 更新 2026-07-10 深夜（owner 拍板）：计划书/任务书主会话自己写 ==
三类活的分工判据定稿（owner 推理原话大意：计划书需要先了解背景、且是流程大头，跟审查「必须派另一个模型」、实现「大头在具体工作」都不同）：**①计划书/任务书 = 主会话自己写**——背景理解与方向判断是大头，全在主会话上下文里零成本；外包 codex 则「喂背景的派单提示词本身≈半份计划书」，且它只知道被告知的（2026-07-10 批 1 任务书实例：codex 草稿质量高但四条关键修订全是主会话背景型判断补的）。**②审查 = 必须另一个模型**（codex/GPT Pro，独立性是本质）。**③实现 = codex**（工作量大头，省额度）。

== 更新 2026-07-10（owner 补充）：审查环节按 CC 额度弹性调度 ==
修订上一条「审查一律 codex」：**看当时 CC 额度**——额度多 → **opus 与 codex 双审并行**（暂行观察：若两者耗时差距过大——大概率 codex 更慢——则退为单走 opus）；额度少 → 单走 codex。owner 理由：主会话最后总会复核一遍，此环节「说重要也重要说不重要也不重要」，适合灵活变化。计划书=亲写、实现=codex 两条不变。


### 审查阵容暂时升级 fable+codex(owner 2026-07-10 凌晨,CC 额度刷新期)
owner:「现在wf可以随便派fable了(暂时),那审查就暂时换成fable+codex」——弹性制的「额度多」档从 opus+codex 升级为 **fable+codex**,自 1C 起生效;额度紧张时回落按原弹性制。同期实测背书:gpt-5.6(codex 侧新模型)双 effort 考试大胜——xhigh 抓到 opus/5.5/主会话三方全漏的交叉场景 BUG,ultra 再多抓跨文件交互 bug(nogood 断链)+边角输入(重复 pose_id),零误判;codex 侧默认 xhigh、手术核心批可上 ultra("max 推理+自动任务委托")。

### fable+codex 首战战绩 + GPT-5.6 Pro 复审代差实证(2026-07-10 深夜)
**1C 双审首战(fable+codex)**:两家结论冲突(fable PASS_WITH_NOTES/codex BLOCK),终审裁决 codex 两 BLOCK 全实锤(缺杆模板 fail-closed 漏洞+调用链异常屏障,均附最小复现);fable 零 BLOCK 但侦察极扎实(5 NOTE 全带实验数据:中间层 stub 真剪实验/pinned 工件 4761 pose 统计/checker 静默退 1 定位),其一次性实验被固化为 T14 回归。**互补形态定型:codex 管"往死里挑",fable 管"把现场摸透"**。
**GPT-5.6 Pro vs 5.5 Pro 复审对比(cut framework 同题材同快照)**:5.6 抓到 5.5 的同一 P0(integrity bypass,已被 c7cd6a0 拦)+**两个 5.5 漏掉的可复现问题**(ghost 轴反置 BLOCKER/scope 自删,当前 HEAD 仍复现,修复批规格书 ce6f703 已备)+3 份 RFC+4 补丁,交付形态=完整工程包(SHA256/evidence/repro 脚本/patched 测试日志)。结论:5.6 系对 5.5 系是审查代差,强项=测试盲区型 bug(square 掩盖非方形/组合负例失真),与本地 codex 5.6 在 1B/1C 的表现同向。
