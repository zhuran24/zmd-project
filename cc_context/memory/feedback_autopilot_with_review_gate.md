---
name: autopilot-with-review-gate
description: 用户明确授权 autopilot 升级到 src 改动级别 + 自动 commit；前提是每次必须有审查兜底（preflight + pytest + 自审）
type: feedback
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

用户在 Endfield 项目（终末地求解器）已经明确升级 autopilot 授权：**可以直接动 src 代码 + commit，不需要等用户回来批准**。**前提是每次都走审查闭环**——不是给"砍审查"的授权。

**Why:** 用户 2026-05-08 直接说："等下你没必要等我回来再开干，毕竟有审查，你可以直接放开手脚"。背景：之前 session 早期我把"用户睡觉"当作"不能动 src 代码 + 不能 commit"，导致每次都要等 explicit 批准、loop 浪费在文档级小动作上。用户纠正：项目有完整的审查机制（pre-commit hook 跑 preflight gate + 核心守卫测试子集 + 我可以手动跑全 pytest），所以不需要把用户当 commit 守门员。

**How to apply:**

- **可以直接做的**（不再等用户批准）：
  - 改 src 代码（master_model / cp_sat_worker_config / 测试）
  - commit（preflight hook 自动审查；如果不过自然 fail）
  - 写新文档 / 更新路线图 / 维护 memory
  - 跑实验（不破坏 checkpoint 的 dry-run / short campaign）
- **每次"开干"必须的审查闭环**（不能跳过）：
  1. 改之前自审：当前任务是否触及 PROJECT_LOCK Forbidden Changes？
  2. 改之后跑测试：相关 unit test 必跑；如果改了 vendor 或 master 入口，跑全 pytest（5-6min）
  3. commit 之前 preflight gate 自动跑（hook）；如果失败先调查再修
  4. commit message 要诚实标明改了什么 + 为什么
- **仍需明确批准的**（destructive / shared 影响）：
  - git push（除非用户已经在某个上下文里说"push"）
  - 删除文件 / branch / 大块代码（即使是 Codex 时代遗留的，先报告再删）
  - 跑 168h production campaign（巨大资源消耗）
  - 改 PROJECT_LOCK / canonical_rules.json（exact 边界变更）
- **autopilot 失败模式 + 防御**：
  - 误判"无活可干" → 实际还有 P0 落地工作（这个 session 早期犯过）
  - 跳过审查直接 commit → preflight hook 兜底，但仍要主动跑相关 test
  - 误把用户睡觉当"等批准" → 用户已明确说不必等
- **如果 audit / pytest / preflight 失败**：
  - 不要硬 commit。诚实报告 + 调查 root cause + 修
  - 不要 --no-verify 或 -c commit.gpgsign=false 绕过

**核心精神**：用户信任审查机制 + 信任我的判断；我不需要把用户当瓶颈。但"放开手脚"不等于"砍审查"——它等于"审查闭环我自己跑完，不要每个 commit 都问用户"。

**调度策略：尊重用户的明确选择，不要"自作主张优化"**。用户 2026-05-08 在另一处明确说"以防万一你还是不要调心跳调度了，固定 1min 吧"——这是 explicit 指令，**不能后续因为"audit 饱和"或"cache 优化"自作主张切到 ScheduleWakeup dynamic 模式**。如果用户想 dynamic 会自己 /loop 重开。我犯过这个错（同 session 内反复在 cron 和 ScheduleWakeup 间切换），用户后来反问"心跳怎么没了"和"心跳不是刚才说要改成一分钟"两次纠正。**调度选择属于用户偏好，不属于"放开手脚"范围**。

**ROI 排序自主权：你能自己按 ROI/风险/解锁成本/收益排序，不要每件都问用户**。用户 2026-05-08 直接说："其实你已经自己能排了不是吗，我来我也是按照 ROI / 风险 / 解锁成本/收益什么的来排的，就不太能理解你为什么需要我拍板，至于时间，这些东西它都是要做的呀，没有什么是可以不做的"。

意思：
- **所有优化都要做（feedback_optimization_strategy 已记），先后顺序由 ROI 决定**——这不需要用户拍板
- "工时大"不是"做不做"的瓶颈，是"先后顺序"的输入。"5-7 day 投资"不是阻碍，是路径
- 我把"等用户决策"当默认是错的——session 早期把"audit 饱和"当"无活"，后来又把"工时账"当"瓶颈"，本质都是不愿意承担"自己排序自己做"的责任
- 按 ROI 序自动推进，遇到真正阻塞（外部依赖如 paper access）才报告

**真需要 escalate 时必须给具体论证，不要说"风险大"**：用户同一回合接着说："当你认为需要我来拍板的时候，你需要给出一个论证合理的理由，而不是说这个风险比较大所以需要我拍板这种经验性的判断"。

正面 escalation 例子：
- ✅ "DFF 实施需要 Carlier-Clautiaux-Moukrim 2007 EJOR §3.2 公式精确读，paper 在 ScienceDirect 付费墙后(HTTP 403)，agent 蓝图含模糊 W'，没有公式 verify 我无法保证 LB 不会 over-tight 切掉可行解破坏 certified_exact"——具体 + 引用 + 不可绕过
- ✅ "远程机分布式需要机 B 规格才能决定能跑 master 还是只能 subproblem batch；OS / GPU / 内存数据我无法自己获取"——外部信息依赖
- ❌ "改造 5 风险大需要你拍板"——经验判断，没具体论证
- ❌ "工时投入大需要你决策"——所有优化都要做，工时不是决策点

**底层精神**：用户雇我是来做事的，不是来当**他的 router**把所有决策反弹回去。能 audit 就 audit，能排序就排序，能落地就落地。真不能（外部依赖 / 物理约束）才 escalate。

## 链 (补连 2026-06-01)
- keep-review-process-light(已归档) — 流程轻量
- [[lazy-mode]] — 同 root
