---
name: zmd-round2-dispatch-fix-state
index_summary: "P1.2: R2(master_geometry)/R3(scheduler end-of-wave)/R4(scheduler mid-wave)各1真reachable false-CERTIFIED reset均已修;R5=RESET(scheduler 两正交 reachable reset R5-01 GPT TOCTOU + R5-02 CC独立审计 persist 毒化,修 d2f2d50);**R6=第1个干净轮(8/8零reset,streak 0→1;benders HARDENING+补丁因type-1 over-reject否决,scheduler+campaign独立确认R5-01/R5-02守住),距闭合还需R7+R8两轮**;教训:封标志≠封类、零finding面≠无洞须CC独立全链审、修一timing≠修一类bug、GPT补丁红→绿≠安全须全量回归、别自设派发限制、拿派生/单点信号当结论(完成检测看ground truth+限流看429/可见消息,修于0c4832c)"
description: "P1.2 闭合 Round2-5 状态: Round2(master_geometry)/Round3(scheduler end-of-wave)/Round4(scheduler mid-wave)各 1 真 reachable false-CERTIFIED reset,均已修(382d764/3bc08b0/f8a0333,LOCK F-GM-BS-R2-01/F-SCHED-BS-R3-01/F-SCHED-BS-R4-01)。连续 3 轮都在 scheduler 相邻代码挖到真洞=闭合不该提前。连续干净计数仍 0,Round5=RESET(非干净):scheduler 面 2 个 reachable reset(F-SCHED-BS-R5-01 GPT success-path respawn TOCTOU + F-SCHED-BS-R5-02 CC 独立审计 preserve-persist),均修+全量 3143 绿,提交 d2f2d50。连续第三轮 R3/R4/R5 都在 scheduler 挖到真洞。已评 benders/campaign=CLEAN、routing=HARDENING、scheduler=RESET;余 4 面重收评估中(不改 RESET 裁决)。R6 为新干净 #1 候选轮。方法: 逐面对抗 reachability 核 + GPT 补丁红→绿对≠安全须全量回归 + 修一个 timing≠修一类 bug + 并发派发现可行(0614 raw-CDP 重写修了 Round2 /project 漂移)。续接先读本节 + handoff + round5/_TALLY.md。"
metadata:
  node_type: memory
  type: project
  originSessionId: 67838178-96da-41c7-bafe-56199802815e
---

# P1.2 闭合 Round2-5 状态 — 2026-06-15 会话

> 续接: 先读本节 + `_cc_live_memory/handoff_windows_ninth_review_pending.md` + **`补丁包/gpt_deliveries/round5/_TALLY.md`(当前轮 Round5 逐面裁决 durable 台账, gitignored 但在磁盘;round4/_TALLY.md 是上一轮 RESET 详情)**。目标(Stop-hook): **P1.2 闭合 = 我这边计数到 3 轮连续干净去偏置白板审(每轮 0 次 certified 路径 reachable false-CERTIFIED reset);自己判、拿不准开 team;计数到 3 自己宣布闭合。**

## 闭合计数现状(关键)
- **连续干净计数 = 1**(2026-06-15/16 起)。**Round 6 = 第 1 个干净轮**(R5 RESET 后)。**距闭合还需 R7、R8 两整轮 clean**(streak→3)。
- **Round 6 = CLEAN(8/8 面零 canonical-reachable false-CERTIFIED reset),基线 snapshot 72ec34a8 / HEAD 600f98c**:
  - benders = **HARDENING 不 reset**(F-BENDERS-RD-01: relaxed_disconnected consume 不验证据,与 front_blocked 不对称;但唯一 producer routing_subproblem.py:601 被 `if disconnected_commodities:` 守卫=结构上不可能发空证据,异常/fallback 只产 ERROR/feasible 非 relaxed_disconnected,nogood 本身不用证据内容仍 sound;GPT probe 靠 monkeypatch=reset 判据②③排除;主审+对抗 subagent 双 confirm UNREACHABLE)。**GPT 补丁否决**:校验要求每 entry 有 `components`,但真实 producer 的 **type-1 entry(L516 缺 source/sink 多 component)无 components** → 补丁误拒合法 type-1 = 可用性回归(实证 /tmp 验证)。
  - master_geometry/campaign/preprocess/binding/cuts/scheduler/routing = **零 soundness finding**。
  - **scheduler 正面 + campaign 侧面独立确认 R5-01(TOCTOU)/R5-02(crash-tainted INFEASIBLE sticky)修复守住**(scheduler §3.3 success-path rotation `fail_on_worker_shutdown_failure=True` + §3.4 `persist_strong_results=bool(effective_wave_completed)`)。
  - 逐面台账 durable: `补丁包/gpt_deliveries/round6/_TALLY.md` + `_CONV_MAP.md`(gitignored 在磁盘)。
  - 历史(Round 2/3/4/5 **均含真 reachable false-CERTIFIED reset**,均已修;R3/R4/R5 连续三轮在 scheduler 挖到真洞):
- **Round 4 已完成 = RESET(非干净)**:8 面收齐 7 面 CLEAN,scheduler mid-wave crash+respawn = canonical-REACHABLE,修 f8a0333 / F-SCHED-BS-R4-01。
- **Round 5 = RESET(非干净),2026-06-15**:基线 HEAD 989a5f9。**scheduler 面 2 个 reachable certified soundness reset → streak 维持 0**:① **F-SCHED-BS-R5-01**(GPT 发现, red→green 确认): success-path `_respawn_all_workers()` 擦进程前不查 exitcode → seal(619)非阻塞 poll 读 None、respawn join(632)reap 后非零却被擦 → completed=True(第三个 crash timing); ② **F-SCHED-BS-R5-02**(**CC 独立审计发现**, 验证阶梯第②线, 非 GPT review): R3/R4 封 completed=False 但保留崩溃波结果 → 消费侧 persist 保留的 INFEASIBLE 成 sticky strong(stop 前)→ resume 信任不复跑 → 毒化 frontier → 更小矩形 false-CERTIFIED, 无 backstop; 2-way 对抗辩论(检方+力证 hardening 的辩方)双双 REACHABLE_RESET high 辩方认输。两者交互(GPT patch 把 TOCTOU 导向 worker_process_failed 正落进 R5-02 毒化路径)→ 两个都修。均已修+全量 3143 绿+LOCK+**提交 d2f2d50**。已评面: benders=CLEAN(零 finding+probe 验真判别; owner 另下第二份 benders 佐证)、campaign=CLEAN(exact_campaign 持久化/resume/checkpoint 权威面彻底审)、routing=HARDENING(F-RT-BS-R5-01 提交 96184b8, 3/3 对抗 UNREACHABLE)、**scheduler=RESET**。余 cuts/preprocess/binding/master_geometry 重收评估中(不改 RESET 裁决)。**Round 5 收口=RESET → R6 为新干净 #1 候选轮**。采集法=前台采集 zmd_r5_fg_collect.py(新 tab→/json/activate 拉前台→导航 /c/→collect, 绕 429/漂移走 DOM; Edge CDP 9222 偶尔掉需等恢复)。
- 历史 reset(三轮都在 scheduler 相邻代码,去偏置白板审在持续找真洞 = 闭合本就不该提前):
  - **R2** master_geometry: boundary screen 用 occupied∪connector 当 ghost blocker 比契约严 → false-INFEASIBLE 过剪,修 **382d764** / **F-GM-BS-R2-01**。
  - **R3** scheduler: run_wave() 末端无进程退出码 seal → worker 交付末 RESULT 后非零死亡误报 completed=True,修 **3bc08b0** / **F-SCHED-BS-R3-01**;cuts CutScope alias = HARDENING(F-CUT-BS-R3-01,src/cuts/ 未接生产)。
  - **R4** scheduler: **mid-wave crash+respawn** 绕过 R3 的 end-of-wave seal(respawn 置 self._processes=[] 抹掉崩溃进程让 seal 失效)→ crash-tainted INFEASIBLE 混入 completed wave → sticky false INFEASIBLE 剪真最大矩形 → max_lex false-CERTIFIED。修 **f8a0333** / **F-SCHED-BS-R4-01**。
  - **R5** scheduler(**两个正交 reset**): ① success-path respawn TOCTOU(seal 非阻塞 poll 读 None、respawn join reap 后非零被擦)→ completed=True, F-SCHED-BS-R5-01(GPT 发现); ② R3/R4 保留崩溃波结果→消费侧 persist INFEASIBLE 成 sticky→resume 毒化→false-CERTIFIED, F-SCHED-BS-R5-02(CC 独立审计)。均修, 提交 **d2f2d50**。

## 关键教训(累积,必守)
- **8 面并发收尾撞端点 429 + tab 漂 /project(2026-06-15 R5 实测)**:backend-api/conversation 端点在 8 面同时 collect 时限流(429);同时 6 tab URL 漂到 /project(dispatch 会话锚定 dispatch_gpt_task.py:805 只纠正漂到别的 /c/、不纠正漂到 /project)→ collect 假阴性读 0。**不是 review 没生成**(probe 直读服务器端证实 finished_successfully)。采集法=**前台采集**(开新 tab→/json/activate 强拉前台→导航 /c/→复用 dispatch collect,前台 DOM 渲染绕 429 走 DOM 收附件链),但仍须**逐个间隔、不并发**避免再撞 429;未来轮收尾应错开 collect / 降并发。
- **修一个 timing ≠ 修一类 bug**:R3 的 3bc08b0 seal 只盖 end-of-wave,mid-wave respawn 路径(R3 回归把 `_respawn_all_workers` stub 成 no-op、从未覆盖)结构性绕过 → R4 才挖出。修一个崩溃 timing 后要主动查**所有** timing/分支(还有没有别的路径绕过同一守卫)。**R5 实证: f8a0333 封死了 completed 标志(timing-enum + respawn-boundary 两视角确认无 bypass), 但"修一类 bug"还差两块: (a) success-path respawn TOCTOU(没被 seal 覆盖的第三 timing, F-SCHED-BS-R5-01); (b) 更深: 即便 completed 正确封 False, 保留的崩溃波 INFEASIBLE 被消费侧 persist 成 sticky → resume 毒化(F-SCHED-BS-R5-02)。封"标志"≠封"类": 真正的类 = 崩溃波的 INFEASIBLE 不得成被信任的 sticky proof, 无论经哪条 timing。**
- **逐面 GPT review 会漏跨边界洞, CC 独立审计(验证阶梯第②线)补得到(2026-06-15 R5 实证)**: F-SCHED-BS-R5-02 是 CC 用 workflow 独立审 scheduler 挖出的, 不是任何 GPT review 发现的 —— campaign 面 GPT review 审了同一个 exact_campaign.py 还判零 finding(它核了持久化自身单调性, 没 catch 到崩溃波 INFEASIBLE 从 scheduler/consumer 边界写进来)。洞跨"scheduler 投结果→consumer 持久化→campaign resume"三面边界, 任一单面 review 只看自己半边。**故零 finding 面≠无洞; 关键 soundness 面要 CC 独立全链审, 不只靠逐面外审。**
- **GPT 补丁红→绿对 ≠ 安全,必跑全量回归**:benders 补丁红→绿过却破 V81 静态门(字面 pattern-match),只全量逮到。mid-wave 补丁全量 3141 passed/0 failed 才提交。
- **HIGH/Critical finding 用 3-opus 对抗 workflow 判 reachability**:含被指派"力证 hardening/救 streak"的 refuter;refuter 诚实驳不倒才判 reset。reset 是清零大事不靠我单方。
- **别自设派发限制(2026-06-15 owner「只发一个请求吗?」纠正)**:gpt_dispatch_concurrency.json `max_in_flight=null`=不限,授权台账写明「该几个发几个、不得自我设限」。我之前 R5 顺序单条派发 = 把放开的额度装回去的病。**并发派发现可行**:0614 dispatch raw-CDP per-tab 重写修了 Round2 的 /project 漂移,8 面并发实测全真 Pro 零降级(只需轻量错开发送避 setup-race + Sentinel burst,8 面全在飞)。
- **切换派发策略时别 resume 半途会话**:--resume 一个原 waiter 已被杀、但 server 端还在生成(且可能 stuck)的会话 → 关 tab 后 "unhandled" exit 3。直接 fresh 重发更稳。

- **R6 派发踩坑: 上传后立即 8 并发派发 → sources_verify 误判 FATAL(假空)(2026-06-15)**: 我上传新快照后立即并发派发 8 面, 每面 dispatch 的 sources_verify 读 `in_sources:[]` 假空 → exit 3(不是骤死)。根因两叠加: ① 上传后来源区页没稳定(连 upload 自己的 verify 都读成 entries=1 flaky), 立即派发读到 loading/空; ② 8 并发各开 owns_tab tab 撞 Edge, sources 页渲染不全。`--list`(无并发, 上传后几分钟)证实 3 文件都在(新快照+旧残留+wheels), **无损坏, wheels 安全**。**R6 fresh 重派纪律**: (a) 上传后先 `--list` 轮询到来源区稳定(3 文件齐)再派; (b) 降并发(≤4, 记忆 "≤4 没暴露这么重")或顺序错开发送(每面 navigate+verify+send ~30s, 错开 ≥45s 让 sources 页不撞); (c) dispatch 用 run_in_background 直接跑这次没骤死(exit 3=sources_verify, 非 58/255), 但仍建议 Start-Process detached 更稳。round6/ 失败面目录可清后重派。
- **R6 收集 + 完成检测 + 限流识别三坑(2026-06-15/16, 修于 commit 0c4832c)**:
  - **重页收集崩**: routing 面 GPT 跑 1hr+ 产出 **184 节点**超重会话页 → fg_collect/--resume 的 DOM attach/navigate 崩 4 次(drift /project + ws "no close frame")。**根因经实证不是限流**: 限流期带 auth 探 `/backend-api/conversation/<id>` 返 **200 可读**(裸 fetch 无 auth 才 404)→ drift 是重页客户端渲染失败回退 /project。**重页收集走 backend**(轻量 backend poller 读会话 JSON 判完成/取结论, 不渲染重 DOM); 全文件可放弃(零-finding 结论从会话最终消息取即够, 无 finding 无需 reachability 评估)。
  - **完成检测「Pro 思考中」误判**(owner 截图抓到): `wait_done` 的 generating 只看停止按钮; Pro 扩展多轮——每条进度 note 各自「结束 turn」, 停止按钮暂消失+文本暂稳但「Pro 思考中」还在 → 误判 done 收走进度 note。修: 加 `_THINKING_BUSY_JS` 检测进行中思考指示器(锚定「思考中/Thinking/Reasoning」开头, 排除已完成「思考用时 N/Thought for N」折叠标记), `generating = 停止按钮 OR 思考中`。
  - **限流不识别**(owner 指出): 撞限流只盲目重试+报含糊 ws 死。加 `RateLimited` 异常 + `probe_rate_limited`(页面内 fetch 查 HTTP 429 **或**可见限流消息「太多访问/请求过频/reached your limit」, DOM 扫描限短叶子可见元素避开 <script> 里的 feature-flag 配置串)→ exit 6 + 清晰日志 + fg_collect 即停。**限流真信号校准**: read 端口不返 429(会话可读), 真限流在 **send 侧**(owner 见「太多访问」); DOM 消息检测 live 触发待下次真限流确认。
  - **共同根因 = 拿派生/单点信号当结论**([[fact-self-report-is-not-evidence]]): backend `end_turn=true` 当完成(每条进度都 end_turn 却继续想)、DOM「rate limit」字符串当限流(全是 feature-flag 配置)、drift /project 当限流(实为重页)。owner 当场抓到我「routing 生成完了」的假断言。**判完成看 ground truth(停止按钮+思考指示器+真交付文件), 判限流看 429+可见消息, 别信单一派生标志。**
## 本会话验证方法(有效, 沿用)
- **并发派发**(2026-06-15 起):8 面各独立后台 shell(护栏每单一个 shell),错开 35-245s 发送,8 面全在飞;降级面 dispatch 快 exit 5→重发,真 Pro 20-66min;reply_chars 早期低位慢爬正常。
- **逐面对抗 reachability 核**:每 finding 独立判 canonical-reachable(reset)vs unreachable(需 monkeypatch solve 逻辑/hand-built/malformed/未接线子系统 = hardening),判据 PROJECT_LOCK:160-166,不裸信 GPT severity。零 finding 面也独立核「使任何残留问题不可达的载荷主张」是否真成立。

## owner 行为裁决(feedback, 必守)
- 离线(owner_sleep=true)→ 全自主,一切自己拍板,不准出现只有 owner 能定的事,不 ping。
- 压缩纪律: 每环节结束查上下文(-Context),近 300k → 先更新记忆树 → /compact。
- soundness 判据 = "能否 emit 项目契约说应 UNKNOWN 的 CERTIFIED",非"答案碰巧对"。

相关: [[zmd-project-entry]] overnight-certified-surface-review-arc gpt-delivery-adversarial-agent-review gpt-delivery-no-blind-trust fact-zero-finding-is-not-proof [[no-gpt-channel-architecture]] [[no-gpt-concurrency-field]]
