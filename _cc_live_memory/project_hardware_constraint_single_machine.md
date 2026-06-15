---
name: hardware-constraint-single-machine
index_summary: "主机+1远程 (WAN), 分布式仅 WAN-适配模式."
description: 项目硬件升级，加了第 2 台电脑（家中远程），分布式方向解锁——但 WAN 延迟约束仍排除细粒度同步原语
type: project
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

终末地项目硬件**2026-05-08 更新**：从单机扩展到 **1 主机（i9-13900KS + 48 GiB DDR5 + 消费级 GPU + Windows）+ 1 远程（用户家中，需要远程连接）**。**分布式方向解锁**。原"永不分布式"硬约束作废。

**Why**：用户 2026-05-08 直接说"等下！有第二台电脑了，但是在他家，可能要远程连接，总而言之，分布式也要开始搞了"+ "这个你记得记下来"。这是 explicit 状态变更，不是临时设想。

**新硬件 envelope**：
- **机 A（主机，本地）**：i9-13900KS（8P+16E HT-off 24T）+ 48 GiB DDR5 + 消费级 GPU + Windows + D: 盘
- **机 B（远程，家中）**：规格未知，需要确认（CPU / 内存 / GPU / OS）
- **连接方式**：需要远程连接（WAN 通过 home internet）

**新连接物理约束**（重要）：
- **WAN 延迟**：跨家庭网络 RTT 通常 10-50 ms（不是 LAN sub-ms）
- **WAN 带宽**：home upload 一般 10-50 Mbps，下载 100+ Mbps，**双向不对称**
- **WAN 稳定性**：可能断线 / 抖动；不是 datacenter cluster
- 这意味着**分布式范式选择不能是"LAN cluster"，要适配 WAN**

**How to apply（新策略）**：

**适合 WAN 的分布式模式**（可探索）：
- **Candidate-level 并行**：每台机器独立跑不同 candidate wave（独立 campaign session），完成后合并结果。WAN 负载只在 wave 边界传输 cut pool / incumbent，不是每秒同步。
- **粗粒度任务分配**：master 在机 A，binding/routing subproblem batch 投递机 B，结果回传。延迟 100ms 量级可吸收。
- **Periodic incumbent sync**：每 5-30 min 交换 best 解，不是每 search step。
- **Asynchronous portfolio**：两台跑不同 random_seed / 不同 worker_count profile，定期合并 cut pool。

**不适合 WAN 的模式**（继续排除）：
- **Sub-ms clause sharing**（HordeSat / D-Painless 风格）：需要 LAN sub-ms 同步，WAN 不可行
- **Worker 间细粒度通信**：CP-SAT 内部 worker 间共享，不能跨机
- **强一致 distributed lock**：WAN 跨网怎么 leader election 都不靠谱

**重新评估 R8 调研**（`a08abe0c37f20c6b8`）：原来标"Ray/Dask 在 Phase 3C 多基地扩张时再考虑"现在变成"**值得 PoC**"——但 WAN-aware 选型，不是简单照搬 LAN cluster guide。

**实操开关**：
- 路线图 Excluded 表**移除** "Distributed / multi-machine" 条目
- 路线图 P2 段**新增** "Two-host candidate-level parallel (机 A 主机 + 机 B 远程)" 项
- 等机 B 规格 + 连接方式确定后再细化

**需要补充的信息**：
- 机 B 规格（CPU / 内存 / GPU / OS）—— 决定能否跑 master 还是只能跑 subproblem
- 连接方式（Tailscale / SSH / VPN / RDP）—— 决定文件同步成本
- 远程机使用窗口（24×7 还是 part-time）—— 决定 168h campaign 能否投递

**永远不会做的**（即使加了远程机也排除）：
- 云端 spot 实例（用户 2026-05-08 之前说"不会做"，仍有效）
- 跨 internet 的细粒度同步（物理约束）
- 把手机当节点（用户笑称排除）
