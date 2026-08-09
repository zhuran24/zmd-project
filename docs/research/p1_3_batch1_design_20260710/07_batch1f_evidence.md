# 批 1F B 段 evidence：生产 smoke 实测（2026-07-10）

> A 段（wrapper 硬帽/w6 注入 + gate 三档分层 + C1 真工件回归）已合入 `f0a7cd4`，
> 慢 lane 31/31。本稿记录 B 段 smoke 实测与 gate 常量回填依据。

## smoke#1：不限 anchor 完整 campaign —— 70×19 撞帽（本批最重要发现）

- 命令：`run_campaign_linux.sh --campaign-hours 1`（wrapper 注入 w6+42G 硬帽全生效，
  日志 `~/m5_runs/batch1f_smoke_20260710_113146.log`）
- 结果：**exit 137，9min47s，cgroup OOM kill**（journal: `Failed with result 'oom-kill'`，
  内核: 单 python 进程 anon-rss **43,947,752 kB ≈ 43.9G**；scope `Consumed 10min 5s CPU,
  42G memory peak`；系统无恙——硬帽兑现了它的全部承诺）
- 死亡现场：campaign 首 anchor **70×19（area 1330）** master solve RUNNING 8 分钟
  （state 存证 `~/m5_runs/batch1f_smoke1_70x19_oom_state.json`）
- RSS 曲线（1s 采样+VmHWM，`batch1f_smoke_20260710_113146.rss.log` 582 点）：
  2min 爬升至 12-13G → **稳态 12-17G 徘徊 7min**（与 batch0 稳态 11-16.6G 吻合）→
  **末段 ~40s 内 17.4G → 31.1G → 41.6G（+24G 断崖）** → 撞帽死。

### 判读（修正 batch0 两条结论）

1. **「w6 安全」只对小 rect 成立**：batch0 全部可行性证据（b0_4r OPTIMAL@541s 等）
   都是 **6×6 ghost（area 36）**；campaign 首 anchor 是 frontier 最大候选 1330 格，
   规模 37×，solve 期传播态+末段大分配远超 42G。
2. **尖峰量级与 worker 数弱相关**：b0_6（w24）+26G/3s，本次（w6）+24G/40s，
   死值同为 anon-rss 43.9G——batch0「大分配被 worker 数放大」假说证伪，
   这是接近某 solve 阶段时的**固定量级大分配事件**；降 worker 只降稳态不降尖峰。
3. **本机（47.7G）上 C1 大 anchor campaign 不可行**是当前 solver 现状（M5 性能线
   的战场，如 C1 family 引导接入候选实验），不是 wrapper/gate 缺陷——readiness gate
   w6=20G 档只对受限 replay/小 anchor 有效，大 anchor campaign 实测 >43.9G，
   47G 保守档反而是诚实的（见下"gate 常量回填"）。

## smoke#2：area-upper-bound 36 受限真链 —— 6×6 也撞帽（回归实锤第一刀）

- 命令：`run_campaign_linux.sh --campaign-hours 1 --area-upper-bound 36`
- 结果：**exit 137，9min52s，42G peak OOM kill**。state 确认死在 `6x6` candidate 的
  **master_solve iteration 1**（heartbeat stage=master_solve/event=start，
  profile=exact_coordinate_guided_branching_v4；跑 8min16s 撞帽），未到 binding/剪杆。
  state 存证 `~/m5_runs/batch1f_smoke2_6x6_oom_state.json`。
- **矛盾**：b0_4r 同机同 w6 同 6×6 温和出解 OPTIMAL@541s（内存 <20G）——
  batch0 用的是原型 C1 patch + 直建，本次是批 1 产品化 C1 + campaign 链。

## smoke#3：同 #2 但无 jemalloc（纯 ptmalloc，与 b0_4r 环境一致）—— 仍撞帽

- 假设检验：wrapper 的 `JEMALLOC_CONF=dirty_decay_ms:-1,muzzy_decay_ms:-1`
  （2026-05-21 witness 时代延迟优化，「内存只增不减」）把瞬态分配累积成撞帽 RSS。
- 结果：**exit oom-kill，9min55s，42G peak**——与 #2 逐秒级一致。**jemalloc 假说证伪**，
  这是分配器无关的真实内存需求。三次撞帽（#1 70×19 / #2 6×6 / #3 6×6-nojemalloc）
  死亡时刻全在 9-10min。
- 中间结论：**批 1 产品化 C1 master 在 6×6 上 solve 期内存 >42G，相对 batch0 原型
  （<20G）存在真实内存回归**。

## smoke#4：当前 HEAD 产品 C1 + 直建（无 campaign 链）—— 直建也撞帽

- 脚本复刻 b0_4r runner 流程但不打原型 patch（产品 C1 默认生效），42G 硬帽+w6。
- 结果：**exit 137，9min18s（solve 段 ~558s 未出解），42G peak OOM kill**。
  build 段正常（core 10.4s/master 15.2s，`c1_pose_bool_cov_channel_v1`，cov=4900）。
- **campaign 链洗清**：直建裸 solve 就撞帽，回归在产品 C1 编码/求解行为本身。

## smoke#5：batch0 原型 patch × 当前 HEAD —— 不兼容，44s 死于 build

- `apply_c1_patch()` 后 `export_core_binding` KeyError（`_c1_pole_intervals_by_pose_idx[0]`
  缺失，exact_coordinate_master.py:3959）——1D 转正后的产品 build 路径与原型 monkeypatch
  面冲突，**原型编码已不可在当前 HEAD 复现**。「编码差异 vs 底座漂移」的最后归因需要
  worktree 回 batch0 时期 HEAD 复刻（归修复批开工侦察）。

## 定位总结（1F 边界内的最终定性）

| 实验 | 形态 | 结果 |
|---|---|---|
| b0_4r（07-09） | 原型 C1 patch + 直建 + w6 | OPTIMAL@541.3s，4.95M branches，<20G |
| smoke#1 | 产品 C1 + campaign 70×19 + jemalloc | 42G OOM @9min47s |
| smoke#2 | 产品 C1 + campaign 6×6 + jemalloc | 42G OOM @9min52s（master_solve iter1） |
| smoke#3 | 产品 C1 + campaign 6×6 + 纯 ptmalloc | 42G OOM @9min55s（jemalloc 证伪） |
| smoke#4 | 产品 C1 + **直建** 6×6 + 纯 ptmalloc | 42G OOM @9min18s（campaign 链洗清） |

**黄金对比**：原型与产品的 cov 通道规模完全相同（cover_literals=4900），build 时长相同
（~10s/~15s）——模型规模无异，但原型 541s 出 OPTIMAL、产品 558s+ 未出解且内存 >42G。
**批 1 产品化 C1 存在求解性能+内存双回归，嫌疑收窄到搜索 profile/约束结构差异**
（原型 patch 时代的 solve 默认 vs 批 1 的 exact_coordinate_guided_branching_v4 及
1B 产品化时的约束结构变化）。归因与修复=数学面（M5/修复批），不在 1F 范围。

## gate w6 档回填（按实测定稿）

w6 档 20G 占位改按实测回填 **44G**（三次 OOM 的内核 anon-rss 证据值 43.9G 上取整）：
本机 parallel=1 时 needed=44+8=52G > 47.7G → gate 恒 BLOCK——这是诚实行为，当前 HEAD
的 C1 在本机任何 anchor 都跑不完 master solve。解除条件：C1 内存回归修复后重测回填。
受限实验跑法用 `EXACT_GATE_WORKER_PEAK_RSS_GIB` override（gate-only，用后 unset）。

## gate 常量回填（待 smoke#2 数据定稿）

- w6 档 20G 占位的适用范围要注明「受限 replay/小 anchor」；大 anchor campaign
  实测 43.9G+ → 任何档位在本机 parallel=1 时 needed=peak+8G，若按大 anchor 真值填
  （44G+8G=52G > 47.7G）gate 恒 BLOCK——**这是诚实行为**：本机现状就是跑不了
  不限 anchor 的 C1 campaign。受限跑用 EXACT_GATE_WORKER_PEAK_RSS_GIB override
  （gate-only env，用后 unset，勿泄漏进 campaign 环境——见 wrapper 头部 WARNING）。
- 待 smoke#2 出稳态/峰值实测后定稿 w6 档数值与注释。

## 归因后记（2026-07-10 晚，M5 归因线三刀判决——本文件「双回归」结论已被推翻）

M5 归因线（`../p1_3_m5_convergence_20260708/m5_c1_memory_attribution_20260710.md`）
三刀实验终判：**无代码回归**。第三刀（88f65a5+原型 patch+runner 全套 env+无 cgroup 帽）
完美复现 b0_4r：OPTIMAL@525.4s、branches 4,982,981、conflicts 1077（逐位相同=solve
确定性），资源证据 HWM 41.58G+VmSwap 峰值 18.57G。

本文件「定位总结」段的正确读法：smoke#1-4 六连灭的共同死因不是产品化回归，而是
**42G 帽+MemorySwapMax=0 低于 C1 solve 出解时刻的固有大分配尖峰**（RSS 需求 >42G、
含 swap 总需求 ~60G 级）；b0_4r 的「w6 温和 <20G」是 30s 空采样只见稳态的观察假象。
产品与原型的结构差异（solve 参数默认值、family×ghost big-M 网络）与撞帽根因解耦，
是否影响产品出解分布待第四刀（产品+原型参数+无帽）验证。

条款派生：42G 帽+禁 swap 不可行；修订方向=允许 zram 吸收尖峰溢出（第三刀实测 wall
525s 比原版还快，短暂尖峰的 swap 性能损失可忽略）。gate w6 档 44G 是「42G 帽下死值」
的诚实下界，数值保留、理由见归因文档。


## 后记 2(2026-07-11 凌晨):「本机大 anchor campaign 不可行」结论作废

修订条款(42G+20G swap)下 70×19 直建重测:**INFEASIBLE@557.5s,尖峰 57G 域被 swap 正常吸收**——smoke#1 当年死于禁 swap 旧条款,离 INFEASIBLE 判决只差 ~30s。大 anchor 的正确结果是被排除(放不下),不是解不动;修订条款下真 campaign 预期全程可行。证据:`../p1_3_m5_convergence_20260708/m5_ab_param_bisect_20260711.md` 附节。
