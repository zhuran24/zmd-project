# 批 1F 实现规格书：生产 replay 与内存条款（主会话亲写定稿）

> 2026-07-10，HEAD `28df9f4`（1E 已收口）。承 `05_batch1f_recon.md` 形态拍板草案，
> 任务书 §七.6。1F 是批 1 收口批：跑完向 owner 交批 1 完成战报 + M5 A/B 解锁通知。

## §0 目标与形态拍板（recon 草案转正）

1. **完整 certified smoke，不复刻 b0_4r**：`run_campaign_linux.sh` 跑
   `main.py --mode certified_exact` 短 campaign（w6+42G 硬帽），终点
   CANDIDATE_PROPOSED。理由：1D 后 C1 已是 certified 默认，全链一次走真
   （C1 master → binding/routing → 1C 剪杆 → proposal 材料 → terminal verifier →
   proof artifacts 可重放），比 monkeypatch 原型复刻更贴验收本意。
   b0_4r（6×6 OPTIMAL@541s，w6 同机）作 wall-clock 参考锚。
2. **资源条款（batch0 evidence 定稿）**：C1 内存危险=事件尖峰非稳态
   （b0_6：稳态 11-16.6G，出解时刻 3 秒 +26GB 断崖，w24 硬帽 9min 击穿；
   w12 两连死；w6 含出解全程温和）。→ **w6 + MemoryMax=42G + MemorySwapMax=0 +
   单发铁律**（prod-scale solve 一次一个，双发=47.7G OOM 双杀实测）。
3. **两段式执行**：代码改动（A 段，codex）先行合入 → smoke 实验（B 段，主会话长跑）
   → RSS 常量按实测回填（B 段尾，主会话小改）。gate 常量更新依赖实测数据，不预填。

## §1 改动面（A 段，codex 实现）

1. **`scripts/run_campaign_linux.sh` cgroup 硬帽 + w6 注入**（launch 段 :144-155）：
   - launch 命令外包 `systemd-run --user --scope -p MemoryMax=42G -p MemorySwapMax=0`
     （`--scope` 保持前台 exec 语义与退出码透传；b0_6 用的 `--unit` 形态是后台监控向，
     wrapper 场景 scope 更贴）。systemd-run 不可用时回退现行为并显式 WARN（别静默裸奔）。
   - 硬帽值可被 env `CAMPAIGN_MEMORY_MAX`（如 `42G`）覆盖，缺省 42G；`CAMPAIGN_NO_CGROUP=1`
     显式退出硬帽（记录到 stdout）。
   - 注入 `EXACT_MASTER_CP_SAT_WORKERS=6`（stage 专属 env，recon 已核在 operational
     allowlist）——**显式 env 已设时不覆盖**（`: "${EXACT_MASTER_CP_SAT_WORKERS:=6}"` 形态）。
   - 与 taskset 组合顺序：`systemd-run ... taskset -c <list> python main.py ...`。
2. **`scripts/production_readiness_gate.py` RSS 模型 C1 化框架**（:330-365）：
   - 现模型 `needed = parallel × WORKER_PEAK_RSS_GIB(30.0 默认) + HOST_OVERHEAD_GIB(8.0)`
     是 witness 30GB 时代估值。A 段只做**框架**：peak 估值按 `EXACT_MASTER_CP_SAT_WORKERS`
     分层（w≤6 / 6<w≤12 / w>12 三档），档位常量先用 batch0 已有实测占位
     （w6 档 ≈20（b0_4r 温和上限+余量）、w12 档 47（两连死=不放行）、w24 档 47（击穿=不放行）），
     **B 段按 smoke rss.log 实测回填 w6 档**。env override `EXACT_GATE_WORKER_PEAK_RSS_GIB`
     语义保持（覆盖任何档位）。
   - 注意该文件非 sealed（已核不在 preflight FROZEN/checker pin 面），常规 preflight 即可；
     不新增 EXACT_* env 名（沿用已有两个），不触碰 benders allowlist。
3. **C1 真实工件 build 形态回归**（1D 遗留）：现有 C1 回归全是玩具 fixture；补一条
   吃 `candidate_placements.json` 真工件 build 路径的 C1 形态断言（family literals/
   cov channel stats 非零形态，参照 `test_regression.py::test_exact_optional_cardinality_bounds_align_with_family_counts`
   的真工件测试形态与 1D 的 c1=False 显式适配史）。**必登记 conftest `_SLOW_TEST_NODEIDS`**
   （预估 ≥8s），并按工件缺失优雅 skip（防 lightweight checkout 硬失败）。

## §2 smoke 执行序列（B 段，主会话）

1. 前置：A 段合入+双审+慢 lane 绿；无其他重负载并发（树冻结+单发铁律）。
2. RSS 采样：复用 b0_6 rss.log 采样先例，**间隔 ≤1s**（尖峰 3 秒级）。
3. 跑：`scripts/run_campaign_linux.sh --campaign-hours <短时>`（触发 production gate 的
   下限按 main.py 现行为核实；若 smoke 不需 24h 门槛则直跑短 campaign）。
   监控：`systemctl --user is-active` 判死 + `journalctl --user` 验尸（OOM 杀进程组，
   done 标记写不出来——recon 环境卡配方）。
4. 记录：wall time、peak RSS（稳态+尖峰）、proof_summary（含 power_pole_dominance
   审计 key 非空=1C 剪杆真链生效证据）、terminal verifier 结果、可重放验证。
5. 回填：w6 档 peak 常量按实测+尖峰余量更新（主会话小改+preflight）。
6. evidence 文档：`docs/research/p1_3_batch1_design_20260710/07_batch1f_evidence.md`。

## §3 验收清单（含 1D 教训纪律）

- [ ] w6+42G 硬帽完整 certified smoke 不 OOM，终点 CANDIDATE_PROPOSED
- [ ] terminal verifier PASS；proof artifacts 重放通过
- [ ] proof_summary 含非空 power_pole_dominance 审计 key（剪杆真链证据）
- [ ] wall/RSS（稳态+尖峰）入 evidence 文档；w6 档 gate 常量已按实测回填
- [ ] wrapper 硬帽/w6 注入行为有测试或至少 bash -n + 手动 dry-run 记录
- [ ] C1 真工件回归绿且已登记 conftest slow 集
- [ ] 双 checker 绿 + preflight 19 过 + **全量 fast 直跑 + 全量 slow 直跑**
      （四批盲区教训必列；跑法按解释器间歇病 SOP：崩则 coredumpctl 定性+分族拆跑）
- [ ] w12/w24 optional perf lane 明确标注不阻塞（可后置单开）

## §4 纪律与风险

- **单发铁律**：smoke 期间禁并发慢 lane/全量 pytest/另一个 solve。
- 解释器间歇病（7 崩三形态账目见 memory 卡）：长跑输出全量落文件+echo exit，
  禁 `| tail`；smoke 本体是 or-tools native 负载，与解释器病区分验尸（cp_model_helper
  崩溃是另一回事，卡里已注）。
- wrapper 改动风险：`exec` 语义变化（systemd-run 包裹后信号传递/退出码）要在 dry-run
  里显式验证 Ctrl-C 与 exit code 透传。
- M5 候选实验只记录不实现：「C1 family 引导接入」（guidance 挂 residual loop，
  C1 杆非 residual 永不触发，b0 破墙 541s 即此形态）——入 M5 实验清单。

## §5 分工

规格书=主会话（本稿）；A 段实现=codex（一次性任务书，指令写全）；审查=fable+codex
双审（额度弹性制）；B 段 smoke 执行+RSS 回填+终审+批 1 战报=主会话。
