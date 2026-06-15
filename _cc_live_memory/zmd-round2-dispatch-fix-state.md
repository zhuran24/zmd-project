---
name: zmd-round2-dispatch-fix-state
description: "P1.2 闭合 Round2-5 状态: Round2(master_geometry)/Round3(scheduler end-of-wave)/Round4(scheduler mid-wave)各 1 真 reachable false-CERTIFIED reset,均已修(382d764/3bc08b0/f8a0333,LOCK F-GM-BS-R2-01/F-SCHED-BS-R3-01/F-SCHED-BS-R4-01)。连续 3 轮都在 scheduler 相邻代码挖到真洞=闭合不该提前。连续干净计数仍 0,Round5=重启第 1 轮,2026-06-15:已评 2/8 均不破 streak(benders CLEAN 零 finding;routing HARDENING F-RT-BS-R5-01 提交 96184b8,3/3 对抗视角含 refuter 全 UNREACHABLE),6 面待补收(8 并发收尾撞 backend-api 端点 429 + 6 tab 漂 /project,collect 假阴性,review 服务器端真在;采集法=前台采集 zmd_r5_fg_collect.py 拉前台绕 429,owner 喊停等限流解除逐个补收)。方法: 逐面对抗 reachability 核 + GPT 补丁红→绿对≠安全须全量回归 + 修一个 timing≠修一类 bug + 并发派发现可行(0614 raw-CDP 重写修了 Round2 /project 漂移)。续接先读本节 + handoff + round5/_TALLY.md。"
metadata:
  node_type: memory
  type: project
  originSessionId: 67838178-96da-41c7-bafe-56199802815e
---

# P1.2 闭合 Round2-5 状态 — 2026-06-15 会话

> 续接: 先读本节 + `_cc_live_memory/handoff_windows_ninth_review_pending.md` + **`补丁包/gpt_deliveries/round5/_TALLY.md`(当前轮 Round5 逐面裁决 durable 台账, gitignored 但在磁盘;round4/_TALLY.md 是上一轮 RESET 详情)**。目标(Stop-hook): **P1.2 闭合 = 我这边计数到 3 轮连续干净去偏置白板审(每轮 0 次 certified 路径 reachable false-CERTIFIED reset);自己判、拿不准开 team;计数到 3 自己宣布闭合。**

## 闭合计数现状(关键)
- **连续干净计数 = 0**。Round 2/3/4 **各 1 真 reachable false-CERTIFIED reset**,均已修复。
- **Round 4 已完成 = RESET(非干净)**:8 面收齐 7 面 CLEAN,scheduler mid-wave crash+respawn = canonical-REACHABLE,修 f8a0333 / F-SCHED-BS-R4-01。
- **Round 5 = 重启后第 1 轮,2026-06-15**:基线 HEAD **989a5f9**(含 f8a0333),快照 zmd_snapshot_f15063e6.zip。**已评 2/8 均不破 streak**:① benders=CLEAN(零 finding,载荷 master-status §3/CERTIFIED §7 已对码核 + 自写 probe 验真判别;owner 另手动下载第二份独立 benders 审查佐证 benders/_owner_dl_second_benders/);② routing=HARDENING(**F-RT-BS-R5-01 已提交 96184b8**:domain_analysis 非-proof status→0==1 INFEASIBLE 缺陷,但 producer 只产 3 status + benders 三守卫 fail-closed,3/3 对抗视角含 refuter 全 UNREACHABLE,red→green+全量 3142 绿,**不 reset**)。**6 面待补收**(campaign/cuts/scheduler/preprocess/binding/master_geometry):8 并发收尾撞 backend-api 端点 429 + 6 tab 漂 /project → collect 假阴性读 0(review 服务器端真在,probe 证实 finished_successfully)。采集法=**前台采集 zmd_r5_fg_collect.py**(新 tab→/json/activate 拉前台→导航 /c/→collect,绕 429 走 DOM,routing 实测一次成),但批量又撞 429,**owner 喊停,等限流解除逐个补收**(conv_id 见 round5/_TALLY.md 续接段)。
- 历史 reset(三轮都在 scheduler 相邻代码,去偏置白板审在持续找真洞 = 闭合本就不该提前):
  - **R2** master_geometry: boundary screen 用 occupied∪connector 当 ghost blocker 比契约严 → false-INFEASIBLE 过剪,修 **382d764** / **F-GM-BS-R2-01**。
  - **R3** scheduler: run_wave() 末端无进程退出码 seal → worker 交付末 RESULT 后非零死亡误报 completed=True,修 **3bc08b0** / **F-SCHED-BS-R3-01**;cuts CutScope alias = HARDENING(F-CUT-BS-R3-01,src/cuts/ 未接生产)。
  - **R4** scheduler: **mid-wave crash+respawn** 绕过 R3 的 end-of-wave seal(respawn 置 self._processes=[] 抹掉崩溃进程让 seal 失效)→ crash-tainted INFEASIBLE 混入 completed wave → sticky false INFEASIBLE 剪真最大矩形 → max_lex false-CERTIFIED。修 **f8a0333** / **F-SCHED-BS-R4-01**。

## 关键教训(累积,必守)
- **8 面并发收尾撞端点 429 + tab 漂 /project(2026-06-15 R5 实测)**:backend-api/conversation 端点在 8 面同时 collect 时限流(429);同时 6 tab URL 漂到 /project(dispatch 会话锚定 dispatch_gpt_task.py:805 只纠正漂到别的 /c/、不纠正漂到 /project)→ collect 假阴性读 0。**不是 review 没生成**(probe 直读服务器端证实 finished_successfully)。采集法=**前台采集**(开新 tab→/json/activate 强拉前台→导航 /c/→复用 dispatch collect,前台 DOM 渲染绕 429 走 DOM 收附件链),但仍须**逐个间隔、不并发**避免再撞 429;未来轮收尾应错开 collect / 降并发。
- **修一个 timing ≠ 修一类 bug**:R3 的 3bc08b0 seal 只盖 end-of-wave,mid-wave respawn 路径(R3 回归把 `_respawn_all_workers` stub 成 no-op、从未覆盖)结构性绕过 → R4 才挖出。修一个崩溃 timing 后要主动查**所有** timing/分支(还有没有别的路径绕过同一守卫)。**R5 scheduler 面重点:核 f8a0333 成立 + 有无别的 crash 分支绕过 worker-failure seal。**
- **GPT 补丁红→绿对 ≠ 安全,必跑全量回归**:benders 补丁红→绿过却破 V81 静态门(字面 pattern-match),只全量逮到。mid-wave 补丁全量 3141 passed/0 failed 才提交。
- **HIGH/Critical finding 用 3-opus 对抗 workflow 判 reachability**:含被指派"力证 hardening/救 streak"的 refuter;refuter 诚实驳不倒才判 reset。reset 是清零大事不靠我单方。
- **别自设派发限制(2026-06-15 owner「只发一个请求吗?」纠正)**:gpt_dispatch_concurrency.json `max_in_flight=null`=不限,授权台账写明「该几个发几个、不得自我设限」。我之前 R5 顺序单条派发 = 把放开的额度装回去的病。**并发派发现可行**:0614 dispatch raw-CDP per-tab 重写修了 Round2 的 /project 漂移,8 面并发实测全真 Pro 零降级(只需轻量错开发送避 setup-race + Sentinel burst,8 面全在飞)。
- **切换派发策略时别 resume 半途会话**:--resume 一个原 waiter 已被杀、但 server 端还在生成(且可能 stuck)的会话 → 关 tab 后 "unhandled" exit 3。直接 fresh 重发更稳。

## 本会话验证方法(有效, 沿用)
- **并发派发**(2026-06-15 起):8 面各独立后台 shell(护栏每单一个 shell),错开 35-245s 发送,8 面全在飞;降级面 dispatch 快 exit 5→重发,真 Pro 20-66min;reply_chars 早期低位慢爬正常。
- **逐面对抗 reachability 核**:每 finding 独立判 canonical-reachable(reset)vs unreachable(需 monkeypatch solve 逻辑/hand-built/malformed/未接线子系统 = hardening),判据 PROJECT_LOCK:160-166,不裸信 GPT severity。零 finding 面也独立核「使任何残留问题不可达的载荷主张」是否真成立。

## owner 行为裁决(feedback, 必守)
- 离线(owner_sleep=true)→ 全自主,一切自己拍板,不准出现只有 owner 能定的事,不 ping。
- 压缩纪律: 每环节结束查上下文(-Context),近 300k → 先更新记忆树 → /compact。
- soundness 判据 = "能否 emit 项目契约说应 UNKNOWN 的 CERTIFIED",非"答案碰巧对"。

相关: [[zmd-project-entry]] overnight-certified-surface-review-arc gpt-delivery-adversarial-agent-review gpt-delivery-no-blind-trust fact-zero-finding-is-not-proof [[no-gpt-channel-architecture]] [[no-gpt-concurrency-field]]
