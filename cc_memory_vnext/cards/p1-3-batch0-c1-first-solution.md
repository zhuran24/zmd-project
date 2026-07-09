---
id: p1-3-batch0-c1-first-solution
kind: decision
title: 批0破墙(2026-07-09夜):C1 编码产出项目史首个完整问题 master 解(OPTIMAL@541s/w6,复验六项全过);批1 certified 化开工,1A 已落地
summary: owner 拍板 a+c 当夜,A 批 0 头对头完整收官。**破墙:C1(杆侧 pose 布尔+全局 cov 通道,B1 线性形态的坐标版)在完整 266 实例+6×6 ghost 自由搜索 w6 下 OPTIMAL@541.3s——原机 24h campaign/M5 跨 OS 14 cell/M6 八实验/C6 双发全 UNKNOWN 之后的首个 master 解**;独立覆盖复验(fail-closed v2,终端验证器同语义)六项全过,unforced=0(26 杆每根都是唯一覆盖者,免剪杆);M6 头号悬案「供电可行布局存在性」关闭。**内存条款:C1 内存危险=事件尖峰非稳态**(稳态 16GB→3 秒+26GB,疑似解附近阶段切换×worker 放大;w6 安全/w12 两连 OOM/w24 42G cgroup 帽 9min 击穿)——内存实验标配 systemd-run MemoryMax 硬帽。C6 判负(冲突率 90-150× 兑现机制诊断但节点代价盖过收益,2h 不破墙)。witness 连「钉布局验证已知可行解」都 UNKNOWN@600s(b0_5,又一弱证)。**同夜 GPT Pro 双轨外审**:生产证明链零 BLOCK(bug 审 3 份三重背书);产出硬化批 `c7cd6a4`≈(attach integrity P0 bypass/dedup 去 proto 反射(has_no_overlap_2d 段错误雷)/footprint clone 绑定/复验脚本 fail-closed v2/step_8 文档漂移清扫)。**批 1 開工**:任务书 1A-1F(`docs/research/p1_3_batch1_design_20260710/00_batch1_workplan.md`,codex 起草+主会话四修订);1A 骨架落地 `b755e80`(c1_power_pole_representation 开关默认关=生产零变化,池完整性五重 fail-closed,c1_power_pole_binding clone 往返,双审 opus+codex 拦 3 BUG,慢 lane 30/30);**1B(cov 通道+witness cell 语义替换)开工中,§九带三项双审移交前置(池校验自证式/空池/多 mode 假设)**;旧 witness 编码 owner 已拍板不留(2026-07-10:certified 层不保留 runtime env 对照/回退,旧函数暂留仅供等价测试直调,1D 无阻塞)。流水线定型:任务书主会话亲写/实现 codex/审查按额度弹性(多=opus+codex 双审,实测 opus 12min codex 6min)/主会话终审+reseal。
scope:
  domains:
    - p1-3-master-cut-integration
    - power-encoding
    - batch1-c1-certified
  paths:
    - docs/research/p1_3_a_batch0_20260709/README.md
    - docs/research/p1_3_batch1_design_20260710/00_batch1_workplan.md
    - src/models/exact_coordinate_master.py
  symbols:
    - c1_power_pole_representation
    - _validate_c1_power_pole_pool
    - c1_power_pole_binding
status: active
priority: P0
triggers:
  intents:
    - batch1-implementation
    - power-encoding-work
    - m5-ab-testing
  keywords:
    - C1
    - 破墙
    - 首解
    - batch1
    - 批1
    - cov 通道
    - pose 布尔
    - OPTIMAL
  negative_keywords: []
  paths:
    - src/models/exact_coordinate_master.py
    - docs/research/p1_3_batch1_design_20260710/
  symbols:
    - c1_power_pole_representation
  error_regex: []
  examples:
    - 批 1 下一批做什么
    - C1 编码的首解数据在哪
activation:
  layer_hint: L0
  reason: 项目根本状态跃迁（首解之墙破+批 1 主线开工），任何 P1.3 后续会话都需要先知道这个。
provenance:
  op: record
  reason: 2026-07-09 深夜批 0 收官+破墙+双外审+批 1 开工的一线记录。
  evidence:
    - docs/research/p1_3_a_batch0_20260709/README.md（完整结果表）
    - git log 88f65a5..b755e80
updated_at: "2026-07-10"
---

详见 summary。关键 commit 链：`88f65a5`（破墙+双考古）→ `ac9fc7d`（b0_5）→ `8659558`（b0_6 内存尖峰）→ `c7cd6a0`（硬化批）→ `a0f1c2c`（批 1 任务书）→ `b755e80`（1A 落地）。姊妹卡 [[p1-3-m6-power-encoding-diagnosis]]（病因）、[[p1-3-m5-phase1-verdict]]（战场史）。
