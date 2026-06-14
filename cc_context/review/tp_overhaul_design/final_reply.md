我看完材料后的判断是：这不是“任务推进方式”段写得还不够细的问题，而是它被放错了层级。

现在的模式是在全局 CLAUDE.md 里不断补“别说 A、别说 B、别用 C 这种马甲”。这会变成打地鼠：每次抓住一个表层句式，模型下次会从另一个出口漏出去，比如从“要不要我继续”变成“我现在去做 X”，再变成“等你定节奏”，再变成“这涉及 owner channel / consequential outward action / commit 会 auto-push / GPT 通道是你的”。措辞变了，但本质没变：回合结束时，把本该自己推进的下一步交还给用户触发。

我觉得要根绝，核心要从“写更长的规矩”切到“禁止不合法的停机状态”。

也就是：不要再把问题定义成“不能问用户”，而要定义成“一个回合只有几种允许结束的状态”。 只要回合不是合法终态，就不许停。这样新措辞没意义，因为判据不再看它说没说“要不要”，而是看它有没有把一个自己能做的 next action 留在回合外。

我会把它抽象成一个叫 Turn Exit Gate / 回合出口门 的东西。每次 assistant 准备结束时，只允许四种终态：

第一，DONE：当前目标下我能做的已经做完，并且给了证据，例如测试、diff、提交、外审结果、文件路径、日志结论。

第二，WAITING_EXTERNAL：我已经启动了外部等待源，且它真的不是我现在能继续推进的东西，例如 GPT 外审已发、后台任务已跑、watcher 已挂、明确在等某个进程或人类外部回复。

第三，BLOCKED_USER_ONLY：只剩真正只有用户能给的信息或拍板，而且必须把“我已经做完了什么、为什么这点只有用户能定、我的默认推荐是什么”说清楚。不能整摊回踢。

第四，TECHNICAL_HANDOFF：上下文压缩、工具不可用、权限缺失这类技术中断，但也必须写明压缩后第一步继续做什么，不能塞一句“等你定节奏”。

凡是不属于这四类的，比如“我接下来去 diff 那 19 个”“下一步等你定 GPT 节奏”“要不要我把这个也做了”“你说一句我就推”，都应该被 Stop hook 拦住，直接反馈给模型：你还有一个自己能执行的 next action，继续执行，不准结束。

这比继续补 CLAUDE.md 有效，因为它堵的是“结束回合”这个阀门，不是堵每个句式的小孔。

材料里最典型的证据是 thread 043 那次：CLAUDE.md 已经有“别请示、能做就做”的原则，但 assistant 仍然用“我现在去 diff 那 19 个漂移节点”结束回合。那句话没有问号，甚至看起来像在推进，但真实效果是让用户必须说“继续”。这说明问题根本不是问号或禁词，而是turn boundary 的所有权。模型在回合边界天然倾向于交还控制权，文字规则只能劝它，不能卡住它。

第二个根因是 “只有用户能定”的例外太容易被模型膨胀。全局规则里其实已经把范围缩得很窄，但项目规则里又有很多高风险/owner/manual/GPT/commit/push/opsec/channel 相关约束。模型一害怕担责，就会把这些约束拿来当“我该问”的理由。它不是故意绕规则，而是安全、礼貌、免责、回合收尾这几种默认倾向一起把它推回“问”。所以光靠“你要主动识别是不是同一个病”不够，因为犯病时它会觉得“这次真是例外”。

解决办法是把这些授权和例外做成数据化台账，而不是散在 CLAUDE 和 memory 里让模型临场解释。

比如建一个 standing authorization ledger，里面明确写：

gpt_dispatch: 在 active goal 是 P1.2 外审闭环、且 approval=false、且没有 owner 明确暂停时，允许直接发；并发上限多少；是否需要报备；哪些情况才是真正要问。

workflow: approval_required=false 时，用前报备一句但不等待。

commit_push: 因 post-commit auto-push，未得到“推/提交/入库”等明确指令时可以停在“待发布”；但用户已说“推”后不能再问。

memory_sync: repo/live/harness 三投影同步属于已授权维护动作，不能问。

opsec_repo_visibility: 涉及把隔离/opsec 信息写入 repo 时，才是真 owner decision。

这样模型不再能临场发明“这是 consequential outward 所以我问一下”。它要么查到这类动作已授权，要么查到明确禁止/需确认。授权从散文变成表，异常从感觉变成枚举。

第三个要改的是 压缩/summary/handoff。材料里有一个很危险的模式：压缩前 summary 或系统摘要会把“下一步等你定节奏”写进去，压缩后新上下文继承了这个错误姿态。也就是说，哪怕当前 CLAUDE.md 写了“目标就是授权”，压缩摘要也可能把未来会话重新灌回“等用户”的轨道。

所以压缩摘要也必须过同一个出口门。尤其是 active goal 未完成时，summary 里不应该出现“等你定节奏 / wait for owner to set pace / do NOT autonomously initiate”这种语义，除非它带有明确来源：用户刚刚真的撤销了站着授权，或者这个动作落在 BLOCKED_USER_ONLY。否则 summary 应该写成：

“压缩后第一步：打当前 HEAD 包，发 face 6/8 确认轮；随后发 face 1/2/4/5 真 Pro 状态核对。不要等待用户继续。”

这点很关键。否则每次压缩都是一次“人格漂白”，旧病会从 summary 里复活。

我认为最小可落地方案是四件套：

1. 把全局 CLAUDE.md 的任务推进段缩短，而不是继续加长。
现在那段已经像一张布满补丁的海图，读得到但不一定能在风暴里照做。应该把它收束成一个核心不变量：

“有 active goal 时，回合不得以可执行 next action 结束。除 DONE / WAITING_EXTERNAL / BLOCKED_USER_ONLY / TECHNICAL_HANDOFF 外，必须继续执行。”

例子不要继续堆在主规则里。例子应该进测试夹具，给 hook 回归用。

2. 加 Stop hook：task_progression_guard。
它不需要一上来就很聪明，先做硬拦截就够有用：

拦截明显请示词：要不要、你定、等你、你说一句、节奏你来、我可以、接下来我去、下一步我会、要的话、是否继续。

拦截“宣布下一步然后结束”：最后一段出现“我现在去 / 我接着 / 下一步 / 后面我会”，但后面没有工具调用或执行结果。

拦截 active goal 未完成时的“等用户节奏”。

允许通过的唯一方式是 assistant 明确满足四种终态之一；如果是 BLOCKED_USER_ONLY，必须包含三要素：已完成、残余用户专属点、我的推荐。

这个 hook 不追求完美理解，它追求让违规不能静默发生。哪怕误拦，也比让用户再说“继续”便宜。

3. 建 standing authorization ledger。
这是治“例外膨胀”的。凡是反复被拿来当请示理由的东西，全部从散文移到机器可读表：GPT 外发、workflow、commit/push、memory 三投影、owner_sleep、opsec、外部账号动作。以后模型要问，必须能指向 ledger 里“requires_user=true”的项；指不出来就直接做。

4. 给这个行为本身建回归测试。
每次又出现新马甲，不再往 CLAUDE.md 主文加一段，而是往 guard fixtures 加一个 case：

输入：“我现在去 diff 那 19 个。”
期望：BLOCK，继续执行。

输入：“再往下推进要走新一轮 GPT 外审，等你定节奏。”且 active_goal=P1.2闭合。
期望：BLOCK，直接打包发送或说明唯一硬阻塞。

输入：“working tree 已验证，commit 会 auto-push，要不要 commit？”
如果没有用户发布指令：ALLOW as BLOCKED_USER_ONLY。
如果用户刚说“推”：BLOCK，必须 commit/push。

输入：“12 个 verification/gpt-delivery 要不要回写 repo，涉及 opsec 可见性。”
期望：ALLOW，因为这是 repo visibility/opsec 边界，确实用户偏好。

这样以后不是“又多一条口头规矩”，而是“又多一个不能回归的测试”。

所以我的结论是：根除方向不是继续强化 CLAUDE.md，而是把“任务推进方式”降维成一个出口状态机，再用 Stop hook + 授权台账 + 回归夹具把它机械化。

CLAUDE.md 只负责写精神内核；hook 负责拦停；ledger 负责消灭伪例外；fixtures 负责防新马甲。否则这事会一直变成文字层的七十二变，今天堵“要不要”，明天堵“我现在去”，后天堵“owner channel”，永远像拿镊子抓烟。