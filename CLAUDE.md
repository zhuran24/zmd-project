# ZMD 研究树

Mode: `RESEARCH`。Branch: `research/main`。

这棵树拥有整个 ZMD 研究计划;零条件整层 campaign 是当前的进攻点,不是最终使命。

## 冷启动

先跑:`/home/zhuran24/zmd-pj/.venv/bin/python research_lab/tools/research_tree.py enter`

第一份活读物是 `/home/zhuran24/zmd-research/research_lab/STATE.txt`:一个当前端点、一个活问题、加上在途恢复句柄。跨树交接、owner 事项、跨会话外部作业才读 `/home/zhuran24/.claude/ops/zmd-pj/membrane/NOW.md`;普通 R0 工作留在本地,不进 O。

首次进树或目标层级变了,读 `research_lab/PROGRAM.txt`;STATE 之后按当前问题读 `.zmd-worktree-mode` 指的活跃 campaign;旧治理与历史只按需加载。

每个新会话、每次上下文压缩后,装载 `/zmd-method` 与 `/research-charter`——它们提供为什么与边界,装载后退到背景,不是逐实验自审清单。运行中何时必须停,由 memory 的 `REFLEX:RESEARCH-PAUSE` 与 `research_lab/ATTENTION_AND_REFLECTION.txt` 负责。当前押注只看 `/home/zhuran24/zmd-pj/docs/项目说明/30_research_charter.md` 末节。owner 原话档案在 `research_lab/METHOD_ORIGIN.txt`(方法)与 `research_lab/STANCE_ORIGIN.txt`(姿态),想回出发点的感觉时去翻。

CC 自动记忆绑在 `research_lab/CC_MEMORY.txt` 记录的研究专用目录,装稳定研究习惯,不装 campaign 状态;现在发生着什么,以 `STATE.txt` 与活跃 campaign 为准。

## 默认注意力

从问题出发:规则、资源账、死亡形状、构造结构、表示、层边界、最便宜的判别实验。现有模块、F1-F9 名字、当前层数与当前 cut 形式都是历史候选,不是公理。

普通发现不预载 `PROJECT_LOCK.md`、`docs/CURRENT.md`、台账或完整操作手册;要精确的当前权威、认证语义、晋级、发布、共享 Git 修复或某条具体操作契约时,再按需去读。

## 运行时停顿

方法论不是只在开场读。命中任一事件,先按 `research_lab/ATTENTION_AND_REFLECTION.txt` §3-4 做一屏反思脉冲,再开下一个实验:同一 skeleton/consumer/成功信号连续两次未推进最深正见证而准备开第三次;连续两次只涨知识账或机器账;UNKNOWN 后只想加时间、seed、profile、cut、atlas 或再套一层表示;已有正几何/见证/有限基底尚未送进更深 consumer 却准备再建抽象;预设停止条件、owner 回看或证据身份变化出现。

这不是写报告或反复盯着纲领。正常工作不自审;触发时一分钟内决定 CONTINUE、BRANCH/CONTROL 或 STOP/SWITCH。只有方向或活问题改变,才更新 `STATE.txt` 的 `Reflection checkpoint`。

## CodeGraph 优先

索引内的代码,CodeGraph MCP 是默认的第一件、也是反复用的工具,不是仪式性的一次查询。读代码路径或改代码前,`codegraph_explore` 传 `projectPath=/home/zhuran24/zmd-research`,点名具体文件与符号,看返回的调用路径和影响面;问题挪到别的代码面就再叫一次;返回的源码当已读。只有未索引材料、图没返回的细节、标了 stale 的文件才直接读。改完尊重 staleness 横幅或等自动同步。CodeGraph 给结构上下文;编译、测试、checker 和运行时证据仍然决定对错。派出去的席位同样适用:涉及本树代码的任务书明写 CodeGraph-first 并传 projectPath。

## 研究自由与真理纪律

猜想、启发式搜索、临时充分限制、替代模型、一次性原型、小反例,全都可以;标明身份和代价就行,别静默把它们变成必要条件。

UNKNOWN 不是不可行;失败的构造器不证明不存在;局部定理没有运输证明不禁止外部对象。保住前提与范围,但不要给日常出想法套审批仪式。

本树可以造候选定理、算法、表示、cut 形式、witness 和晋级 packet;它不发生产、认证、U/L 更新、耐久强状态、发布权或 owner 权——那些只走认证的证明链与闸门。

## 仓库角色

`/home/zhuran24/zmd-pj` 是历史材料树,保持只读;独立认证树在 `/home/zhuran24/zmd-certification`(`certification/main`)。

不把本分支整体合并进认证树;成熟工作靠紧凑 promotion packet 过去:精确 claim、前提、选中的 commits 或 diff、复现命令、对照、已知未知、请求效果。认证是新会话冷审。

## 工作节奏

让每个结果改变下一个问题。按所声称的效力(不是按文件路径)从 `research_lab/CHECKS.txt` 选最轻的诚实检查级(R0/R1/R2)。耐久研究改动用小而连贯的精确 pathspec 提交;日志、缓存、求解器 dump、临时模型、可再生工件放 `research_lab/local/`。

项目 Python 用 `/home/zhuran24/zmd-pj/.venv/bin/python`;这个轻量 worktree 有意不带虚拟环境副本。
