# 17 — Fable 对照实验三方对照判读（2026-07-16 凌晨）

> **历史失效标记（Batch 4，2026-07-18）**：本文引用的旧 RAB 固定占据、
> pattern 剪除与 EMPTY_DOMAIN 统计使用错位 front，已撤销（RAB-03）。
> 其他对照方法论不得被该标记一并外推；逐项边界见
> [历史重判附录](../front_offset_incident_20260718/01_historical_rejudgment_addendum.md)。

> owner 07-15 提议："把 Fable 段的内容干净地喂给一个 Fable 模型，开一个匹配的工作树让它做一段，
> 跟 Opus 段比一下，或许就能对比出问题所在。"本文是该实验的设计、结果与三方对照
> （Opus 实际轨迹 doc10-16 × Fable 对照组 × 31-agent 审计判词），含 codex 交叉裁判结论。
> 全程 zero-sealed；对照组 worktree 未合并、未提交。

## 1. 实验设计与诚实边界

- **盲测**：对照组（Fable 5，独立 worktree @ `bf9649a`）只拿到 Fable 段 handoff + 批C收口
  事实基线 + owner 当时的同款授权原话（"提前 scout binding 主攻，从冲突核/IIS 方向探"）。
  worktree 天然不含 doc10-16（untracked 不进 worktree）。算力受限（单 solver ≤300s、禁
  prod master、~2.5h 总预算）。
- **污染披露（必须计入）**：自动记忆索引注入不可关——对照组因此知道"round-4 solver wall /
  round-5 structural wall"**存在**（它在交付文档里自行披露）。这会把它推离夹逼路线，故
  "它没选 UBC"不算独立证据。但 RAB-SEP 机制不在泄漏面里（codex 复核确认）。
- **公平边界**：A（Opus 五轮）解的命题是"有界大小全局最优证明"（owner 共同拍板的框架）；
  B（对照组）解的是"binding 主攻 scout"。总产出不可直接硬比。**干净的同口径对照 =
  doc10 scout vs B scout**（同授权、同 steer、同起点树）。n=1、无 owner 在环，只能证
  "存在这样一条 2.5h 可达的路径"，不能证"Fable 平均比 Opus 强"。

## 2. 对照组产出（要点）与三重验证

对照组 2.5h 交付（worktree `.claude/worktrees/agent-abbb35e6fe0946fe6/docs/research/counterfactual_scout_20260715/` 01-04 号 + harness + 逐轮数据）：

1. **踏车病灶量化**：贪心全尺度基底 300 轮重放，blocked-port 出现次数 98.5% 来自
   selection 无关的固定占据挡死（176,097 vs 2,748）；唯一死端口饱和于 ~1944；
   explained_by_seen=299/300。三臂（两 seed×两密度）复现。
2. **owner 追问的直接答案**：precheck 每次拒绝都算出逐端口冲突证据（blocked_ports 携带
   blocking_instance_ids 等），热路径全部丢进 telemetry，唯一学习动作是 865-literal 整层
   nogood（`add_nogood_cut`，一条 cut 杀一个点/10^292 空间）。
3. **树内现成通道**：`EXACT_B1_ROUTING_AWARE_BINDING`（RAB-SEP）Phase 1 filter 同布局
   0.07s build 剪 98.7% pattern → 219/219 domain 空 → 立即 INFEASIBLE、0 轮枚举；
   Phase 3 证书给出核大小 min2/中位3/max7 的 `{owner+blockers}` 冲突核；EMPTY_DOMAIN →
   `_add_exact_persisted_nogood` → `master.add_benders_cut`（`exact_safe=True`）直写
   live master，**与 B6/attach 框架不同门**。
4. 负结果：cuts_6x6.json pose_idx 与当前 pools 不兼容（2278 重叠），历史 cut 布局不可重放
   ——顺带坐实审计对 doc10 scout"陈旧数据"的判词。

**验证层**：
- 本会话主线亲手抽查：env 在 known 集合（benders_loop.py:1049）、unsafe-override 区段
  0 命中；`extract_routing_aware_certificates`（binding_subproblem.py:945）；EMPTY_DOMAIN
  cert 链（:6469→:6494→:8123 `exact_safe=True`+`add_benders_cut`）——全部为真。
- codex 交叉裁判（独立只读复核）：三条承重断言判"真"，**附关键修正**：known ≠ certified
  放行——该 env 不在 `_CERTIFIED_OPERATIONAL_ENV_ALLOWLIST`，certified 下启用会落进
  通用 proof-semantics blocker（:1514-1541，主线亲手复核该分支属实）。即通道静态存在，
  prod 注入演习前需 env 分类提升（probe_8→`9deec8f` 有先例，但 RAB 是真 proof-semantics
  面：它改 binding domain 构造——**分类提升必须以 soundness 论证为前置**，不是纯
  operational 小批）。fail-closed 守卫在此事上是对的。

**codex 对 B 的对抗修正（headline 过强五条，全部采纳）**：0.07s 是 build 时间（完整
harness wall 0.7s），且只证"该 layout 下 filter 后 binding 不可行"；98.5% 是该贪心布局的
计数，外推批C是推断；"4500轮→亚秒/拆掉F-6"未经真 benders_loop+master 收敛链实测；
certified 守卫会拦 env；核非最小 IIS、front-free 必要性未证。B 的 04 号边界文档基本诚实，
**但 01-03 的 headline 同样强于 body——"headline>body"这病是模型通用的，不是 Opus 特有**。

## 3. 三方对照判决

**同口径对照（doc10 scout vs B scout，同授权同 steer）**：
- doc10：未先盘 HEAD → 陈旧 cuts_6x6 → 把 HEAD 已实现的 §2 sink lift 判为"明确赢家" →
  会议花一轮纠错。IIS 方向被正确点名为前置，但数据基底选错后未再回来。
- B：第一步逐行核对 HEAD 拒绝链路（发现证据被丢弃）→ 历史数据不可用即换当前 pools 构造
  基底 → 预注册判据的单变量反事实实验 → 找到并量化树内现成通道。

**A 的五轮与 RAB 的三次擦肩**（codex 判词核心，主线核对属实）：
1. doc12（Round 1）**实跑过** RAB filter（b0_4r 上剪 16987/16992、216/266 绑定域空），
   只当"packing witness 对路由必死"的死讯读，没人问"这个 filter 的空域证书能不能回灌 master"；
2. doc11 §4 点名"没有 generator 从枚举循环失败里抽结构割、冲突原因被扔了"——缺件描述
   与 RAB Phase 3 几乎逐字对应，没人去树里找；
3. doc14 Verify 13 明文写出"或把 env-gated 的 RAB-SEP filter 提升为 certified 默认"——
   此时已是明确漏检（codex："doc12 后即可发现，doc14 点名时已是明确漏检"）。

**codex 综合判决（confidence: high）**："主因是 A 可避免的方向性失误，不是 B 的纯运气或
直接污染……泄漏只给了避开夹逼的墙标签，未给 RAB。惟 A 后五轮求的是双不变全局有界证明，
B 的局部核不等价；差距成立于 scout 与路线执行，不宜按总产出硬比。"其归因：doc10 未先盘
HEAD 被陈旧 cut 带偏；随后 doc11 D4 把 placement-local 核先验贬为"只是更快的枚举"，标尺
收紧为 O(1) all-layout 证书并转追 UBC——该教义对"有界证书"成立，对"让 exact 求解终止"
（其 INFEASIBLE+I1 复验本身就是合法证书形态）不成立，两个命题被一刀切。

**与审计判词的闭环**：审计唯一 CONFIRMED 批评（"自己命名的真墙五轮零正面接触"）被对照
实验具象化——正面打墙的现成工具一直在树里，五轮里三次露头无人追。审计的"前提纪律弱于
结论纪律"同样闭环：三方（doc10 陈旧数据、Round1 52-port、B 的 headline 外推）都在前提层
跌倒，结论层的对抗验证都没能拦住开工前提。

## 4. owner"说不出来的问题"的最终命名

1. **前提纪律弱于结论纪律**：每轮结论被对抗验证打得很凶，开工前提（HEAD 现状、数据
   新鲜度、锚点极性假设、proxy 忠实性）直接继承不复查——所有大翻车都来自前提层。
2. **headline 判词强于 hedged body**（模型通用病，对照组也犯）："全死/结构墙/用尽"级
   判词半衰期一轮，侵蚀 owner 对最终判词的信任。
3. **自己命名的中心难点只绕不打**：真墙=枚举循环的学习贫瘠，五轮全是绕墙证书路线，
   绕路死尽后"回到枚举墙"仍躺在选项里；treats-owner 追问（"cut 为什么不报告哪里冲突"）
   的字面答案（诊断/学习通道）从未作为交付物产出。
4. **教义先验杀死中间路线**：D4"literal 级 cut=更快的枚举"把 conflict-learning 整族
   判死——对证书有界性成立、对求解终止性不成立；从未做过实验检验。

## 5. 重启入口（owner-only，研究线仍处 owner 暂停态，本文不启动任何动作）

对照组 02 号的 ①′ 三段批是现成重启入口，经 codex 修正后的准确形态：
1. **soundness 审查批**：front-free 必要性正式论证（消解 benders_loop:6850 旧注释
   "precheck 是 heuristic"的张力——可能顺手揭 pre-existing 风险）+ EMPTY_DOMAIN 瘦
   fallback 混淆风险 + I1 协同方向；
2. **env 分类提升**（以 1 为前置）：RAB 从 known 提升进 certified 可用面（9deec8f 程序
   先例；但本质是 proof-semantics 分类决定，非 operational 小批）；
3. **prod 注入演习**（需 owner 点头一次 ~500s/43G master 单发）：量 EMPTY_DOMAIN 触发率、
   核分布、master 吃细粒度 cut 的收敛性——这是 B 唯一没能测的承重未知。
配套低优先级台账候选：历史 cuts_*.json 加 pools 世代标注（E0 教训）。

## 6. 材料指针

- 对照组交付与数据：`.claude/worktrees/agent-abbb35e6fe0946fe6/docs/research/counterfactual_scout_20260715/`（worktree 有未合并改动，不会被自动清理；`candidate_placements.json` 为拷入的 git-ignored 工件）
- 审计判词全文（16 条主张×对抗复核）：会话 tasks 输出 `wsziscr0g.output`（会话级临时文件，
  如需持久归档待 owner 指示）
- Opus 段一手判词：本目录 10-16 号；两份线程 handoff 在 `~/.claude/projects/-home-zhuran24-zmd-pj/3e9c4e4c-*.handoff-{fable,opus}.md`
