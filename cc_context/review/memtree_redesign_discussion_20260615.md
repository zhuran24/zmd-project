# 记忆树重构 — 多代理讨论全记录(2026-06-15)

> 本文是一场 Agents Team 讨论的完整经过与内容。团队 = 2 个 Claude 成员 + 2 个 codex(GPT-5.5/xhigh)成员 + 1 个 Claude lead 综合。讨论对象 = 一个给 AI 跨会话协作连续性用的「记忆树/知识树」(markdown 知识库)的**重构**。随包附上的项目快照里含整颗记忆树(repo 侧 `cc_context/memory/` + 镜像 `_cc_live_memory/` + harness-only 节点快照 `cc_context/harness_memory_snapshot/`,以及若随附的 live harness 树副本)。

---

## 0. 背景:为什么要重构

这棵「逻辑一树」实际有 **5 个物理投影 + 1 个备份**:

1. `cc_context/memory/`(repo 内,~104 内容节点;snake 前缀 `feedback_/project_/reference_/fact_/user_/handoff_` + 一批 kebab 共维护节点;含手工维护的 `MEMORY.md` 索引)—— owner 手维护的协作记忆树。
2. `_cc_live_memory/`(repo 根,cc_context 的**逐字节镜像**)—— 为了让 GitHub 远程可见(harness 不入仓)。
3. **harness 召回树** `~/.claude/projects/<slug>/memory/`(~153 节点,全 kebab,含自己的 `MEMORY.md`)—— **这才是 Claude Code 的 auto-memory 运行时真正自动召回读的树**。召回机制 = 按每个节点 frontmatter 的 `description` 字段做语义匹配注入上下文,**不顺 wikilink 走**,且 `MEMORY.md` 有一个 **~24,576 字节的注入体积上限**(超了尾部条目静默掉出召回)。
4. `docs/subjects/`(6 个 subject 源)+ `PROJECT_SUBJECT_PROJECTIONS.json`(30 个投影)+ `sync_doc_subjects.py`(sha256 marker 双向同步)—— 文档单源多投影引擎。
5. `authoritative_numbers.json` + `gen_authoritative_numbers.py` —— 复用数字的单一来源。
- `cc_context/harness_memory_snapshot/`(49 节点)—— harness-only 节点的**手动** git 备份(`snapshot_harness_memory.py` 单向 harness→repo)。

实测出来的核心病(都有证据):

- **读写分家(最核心)**:AI 召回读 harness(kebab),owner 维护 cc_context(snake),两者**不是同一内容集**(仅 ~33 同名交集,~120 个 harness-only,~72 个 repo-only)。桥是单向手动 `sync_memory_to_harness.py --apply`(只投 snake 投影类、跳 `handoff_`)。owner 在 cc_context 写规则若不跑 sync,AI 召回侧根本读不到 —— 这就是「AI 不长记性」的结构根源(2026-06-14 体检曾发现 60+ 节点不在召回树、`CLAUDE.md` 里 wikilink 跨树跳空)。
- **MEMORY.md 顶到截断红线**:harness `MEMORY.md` 实测 24,195 / 24,576 字节,只剩 ~381 字节余量;加一条索引就把尾部条目静默挤出召回。
- **召回覆盖不全**:41%(63/152)harness 节点不在 `MEMORY.md` 平铺索引、藏在 3 个父索引节点的 wikilink 列表里;但召回**不顺 wikilink 走** → 这些节点(含大量干活铁律)只能靠自身 description 碰巧命中。
- **同步工具碎片化、无总闸**:5 个工具分居两目录各管一段;操作者要记一张「改 X 类→跑 Y」分流表(snake 类→`sync_memory`;docs subject→`sync_doc_subjects`;kebab 共维护→纯手动写三处;handoff→stamp 引擎),拿错命令静默漏同步。
- **harness-only 节点 repo 备份靠手动 snapshot**:实测两个节点(codex 子代理相关)改完一天没跑 snapshot → repo 备份落后整整一天、新节点完全没备份(harness 一丢就永久丢失)。
- **现状值无强制函数**:散文里嵌的计数 / URL / phase 名没机器保护,反复复发漂移。
- **失效链全 fail-soft**:唯一硬门禁(pre-push 的 `preflight_gate`)只扫 repo 树,**看不见 AI 真召回的 harness 树** → harness 投影漏同步 / harness 死链 / 三写漏一处全是 warn-only 或 CI skip。
- 附带:frontmatter 两套格式(132 个嵌套 `metadata:` vs 20 个旧根级 `type:`);harness slug 硬编码(同机 19 个近似 slug,有写错树风险);删 harness 节点留的悬空 wikilink 无任何自动 gate。

**不可改的硬约束**(设计必须在这之内):
- harness 的读取行为(固定读 `~/.claude/projects/<slug>/memory/`、按 description 语义注入、不读 wikilink、有体积上限)是 Claude Code **产品行为,改不了**;只能设计「往里放什么、怎么命名 / 组织 / 控制体积」。
- repo 有 CI gate + pre-push hook + **post-commit auto-push(commit 即发布远程,不可逆)**。
- 不碰 certified/exactness 证明源(项目的数学正确性边界);review count 由 owner 在 repo 外手动维护。

---

## 1. 团队构成与方法

| 成员 | 模型 | 透镜 |
|---|---|---|
| `arch` | Claude opus | 架构 / 第一性原理(大胆重设计) |
| `migrate` | Claude opus | 迁移与风险(对重,守住不能破的) |
| `gpt-eng` | GPT-5.5 / xhigh(经 codex) | 外部工程 / 自动化 / forcing-function |
| `gpt-red` | GPT-5.5 / xhigh(经 codex) | 红队 / 对抗 / 找静默失败模式 |

方法:**round 1 独立开场立场 → round 2 定向交叉批评(lead 当中继,成员互相看不到消息)→ round 3 补 slug 机制 → round 4 对 slug 机制做最终对抗验真**。

---

## 2. Round 1 — 四份开场立场

### 2.1 `arch`(架构 / 第一性原理):翻转真相源到 harness

核心主张:**真相源选错了。把 harness 树定为唯一真相源,repo 树降级为它的备份投影 —— 而不是反过来。**

第一性原理推导:
- 系统目的 = AI 跨会话不断片。唯一真正被读进 AI 上下文的,是 harness 树(按 description 召回)。repo 树 / `_cc_live_memory` 一行都不进 AI 召回。
- 当前架构把 owner 手维护的 repo 当「权威源」、harness 当「派生投影」,**方向是反的**:权威源不在被消费的路径上 → owner 写一条规则要手动跑 sync 才到达消费点 → 漏跑 = AI 读不到。这不是 bug,是**拓扑错误**。
- AI 在会话里天然写的就是 harness。所以「读」和「写」两个高频动作天然都落在 harness。把真相源放别处,等于让两个高频动作都跨一道手动桥。
- 现状坐实:harness 已 154 节点、repo 只 105、49 个 harness-only 节点(含 AI 自己积累的协作经验)在 repo 压根不存在,只靠手动 snapshot 备份。**真相事实上已经在 harness 了,文档却还假装 repo 是源 —— 名实背离。**

关键设计动作:① 翻转方向(harness=源,repo=镜像);② 砍掉 `_cc_live_memory` 第三份(两份逐字节镜像 = 两个漂移点零额外价值);③ `MEMORY.md` 改成从 frontmatter 全自动生成,按召回价值排序 + 硬性体积预算(把产品约束变成生成器的输入参数);④ 统一命名空间到 kebab,废 snake 前缀;⑤ 一个总闸命令 + 一道真校验 harness 的硬门禁。

自曝待打的点:harness 在 home 目录、不在 git 下 —— 把它当源 = 真相源不在版本控制里,崩溃 / 误删恢复全靠 harness→repo 镜像的及时性。

### 2.2 `migrate`(迁移与风险):这是活体器官移植,不是推倒重盖

读了真实脚本坐实并纠正了几个数字:节点数 harness 154 / repo 105 / `_cc_live` 105 / snapshot 50;两树文件名交集仅 32;repo 的 72 个 repo-only 全是 snake 投影类。**CI 硬 gate(`check_memory_tree.py`)真实拦的 9 项**:重复 name、未解析 wikilink、孤立节点、`MEMORY.md` 缺节点覆盖、fact→projection 契约、INSTANCE 槽平衡、stamp 引擎、`MEMORY.md` ≤24576B、`_cc_live` 镜像字节一致。**harness 同步 / harness↔repo drift 全是 warning 不 block**(owner 2026-06-15 明确降级);CI 无 harness → harness 相关 check 直接 skip。

核心主张:150+ 活节点 + 9 项活 CI block + commit=auto-push 不可逆 + owner 手维护肌肉记忆。**红线:任何一步都不能让 `check_memory_tree.py` 变红,不能让 owner 某天打开发现熟悉的文件没了或路径变了。**

「特性不是 bug」清单(砍之前必须想清替代):`_cc_live_memory` 镜像是为远程可见(harness 不入仓),是 CI block 项不是冗余;harness/repo 物理分家是产品行为强加的物理必然,「合并成一棵」在召回路径不可改前提下做不到;单向 repo→harness sync 是「反向会少覆多删数据」吃过亏后的正确决定;harness 同步降为 warning 是 owner 的 deliberate call;索引父节点不平铺是绕 24KB 截断线的主动设计。

分阶段迁移骨架:P0 基线冻结 → P1 纯加固(不改结构)→ P2 单点结构改造(一次一个轴)→ P3 合并 / 总闸类(最高风险,放最后,先并行观察期对齐再切换)。

### 2.3 `gpt-red`(红队)Round 1:重塑框架 —— harness 是原生写入源

**总判断:这些方案会静默翻车的根因不是同步脚本写得不够多,而是模型错了 —— harness 不是普通派生目录,它有原生写入。** 只要 AI 会话还能直接写 harness,就必须把它当**并列输入源**;只要召回不读 wikilink,就不能把父索引当召回保证;只要 commit 自动 push,就不能让生成器自动提交未经人工审的状态。

- **(a) repo 单一源→生成 harness:会翻车。** AI 会话里新记忆天然写进 harness,不先合并就重生成 = 拿旧 repo 覆盖新运行时记忆。双写入源(人改 repo / AI 改 harness)撞同一节点时,任何单向同步都不是 merge、是随机丢一边。**关键:「同步成功 + gate 绿 + 节点数对」全部正常,只有「信息内容已消失」没有检测器。** 破解门槛 = 三方同步(`last_synced_base` + repo 当前 + harness 当前 做 diff,两边都改就停下报冲突),harness-only 节点默认不可删,重生成只写明确标记的派生块。
- **(b) 靠 wikilink/父索引组织:注定「组织了但召回不到」。** 链接健康检查显示「无死链」≠「会召回」。组织越漂亮越危险,因为给人错觉。
- **(c) 自动重生成 + 自动 commit:高危。** commit=auto-push,远程会出现没人工审过的版本;hook 改文件没 `git add` 会本地/远程不一致;自动 `git add` 生成物 = 错误结果被固化到远程历史。
- **(d) 自动裁剪 `MEMORY.md` 绕 24KB:把「谁重要」交给脚本猜,必然静默降级。** 按时间裁会挤掉稳定但要命的红线;按链接数裁会误杀「出事才需要」的低链接节点。
- **(e) slug 漂移:最容易「脚本成功但写错树」。** 错误目标不是不存在,而是「存在但不是当前运行时」。

### 2.4 `gpt-eng`(工程 / forcing-function)Round 1:repo=源,harness=部署目标

**核心判断:把 live harness 当「部署目标」,不要当源;把 repo 里某个目录当唯一可审计源;CI 只校验 repo 内可复现的投影。** 否则 CI 永远看不见 `~/.claude/...`、只能假装看见。

可搬的成熟模式:① generated-files-marked-DO-NOT-EDIT(带 source + sha256 marker);② 单入口编排(一个 `sync_knowledge.py --sync/--check` 串所有子脚本);③ CI 重新生成再比较(`git diff --exit-code`,stale 即红);④ checksum/manifest lock;⑤ 声明式 registry;⑥ absorb/import 流程;⑦ schema gate(description 质量进 gate);⑧ 体积预算 gate(`MEMORY.md` 生成时检查 <24576)。

总闸设计:源 = `cc_context/memory/` + `docs/subjects/` + `authoritative_numbers.json` + 投影注册表;生成物(不可手改)= `_cc_live_memory/` + **repo 内新建 `cc_context/harness_memory_projection/`**(repo 内的「期望 harness 树」,CI 可见可 diff)+ doc 投影块 + 数字 claim。校验位置:pre-commit 阻断 stale;pre-push 校验本机 live harness(关键,因 auto-push);CI 只校验 repo 内可复现物。harness 不在 repo 的处理:live harness 是 deploy target;live 多出的节点视为「未导入源的危险数据」→ 硬错误逼 `--import-harness`。

---

## 3. Round 2 — 交叉批评与收敛

### 3.1 `arch` R2:认输并合成 —— 接 gpt-eng 骨架 + 接 gpt-red 的双写检测

- **(1) gpt-eng 在「真相进 git」上赢了。** 「harness=源」意味着 CI 永远只能假装看见;gpt-eng 的 repo-internal `harness_memory_projection/` 让 CI 真能校验期望态、pre-push 校验本机部署。**撤回「harness 必须当源」。**
- **(2) gpt-red 对,但 gpt-eng 同样没解根。** import 之后双写撞同一节点仍是单向静默丢一边。`arch` 实测了 `git log`:repo `cc_context/memory` **257 次改动 100% 是 owner 单账号、commit message 全是 `chore(memory)` 自动化口吻** → 强烈提示「repo 手改」其实多是「AI 写 harness→镜像→提交」,**实践中近似单写入源**(但不能当设计保证)。
- 合成:接 gpt-eng 骨架 + 把「单向同步」升级为「带冲突检测的单向同步」(存 last-synced content-hash,三方比较,只一边变→安全传播,两边都变→硬错误停下等裁决,= 退化版 3-way「撞了就喊停」)+ 约定单一写入入口降低冲突频率。
- 留给 owner 的 crux:愿不愿接受「唯一写入入口 = harness/会话,repo 永远只读生成」?

### 3.2 `migrate` R2:B 可达,A 不可达

- **架构 B(repo=源)远比 A 可达;A 基本不可达。** A 把 harness 当源,但 harness 不入 git、CI 看不见、无版本史、auto-push 推不到 → 废掉现有 9 项 CI block 的全部前提 = **记忆树脱离版本控制保护**。砍 `_cc_live` 更是删唯一远程可见性。
- **`MEMORY.md` 自动生成不撞红线#3**:它是派生索引、不是 owner 写知识的内容节点。但有前提:自动生成要能复现 owner 当前的分组/信息;且 owner 手抄润色的 description 措辞会被 frontmatter 字段替代,这要 owner 拍板;DO-NOT-EDIT 应渐进(先生成 `MEMORY.generated.md` diff 给 owner 看 N 次满意再切)。
- **三方 merge 当前是过度工程**:不是真双写(72 个投影类 owner 只在 repo 改;真双写只有 30 个 kebab 共维护节点 + 一次性 `--import-harness`)。轻量替代:30 个升 pre-push 软 block;import 是一次性、人肉看 diff。**别为不存在的并发建常驻三方 merge 引擎。**
- A/B 可迁移交集 P0–P3:P0 基线冻结 + 全量 snapshot + tag;P1 description schema gate(先 warn)+ 单入口 `sync_knowledge.py`(只编排不改语义);P2 新建 `harness_memory_projection/` + CI diff;P3 `MEMORY.md` 自动生成(并行观察期 + owner 拍板)。**不进交集的**:砍 `_cc_live`、harness 当唯一源、常驻三方 merge。

### 3.3 `gpt-red` R2:验真 gpt-eng 的具体方案,挖出 3 个洞

- **(1) deploy 覆盖 AI live 新写:部分堵死,部分仍静默失败。** 新建节点会 hard error;但**改已有节点的 description**(AI 在 live 改 `certified-redlines.md` 的 description 让召回更准)不算 harness-only、不触发 import → 被 repo 期望态覆盖,manifest 还报绿。
- **(2) description_sha256 抓不到语义退化:** 只抓字节不一致。owner 把 description 从含 `auto-push` 关键词改成模糊措辞 → hash 更新、CI 绿,但召回退化、零信号。
- **(3) slug 漂移写错树报绿:没堵死。** 硬编码 slug 是死穴;`generated_harness_path` 只证明「写到了 manifest 指定路径」,不证明「写到了 Claude 此刻真读的路径」。
- **(4) harness-only 硬错误:护栏对,但缺分级会沦为噪音→被 allowlist 绕过→静默丢数据。**
- 3 个必补:① deploy 保守合并(冲突前零写入)② 召回回归测试集(hash 之外的语义层)③ active slug 运行时确认。

### 3.4 `gpt-eng` R2:接受批评,精化机制

- **模型修正:这不是「一个源+多个生成物」,而是 repo 与 harness 两个可写副本 + 一个同步基线。**
- **(1) 三方吸收:** 按 frontmatter.name 识别同一节点;新增 `cc_context/knowledge/memory_sync/`(manifest + base/ 快照 + conflicts/ 落盘);6 种情况判定表(只一边变→传播;两边都变且不同→停下写 conflict bundle;harness 新增→pending 队列;repo 删 harness 未删→不自动删生成 deletion candidate)。冲突走显式 `--resolve --take repo/harness/--manual`。
- **(2) harness extra node 改 pending 队列:** 自动 harvest 到 `cc_context/memory_pending/`,pending 存在**不报红**只提示;只有「没备份/冲突/疑似 secret/pending stale」才红;删除走 tombstone;promotion 单独做。pre-commit 安全自动 harvest + secret scan。
- **(3) description 退化检测三类 gate:** ① 硬格式 lint(禁「见正文/同上/TODO」,要求 30-180 字 + 主题词 + 具体触发词)② `body_basis_sha256` freshness(正文改了但 description 没改→红;reviewed_at 超 180 天→红)③ **本地 BM25 召回 smoke test**(给重要节点加触发 query,要求目标节点排进 top-5/10,`description: 见正文` 直接失败)。

---

## 4. Round 3 — slug 机制(gpt-eng 设计)

**核心修正:slug 不能再是配置常量,必须是一次运行里先解析出的 runtime target set。manifest 只记录「上次写到哪」,不能证明「Claude 现在读哪」。**

- 新建 `cc_context/tools/harness_resolver.py`,返回带证据的对象(不是单字符串)。
- **证据强度排序**:① 强 = 扫 `~/.claude/projects/*/*.jsonl` 找最近活动 session,解析 jsonl 里的 cwd/projectRoot 字段,精确 == 当前 repo root(`git rev-parse`)才算权威;② 中 = `.claude.json` 项目映射(仅交叉核对,可能 stale);③ 弱 = cwd 反推 slug(已证明会有任务后缀,不能当权威);④ 显式 `ZMD_ACTIVE_HARNESS_DIR` override。
- **多候选判据**:0 强候选→pre-push 红(只允许 repo-internal check,不声称 live 同步);1 强→用它(哪怕 ≠ 旧硬编码,打印「legacy slug ignored」);多强 + check/deploy→对全部 active targets 执行;多强 + merge/import→报红让人指定。活跃窗口:jsonl mtime ≤6h=active,6h-7d=stale,>7d=archive。
- **单一函数 + 一次 run 只 resolve 一次**:结果写 `.artifacts/memory_sync/resolution-<run_id>.json`;deploy 和 check 都只吃同一个 targets-file + 校验同一 `resolution_sha256`。代码级测试 `test_no_hardcoded_harness_slug.py` 禁止字面量 slug。
- 换机:repo root 来自 `git rev-parse`、projects 根可 `CLAUDE_PROJECTS_DIR` 覆盖、路径 normalize;首次无 jsonl 给 `--bind-harness` bootstrap 写本机私有 `.git/info/zmd_active_harness.json`(不进 git)。

---

## 5. Round 4 — slug 机制最终对抗验真(gpt-red)

**总结论:slug 常量洞被大幅缩小,但没堵死。最大新风险不是「找不到 slug」,而是「找到太多强 slug 后对全部 deploy」—— 在并发会话真实存在时,这把部署动作从「当前会话目标」扩大成「所有活跃同 repo 会话目标」,本身就是跨会话写入。**

| 攻击角度 | 结论 |
|---|---|
| 并发会话多强候选全部 deploy | **未堵死,新增跨会话污染**:把本会话 projection 写进另一个活跃会话正在用/正在改的 harness,盖掉人家会话内刚写的记忆 |
| jsonl cwd 字段不稳定 | 不会静默写错,但 gate 过严→人为 `ZMD_SKIP` 绕过→退化成没 gate(比硬编码更糟) |
| basename 碰撞 / 路径归一化 | 完整路径匹配基本堵住 basename 碰撞;但 Windows realpath 归一化有残留洞(junction/symlink/8.3 短路径/subst/UNC) |
| resolve 与 push 之间 TOCTOU | **未堵死**:`resolution_sha256` 只防 deploy/check 内部不一致,不保证 targets 在执行时仍反映真实世界 |

3 个必改:① 多强候选时 deploy 默认红或只写当前绑定 target,不「对全部 active 执行」;② resolver 必须有诊断输出(字段缺失原因可见),防黑箱→强制绕过;③ Windows 路径归一化走 realpath/volume-inode 而非字符串;(+ TOCTOU:resolve 后结束前重扫 active set,变了则红;每个 live 写入前文件锁 + per-file CAS)。

---

## 6. 收敛结论 — 最终设计

| 部件 | 方案 |
|---|---|
| **源** | repo `cc_context/memory/` 唯一可审计源(owner 现有节点零迁移);**保留 `_cc_live_memory`**(远程可见,是 CI block 项);新增 repo 内 `cc_context/harness_memory_projection/`(CI 可见的 harness 期望态,重生成再 diff) |
| **双写调和** | 新 harness 节点→`memory_pending/` 收容队列(不报红);改已有节点→基线快照三方撞停(不静默覆盖) |
| **总闸** | 单入口 `sync_knowledge.py --sync/--check` 包住所有现有子脚本(消灭「改 X 跑 Y」碎片化) |
| **MEMORY.md** | 自动生成(DO-NOT-EDIT)+ 硬 24KB 预算报红(不静默裁剪)+ 显式优先级标记;渐进切换(先 `MEMORY.generated.md` diff 给 owner) |
| **description 质量** | 格式 lint + `body_basis_sha` freshness + 本地 BM25 召回 smoke test |
| **slug / harness 写入(最危险)** | runtime resolver(证据排序、一次解析、单一函数、代码级禁硬编码)+ red 的 3 必改(只写绑定 target / 诊断输出 / realpath 归一 / TOCTOU 重扫 + CAS) |

迁移路径(A/B 通用、不破 9 gate、不 auto-push 中间态):**P0** 基线冻结 + 全量 snapshot + git tag → **P1** 单入口 `sync_knowledge.py`(只编排)+ description schema gate(先 warn)→ **P2** `harness_memory_projection/` + CI diff → **P3** `MEMORY.md` 自动生成(并行观察期 + owner 拍板)+ 基线冲突检测 + pending 队列 + slug 运行时确认。

---

## 7. 关键洞察:所有残留洞都集中在一个可避免的动作上

经 4 轮提案→验真,**剩余的洞 100% 集中在「repo 自动写回 live harness(deploy)」这一个动作**:跨会话污染、TOCTOU、Windows 路径地狱,根都在「自动往一个别的活进程正在读写的目录里写」。

这类洞不是「补丁能补掉」的 bug,是那个动作的本性 —— 并发写一个别人正在用的目录天生就是 race,红队再来几轮也只会找到新的 race,到不了「零洞的自动 deploy」。

**由此得出的设计修正:采用 harvest-only。** 让 AI 在会话里原生写 harness(它本来就这么干)、只做 harvest(live→repo 收容)+ repo 内 projection 给 CI 看,**永远不自动反写 live harness**。这一刀下去,上面整类洞全部消失(没有 deploy = 没有跨会话污染、没有 TOCTOU、不用解 Windows 路径)。剩下要建的(P0/P1/P2 + harvest + pending + description gate)是 repo 内的只读检查/编排/收容,**没有有意义的洞了**。

---

## 8. 待 owner 拍板的决策(lead 给的推荐)

1. **写入入口约定**:接受「唯一写入入口 = harness/会话,repo projection 永远只读生成」吗?(推荐:接受 —— 实测 repo 手改近乎不存在,接受后双写坍缩成单写,冲突检测只当保险。)→ **owner 已表态:接受。**
2. **MEMORY.md 措辞**:接受自动生成用 frontmatter description 替代手抄润色的索引措辞吗?(推荐:渐进切换。)→ **owner 已表态:接受。**
3. **harvest-only(取消自动 deploy 到 live harness)**:采纳吗?(推荐:采纳 —— 从根上去掉整类危险。)

---

## 9. 我们想问 GPT 的

以上是讨论的全部经过、内容和收敛结论。本 Project 文件区随附两个 zip:

- `zmd_v80_impl_full_20260615_single.zip`(sha256 `72ec34a80bfee3eefcbdc223d5a3a1dcd834118ed04912e3136bbd24e8f9c092`)= **整个项目** + repo 侧记忆树(`cc_context/memory/` + 逐字节镜像 `_cc_live_memory/` + harness-only 节点快照 `cc_context/harness_memory_snapshot/`)。(文件区里 `zmd_snapshot_72ec34a8.zip` 是同内容副本、`zmd_snapshot_f15063e6.zip` 是更旧快照,看本文件即可。)
- `harness_memory_tree_20260615.zip`(sha256 `e71ee109235e8125c7ee7f05dda2b1e2302a64a8c4a4d189194271912362c548`)= **AI 运行时真正召回读的那棵 live harness 树**的当前副本(154 个 .md,本讨论的真正主角)。

请解开这两个包、对照本讨论看完整现状(整个项目 + 整颗记忆树的两个物理面)。

**你怎么看?**
