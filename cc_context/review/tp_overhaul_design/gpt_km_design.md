我把材料包和 scripts/check_memory_tree.py 都解开看过了。结论先放前面：**两层 normalize 的方向是对的，但不要物理拆成另一个目录。**最稳的落地形态是：仍放在同一个 cc_context/memory/ 命名空间里，新增 fact_*.md 一等节点，frontmatter type: fact，投影节点用一行 > 事实依据: [[fact-*]] 回指。这样不改现有 wikilink 解析模型，不引入第二套扫描路径，也能直接吃现有 gate。

我做了一个可应用补丁包，里面包含首批 7 个 fact 节点、首批 projection 回指、MEMORY.md 直连覆盖块、check_memory_tree.py fact gate、sync_memory_to_harness.py 第三投影同步强化。下载：
normalize_memory_facts_patch_bundle.zip

补丁在解出的 snapshot 上验证过：

memory graph: nodes=101, links=337, resolved=337, unresolved=0
memory facts: facts=7, projection_edges=23, baseline_exemptions=40
MEMORY.md size: 20494/24576 bytes
live memory mirror: 102 files byte-identical
memory tree check passed: 101 nodes, index within cap, graph/currency healthy

harness 模拟同步后 MEMORY.md 是 22735/24576 bytes，仍低于上限。

1. 结构定型：不是“第二棵事实树”，而是同一图里的 fact 节点

落地约定：

cc_context/memory/fact_*.md
frontmatter:
  name: fact-...
  metadata:
    node_type: memory
    type: fact

投影节点统一加一行：

Markdown
> 事实依据: [[fact-decision-boundary-is-ability]] [[fact-understand-before-output]]

这样做的好处是非常实际：

第一，check_memory_tree.py 当前只扫一个 memory dir，wikilink 也只认同一个 name: 命名空间；把 fact 放进同一目录，零架构迁移。

第二，MEMORY.md missing N nodes 的坑可以直接规避，因为每个 fact_*.md 都在 MEMORY.md 里用 md-link 直接列一次，不依赖父索引传递覆盖。

第三，projection 不需要被重写。第一轮只给最高杠杆节点加“事实依据”行，把抽象事实从正文里剥出来；原文暂时可以保留，后续瘦身时再删重复解释。

2. 你的 7 条候选怎么精炼

我会把你给的 7 条压成 6 条行为/验证事实 + 1 条会话状态事实。关键调整是：你候选里的 1 和 2 应该先合并成一个“决策边界/授权边界”事实；同时把你举的真实例子「GPT 无状态 / 跨窗口不带」补进第一批，因为它已经造成 opsec 推理错接，是高杠杆事实。

首批 7 个 fact 节点如下。

fact slug	抽象事实	首批回指 projection
fact-decision-boundary-is-ability	能不能问 owner 的判据是“我能不能自己定/做”，不是措辞；已给目标、既有先例、已放开的开关都是站着的授权；真 owner-only 只剩外部状态、不可推偏好、不可逆高风险。	root-cause-over-symptom、lazy-mode、no-reply-means-agree、workflow-approval-not-avoidance、subagent-for-closed-loop-tasks、no-gpt-concurrency-field
fact-understand-before-output	LLM 默认病是“收到消息就立刻产出一个可见反应”，跳过理解意图和根因；正确顺序是先理解/找因，再答/做。	root-cause-over-symptom、directly-state-core-finding、memory-value-yardstick
fact-evidence-before-story	干净叙事不是证据；N=1、终态出现、重试成功都不能定因；明确数字/规则优先于编出来的来源故事。	no-causal-claim-from-n1、verify-solver-param-claims、verification-independent-backstop
fact-self-report-is-not-evidence	外部模型/工具/我自己的自验摘要、明面 metadata、单次结果都不是最终证据；可信度来自独立复现、对拍、端到端验收和可判别 probe。	verification-independent-backstop、no-gpt-downgrade-evidence、agent-vs-workflow-dispatch
fact-zero-finding-is-not-proof	审查零 finding 只能说明该审查没找到问题，不能证明没问题；终结靠独立 oracle/fuzz/proof，或多轮独立零 finding 加外部计数闭合。	verification-independent-backstop、authoritative-numbers-single-source、memory-currency-protocol
fact-forcing-function-required	反复复发的行为/状态漂移不能靠“再写强规则”根治；要 hook/test/gate/stamp/生成器，规则只做 fallback。	authoritative-numbers-single-source、memory-tree-structural-health、memory-currency-protocol、zmd-env-ci-gate、zmd-env-prepush-gate
fact-conversation-state-is-window-local	GPT/LLM 会话状态只活在当前窗口/线程/Project 来源区/显式附件里；跨新会话不携带隐式记忆。新任务隔离和 opsec 威胁面都必须按显式材料推导。	no-gpt-send-settings、no-workflow-use-chrome-gpt-review、agent-vs-workflow-dispatch

这 7 个的排序不是“哲学上最干净”，而是“最能止血”：它们正好覆盖你这次诊断的主病灶，且每个都有至少 2 到 6 个现成 projection 可以立刻挂上去，不会变成孤点。

3. MEMORY.md 怎么改，不超限、不 missing、不孤立

repo 当前 cc_context/memory/MEMORY.md 约 19335 bytes，补丁加完是 20494 bytes，还有约 4082 bytes 余量。

新增块放在开头说明之后、## 当前状态 / 交接 之前：

Markdown
## 抽象事实层 (normalize: fact → projection)

> 投影节点只回指这里的事实,不要把抽象事实再复刻成新原子。每个 fact 在 MEMORY.md 直接覆盖,避免父索引传递覆盖失效。
- [决策边界=能力](fact_decision_boundary_is_ability.md) — 能不能问 owner 看我能不能自己做/定; 目标/先例/放开开关=授权
- [先理解再产出](fact_understand_before_output.md) — 默认病是抢可见反应,正确顺序是先读懂意图+根因
- [证据先于叙事](fact_evidence_before_story.md) — N=1/终态/重试不定因; 明确数字/规则优先
- [自报不算证据](fact_self_report_is_not_evidence.md) — 自验摘要/metadata/单次结果不裸信,靠独立复现和端到端验收
- [零 finding 不是 proof](fact_zero_finding_is_not_proof.md) — 审查只能证有问题; 闭合靠独立对拍/fuzz/proof/多轮计数
- [强制函数优先](fact_forcing_function_required.md) — 复发行为/漂移靠 hook/test/gate/stamp,规则只做 fallback
- [会话状态局部](fact_conversation_state_is_window_local.md) — 新会话不带隐式记忆; 新任务隔离与 opsec 都按显式材料算

这里刻意用 md-link 而不是只写 [[fact-*]]，因为现有 gate 对 MEMORY.md 的 coverage 同时支持 wikilink 和 md-link；md-link 还能直接指到 repo 文件名。每个 fact 都直接出现在 MEMORY.md，所以不会踩“只挂在 harness-only 父索引下导致 repo MEMORY missing”的坑。

孤立性靠两层保证：fact 节点正文里列“首批投影”，形成 out-link；投影节点的 事实依据 行回指 fact，形成 in-link。即使以后瘦掉 fact 正文里的投影列表，只要投影回指仍在，fact 也不会孤立。

4. 三投影同步方案

三处的职责要分清：

cc_context/memory/ 是 repo 权威编辑面；_cc_live_memory/ 是字节镜像，必须逐字节一致；harness ~/.claude/projects/<slug>/memory/ 是 auto-memory 真召回面，是第三投影，不是 repo 权威源。

落地动作：

PowerShell
# 1. 修改 repo 权威树
cc_context\memory\fact_*.md
cc_context\memory\MEMORY.md
cc_context\memory\<projection>.md

# 2. 字节同步 live mirror
robocopy cc_context\memory _cc_live_memory *.md /MIR

# 3. 同步 harness 第三投影
python cc_context\tools\sync_memory_to_harness.py --apply

# 4. 验证
python scripts\check_memory_tree.py --require-live-mirror
python cc_context\tools\sync_memory_to_harness.py --check

补丁里已经把 sync_memory_to_harness.py 加固成：

Python
运行
COPY_PREFIXES = ("fact_", "feedback_", "project_", "reference_", "user_")

并新增 harness-only 的 abstract-facts-index。更关键的是，它会自动维护 harness MEMORY.md 的 fact 直连覆盖块，而不是只把 fact 挂到 abstract-facts-index 父节点下。这样第三投影也不会出现“节点存在但 MEMORY 不覆盖”的隐形召回洞。

5. Forcing function：让它别再漂

补丁里把 forcing function 分成三层。

第一层是 repo CI gate，直接塞进 scripts/check_memory_tree.py。新增规则：

fact nodes:
  - name 必须是 fact-* 或文件名 fact_* 或 type: fact
  - 每个 fact 至少要有一个 projection backlink

projection nodes:
  - 新增 feedback/projection 节点必须引用至少一个 [[fact-*]]
  - legacy 未迁移节点放在 cc_context/memory_fact_projection_exemptions.txt
  - 如果 baseline 里的节点后来已经补了 fact refs，但没从 baseline 删除，gate 报红

这解决三件事：

“事实没被任何投影引用”会报红。
“新增规则没接到事实层”会报红。
“迁移完却忘了收缩 baseline”会报红，防止 exemption 变成垃圾场。

第二层是第三投影 gate。check_memory_tree.py 在本机 harness 存在时，会调用：

PowerShell
python cc_context\tools\sync_memory_to_harness.py --check

如果 repo fact/projection 已改但 harness 没同步，会变成本地 preflight blocker。CI 没有 harness 时自动 skip，不会在 GitHub Actions 上误炸。

第三层是 harness MEMORY.md 体积和 coverage。sync_memory_to_harness.py --apply 会维护 managed block，并继续检查 24576 bytes 上限。模拟应用后 harness MEMORY.md 是 22735 bytes，还剩约 1841 bytes，够第一波 normalize 用，但后续每加一批 fact 仍要 slim 旧索引。

语义漂移不能靠纯正则完全证明，但可以把“漂移静默发生”变成“不更新图结构就过不了门禁”。真正的语义层，再加一个周期性审查就够：phase boundary 或大改前跑一次“fact/projection coherence review”，主体是整棵 memory tree，目标是找“projection 说的 why 已经不是 fact 推出的东西”或“正文复刻了 fact 但没回指”。这个审查是第二道雷达，静态 gate 是第一道闸门。

6. CLAUDE.md 怎么对接

CLAUDE.md 不应该继续承载一大坨行为学解释。它应该只留“核心不变量 + 出口协议 + fact 指针”。现在全局 CLAUDE.md 的「任务推进方式」已经膨胀到把多个投影事实揉在一起，正是“投影即原子”的一个显眼样本。

建议把全局段落压成这样：

Markdown
## 任务推进方式：核心不变量

默认是做，不是问。有 active goal 时，本回合只能以四种合法终态结束：

1. DONE：目标已完成。
2. WAITING_EXTERNAL：只剩外部系统/别人回复/长跑任务结果。
3. BLOCKED_USER_ONLY：只剩真正只有 owner 能定的一点残余。
4. TECHNICAL_HANDOFF：技术上必须交接，并已写清恢复点、已完成项、下一步。

能自己做/定的下一步必须继续做，不准用“要不要我继续 / 我现在去做 X / 节奏你定 / 发吗”把控制权踢回 owner。只交真正 owner-only 的残余。

依据事实：
- [[fact-decision-boundary-is-ability]]
- [[fact-understand-before-output]]
- [[fact-forcing-function-required]]

细则不放 CLAUDE.md，放投影节点里：

lazy-mode
no-reply-means-agree
workflow-approval-not-avoidance
root-cause-over-symptom
no-gpt-concurrency-field
subagent-for-closed-loop-tasks

也就是说，CLAUDE.md 是“回合出口门”的精神内核；fact 层是它的依据；具体场景规则是 projection；Stop hook 是真正的刹车。

7. 后续迁移节奏

不要一次性重写 140 个节点。第一轮只落 7 个 fact + 约 18 个首批 projection 回指，这已经足够把主干连起来。

第二轮从 baseline 里按簇消灭，而不是按文件名顺序：

先迁“问 owner / 授权边界”簇：effort-matches-stakes、autopilot-with-review-gate、autonomous-loop-workflow、no-sleep-loop-for-goal-hook。
再迁“证据/叙事”簇：harness-only 的 verify-before-claiming、hallucination-fabricated-rationale-to-override-rule、chatgpt-login-and-completion-detection。
再迁“GPT 交付验收”簇：gpt-delivery-no-blind-trust、gpt-delivery-probe-discrimination、gpt-delivery-dont-track-model-downgrade。
再迁“验证终结”簇：verification-hardening-ladder、verification-calibration-line-1-opsec、verification-diff-fuzz-line-2、verification-per-face-rolling-review-line-3、verification-proof-carrying-line-4。

每迁一个 projection，只做三步：

Markdown
> 事实依据: [[fact-...]]

然后删掉正文里重复的抽象解释，只保留该场景的触发条件、例外、操作步骤和事故样本。最后从 memory_fact_projection_exemptions.txt 删除它的 name。gate 会强迫这件事闭环。

8. 应用补丁

补丁包里有 normalize_memory_facts.patch。在项目根目录应用：

PowerShell
patch -p1 < normalize_memory_facts.patch
python cc_context\tools\sync_memory_to_harness.py --apply
python scripts\check_memory_tree.py --require-live-mirror
python cc_context\tools\sync_memory_to_harness.py --check

补丁包：
normalize_memory_facts_patch_bundle.zip