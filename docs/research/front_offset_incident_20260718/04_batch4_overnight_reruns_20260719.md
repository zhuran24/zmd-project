# Batch 4 值夜重跑记录（2026-07-19 凌晨）

> 承接 `02_batch4_revalidation_results.md`（codex 阶段性复验）与 `03_active_port_boundary_domain_correction.md`（82,829 域修正）。本轮由主会话值夜执行，原始输出在未跟踪目录 `.artifacts/batch4_20260718/prod_ab/`（诊断证据不提交，下文钉关键值）。所有臂 revision：`a0f7525`（批 3+5 池 81,797，域修正 82,829 **不在**本轮臂的输入内——臂跑在域修正合并之前，见 §4 边界）。

## 1. RAB-on 臂重跑：clean run 达成，SIGSEGV 调查销项

原臂（codex，`02` 号 §3）：结果落盘后 `_Py_Finalize` 清理 OR-Tools protobuf 时 SIGSEGV（exit -11），记 `WORKER_FAILED`、非 clean。

重跑（`rab_on_rerun_postmem/`，同配置 6×6/seed 1/1 worker/900s 档/cgroup 20G/24G）：

| 项 | 原臂 | 重跑 |
| --- | --- | --- |
| run_record | WORKER_FAILED, exit -11 | **COMPLETED, exit 0** |
| lbbd_status | UNKNOWN | UNKNOWN |
| exact-safe cuts | 1,208 | **1,208（逐字一致）** |
| LBBD 墙钟 | 48m13s | 48m17s |

判读：①退出崩溃为环境层事件（当日机器内存条超频不稳、owner 调整后消失；同日 preflight xdist 崩溃同源），**不是** protobuf 析构 bug，也不是本仓代码问题——批 4 剩余项"RAB-on cleanup SIGSEGV 独立复现/根因调查"**销项**；②原臂崩溃前落盘的诊断快照与 clean run 逐字一致，其数据可信度追认。

## 2. FCL 生产 lift A/B：两臂齐，lift 默认 OFF 维持

同配置（fcl 实验固定 `--rab on`，lift 为唯一 A/B 变量）：

| 臂 | 终态 | exact-safe cuts | LBBD 墙钟 | 备注 |
| --- | --- | --- | --- | --- |
| lift-off（`fcl_lift__postmem/`，目录名残缺见 §4） | COMPLETED / UNKNOWN | 1,208 | 47m57s | 与 RAB-on 基线一致（符合预期：off 臂=RAB-on 状态基线） |
| lift-on（`fcl_lift_on_postmem/`） | COMPLETED / UNKNOWN | **0** | **2h26m（8,764s）** | 零轮遥测（`raw_empty_by_iteration=[]`）、master 最后一次 solve 零分支零冲突 |

lift-on 的 lift 编码本身正确建起（1,738 元素 / 17 组覆盖 / 219 slot 约束 / RFSC 空集=批 3+5 新语义），但 master 重到在 900s 档内连第一轮 LBBD 都走不完。**判读：07-16/07-17 "lift-ON 解不动 6×6"（`rab_sep_promotion_20260716/06` 终判，错位语义时代）的形态在修正语义 + 81,797 池下复现；"front-clear lift 默认 OFF" 维持（roadmap 台账 #10 不变）。** 附带效应：生产 lift 回答不了 INFEASIBLE 与否 → Round 4/5 bespoke 紧凑 master（10.7K 变量）的重建价值上升（rounds 重跑清单第 3 梯队决策依据）。

诚实边界：lift-on 臂全程被 cgroup 24G 帽节流（峰值 RSS 25.3G 含换页水位；01:06 曾热放宽至 38G，但 LBBD 已于 01:05:35 按时限自然终止，放宽对结果零影响）——墙钟数字受节流放大，**终态 UNKNOWN/0 cuts 的判读与内存无关**（时限内 master 无 incumbent 无 INFEASIBLE 是求解行为，不是资源杀）。

## 3. 域修正合并与终态门（主树）

codex `0c8603d`（82,829 域）+ `5a697c8`（strict cleanroom 包）经对角验收合并入主树（merge `b1cf014`）：

- 逐池闭式对账全中：制造机三池不变（17,952/16,896/16,900），core `2×62²=7,688`（+488）、box `4×68²=18,496`（+544），总 82,829；字节 54,467,709、SHA256 `f05b1291…d280d3` 与 `03` 号钉一致；
- 贴边样本核验：core (0,0) pose 存在且保留 10 个出界口记录（激活合法性推迟 binding，语义落地）；
- strict 外发面禁词扫描零实质命中，validator 确认不在外发包（owner 防牵引拍板）；
- 合并态终态门：preflight `--full` 19/19 PASSED + `--slow-tests` PASSED，双结构 checker 绿。

## 4. 操作坑（复现者须知）

- systemd-run 会把命令串里的 `${VAR}` 在 unit 层展开为空（`$VAR` 存活）：FCL 链式脚本因此第一臂输出目录名残缺为 `fcl_lift__postmem`（内容完好，`run_record.configuration.lift=off`/`arm=fcl_lift_off` 为权威标注）、第二臂因目录撞名被 runner fail-closed 拒绝后单独补跑。给 systemd-run 传含变量的 bash 脚本一律写死参数或转义 `$$`。
- 本轮三臂输入池均为 81,797（`78e2bcf0…`，跑动期间为当时钉值）；82,829 域修正合并在臂完成之后。**若未来判读对贴边 pose 敏感（RAB/FCL 的 empty-domain 计数理论上受 core/box 新增 1,032 pose 影响），需在新池重跑对应臂**——本记录不预判该差异方向。

## 5. witness maximize 臂（WIT-04，凌晨补跑）

harness 扩 `cpsat_max` 臂（v5 配方 `--maximize` 受控重跑，`--time-limit/--hint-from` 透传；测试 7 passed）后在**新池 82,829**（`f05b1291…`，域修正合并后）跑：

- **新池 greedy 基线**：266/266 全放置，0.48s（`witness_newpool/greedy_s0/`）——对照当年贪心天花板 241/266：**"摆不满"这个 witness 构造瓶颈在修正语义+补域后已消失**（批 4 §2 的 greedy/comb 266/266 同向，本轮加上新池贴边域再证）；
- **cpsat_max（1800s + greedy hint）**：FEASIBLE / 235 placed / ghost 净空 / frozen 47（`witness_newpool/cpsat_max_1800/`）——从 hint 出发 LNS 30 分钟只回到 235 < 266，**"CP-SAT maximize 弱于结构化贪心"的历史收官结论（构造日志 cpsat v7）在新池复现**。

判读：WIT-04 收官。witness 线的真瓶颈确认转移为 **routing-aware 布线**（摆满已廉价、绑定 FEASIBLE 已验证，缺的是 front 暴露+17 商品连通的构造器），与 doc 12 §3 的缺口判断在新语义下一致。

## 6. 批 4 剩余项（更新后）

生产 FCL A/B ✅；RAB-on SIGSEGV 调查 ✅（销项）；witness maximize 臂 + 新池基线 ✅（本文 §5）；Rounds 梯队 1-2 ✅（梯队 2 见 `05` 号）；剩：独立零违规审计（witness 链）、Rounds 梯队 3（Round 3 必要条件实体口重证 + Round 4/5 bespoke 紧凑 master 重建——已按 owner 端到端流程派 codex plan 模式进行中）、PB 当前 provenance 工件的完整 solver+verifier 闭环。"24 杠杆穷尽/结构墙"等全称判词维持撤回。
